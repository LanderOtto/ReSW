import re
from collections import Counter
from pathlib import Path

from .cache import build_input_cache_from_clone
from .parsing import (
    detect_script_interpreter,
    extract_process_block,
    get_parse_fail_count,
    reset_parse_fail_counter,
)
from .resolve import (
    MULTITOOL_KITS,
    _extract_include_info,
    _find_process_in_file,
    _resolve_include_path,
)
from .scoring import compute_mrs

_VERSION_PRINTERS = frozenset(
    {
        "get_software_versions",
        "getversions",
        "software_versions",
        "versions",
    }
)


def _is_version_printer(pname):
    return pname.lower() in _VERSION_PRINTERS


def _is_exact_match(pname, base, nfcore_subtools_set=None):
    if pname == base:
        return True
    if base not in MULTITOOL_KITS:
        return False
    suffix = pname[len(base) :].lstrip("_")
    if not suffix:
        return True
    if nfcore_subtools_set is not None:
        return f"{base}/{suffix}" in nfcore_subtools_set
    return False


def _classify_process(pname, nfcore_base_set, nfcore_subtools_set=None):
    """Classify a process as exact, metric, or skip.

    Returns ("exact", base) or ("metric", None) or ("skip", reason).
    """
    if _is_version_printer(pname):
        return ("skip", "version_printer")
    for base in nfcore_base_set:
        if base not in pname:
            continue
        if _is_exact_match(pname, base, nfcore_subtools_set):
            return ("exact", base)
    return ("metric", None)


def count_script_interpreters(clone_path, nfcore_subworkflows=None):
    """Count the script interpreter of every countable process block.

    Mirrors the scope of ``scan_nf_files_for_nfcore_tools``: same ``.nf``
    traversal (first 100 files, vendored nf-core module/subworkflow files
    excluded), same version-printer / subworkflow-name skips, and per-process
    dedup. Returns ``{interpreter: count}`` including a ``"default"`` bucket
    for processes whose script carries no ``#!`` shebang.
    """
    clone_path = Path(clone_path).resolve()
    nfcore_subworkflow_set = set(s.lower() for s in (nfcore_subworkflows or []))
    nf_files = list(clone_path.rglob("*.nf"))
    interpreters = {}
    seen = set()

    for nf in nf_files[:100]:
        parts = list(nf.parts)
        if "modules" in parts and "nf-core" in parts:
            im = parts.index("modules")
            if im + 1 < len(parts) and parts[im + 1] == "nf-core":
                continue
            isw = parts.index("subworkflows") if "subworkflows" in parts else -1
            if isw >= 0 and isw + 1 < len(parts) and parts[isw + 1] == "nf-core":
                continue
        try:
            lines = nf.read_text().splitlines()
        except Exception:
            continue
        for lineno, line in enumerate(lines, 1):
            s = line.strip()
            m = re.match(r"process\s+(\w+)", s, re.IGNORECASE)
            if not m:
                continue
            pname = m.group(1).lower()
            if _is_version_printer(pname):
                continue
            if pname in nfcore_subworkflow_set:
                continue
            rel = str(nf.relative_to(clone_path))
            if (rel, lineno) in seen:
                continue
            seen.add((rel, lineno))
            block = extract_process_block(lines, lineno)
            if not block:
                continue
            interp = detect_script_interpreter(lines[block[0] : block[1] + 1])
            interpreters[interp] = interpreters.get(interp, 0) + 1
    return interpreters


def scan_nf_files_for_nfcore_tools(
    clone_path, nfcore_modules, nfcore_base_names, nfcore_subworkflows=None, config=None
):
    reset_parse_fail_counter()
    build_input_cache_from_clone(clone_path)
    exact = set()
    exact_subworkflows = set()
    custom_subworkflows = set()
    evidence = []
    infra_only_entries = []
    seen_evidence = set()
    clone_path = Path(clone_path).resolve()
    nf_files = list(clone_path.rglob("*.nf"))
    nfcore_subtools_set = set(m.lower() for m in nfcore_modules)
    nfcore_base_set = set(b.lower() for b in nfcore_base_names)
    nfcore_subworkflow_set = set(s.lower() for s in (nfcore_subworkflows or []))
    total_process_count = 0
    script_interpreters = count_script_interpreters(clone_path, nfcore_subworkflows)

    skip_counter = Counter()

    for nf in nf_files[:100]:
        if "modules" in nf.parts and "nf-core" in nf.parts:
            parts_set = set(nf.parts)
            idx_mod = nf.parts.index("modules") if "modules" in nf.parts else -1
            idx_sw = (
                nf.parts.index("subworkflows") if "subworkflows" in nf.parts else -1
            )
            if (
                idx_mod >= 0
                and idx_mod + 1 < len(nf.parts)
                and nf.parts[idx_mod + 1] == "nf-core"
            ):
                continue
            if (
                idx_sw >= 0
                and idx_sw + 1 < len(nf.parts)
                and nf.parts[idx_sw + 1] == "nf-core"
            ):
                continue

        try:
            lines = nf.read_text().splitlines()
        except Exception:
            continue
        for lineno, line in enumerate(lines, 1):
            s = line.strip()
            if s.startswith("include"):
                module_names, inc_path = _extract_include_info(s)
                if not module_names:
                    continue

                got_subworkflow = False
                for mname in module_names:
                    if inc_path and "subworkflows/nf-core" in inc_path:
                        if mname in nfcore_subworkflow_set:
                            exact_subworkflows.add(mname)
                            got_subworkflow = True
                        elif nfcore_subworkflow_set:
                            exact_subworkflows.add(mname)
                            got_subworkflow = True
                    elif mname in nfcore_subworkflow_set:
                        custom_subworkflows.add(mname)
                        got_subworkflow = True
                if got_subworkflow:
                    continue

                for mname in module_names:
                    for base in nfcore_base_set:
                        if base not in mname or not _is_exact_match(
                            mname, base, nfcore_subtools_set
                        ):
                            continue
                        target_file = (
                            _resolve_include_path(nf, inc_path) if inc_path else None
                        )
                        if not target_file:
                            continue
                        try:
                            target_lines = target_file.read_text().splitlines()
                        except Exception:
                            continue
                        r = _find_process_in_file(target_lines, base)
                        if not r:
                            continue
                        t_lineno, t_line, _, _ = r
                        src_rel = str(target_file.relative_to(clone_path))
                        key = (base, src_rel, t_lineno)
                        if key in seen_evidence:
                            continue
                        seen_evidence.add(key)
                        exact.add(base)
                        evidence.append(
                            (
                                src_rel,
                                t_lineno,
                                t_line.strip(),
                                base,
                                "exact",
                                0.0,
                                {
                                    "score": 0.0,
                                    "tool_ratio": 1.0,
                                    "tool_cmds": [],
                                    "tool_cmds_fullname": [],
                                },
                            )
                        )
                continue
            m = re.match(r"process\s+(\w+)", s, re.IGNORECASE)
            if not m:
                continue
            pname = m.group(1).lower()

            # Subworkflow names take priority
            if pname in nfcore_subworkflow_set:
                if pname not in exact_subworkflows and pname not in custom_subworkflows:
                    custom_subworkflows.add(pname)
                continue

            nf_rel = str(nf.relative_to(clone_path))

            kind, tag = _classify_process(pname, nfcore_base_set, nfcore_subtools_set)

            if kind == "skip":
                skip_counter[tag] += 1
                continue

            if kind == "exact":
                key = (tag, nf_rel, lineno)
                if key in seen_evidence:
                    continue
                seen_evidence.add(key)
                exact.add(tag)
                block = extract_process_block(lines, lineno)
                if not block:
                    skip_counter["failed_parsing"] += 1
                    continue
                comp = compute_mrs(
                    lines[block[0] : block[1] + 1],
                    nfcore_base_names,
                    cache_key=tag,
                    config=config,
                )
                total_process_count += 1
                evidence.append((nf_rel, lineno, line.strip(), tag, "exact", 0.0, comp))
                continue

            # kind == "metric"
            key = (pname, nf_rel, lineno)
            if key in seen_evidence:
                continue
            seen_evidence.add(key)
            block = extract_process_block(lines, lineno)
            if not block:
                skip_counter["failed_parsing"] += 1
                continue
            comp = compute_mrs(
                lines[block[0] : block[1] + 1], nfcore_base_names, config=config
            )
            tools = comp.get("tool_cmds", [])
            if not tools:
                if not comp.get("all_tokens"):
                    skip_counter["no_tools"] += 1
                    continue
                comp["infra_only"] = True
                infra_only_entries.append((nf_rel, lineno, line.strip(), pname, comp))
                continue
            total_process_count += 1
            evidence.append(
                (nf_rel, lineno, line.strip(), pname, "metric", comp["score"], comp)
            )
    return (
        sorted(exact),
        evidence,
        infra_only_entries,
        sorted(exact_subworkflows),
        sorted(custom_subworkflows),
        total_process_count,
        dict(skip_counter),
        get_parse_fail_count(),
        script_interpreters,
    )
