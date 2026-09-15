import re
from pathlib import Path

from .parsing import extract_process_block
from .scoring import compute_mrs

MULTITOOL_KITS = {
    "samtools",
    "bcftools",
    "bedtools",
    "gatk",
    "picard",
    "ucsc",
    "bwa",
    "salmon",
    "kallisto",
    "subread",
    "hmmer",
    "epang",
    "gappa",
    "deeptools",
    "macs2",
    "bowtie2",
    "star",
    "minimap2",
    "umitools",
    "sambamba",
    "stringtie",
    "rseqc",
    "preseq",
    "gffread",
    "seqtk",
    "sratoolkit",
    "qualimap",
    "seqkit",
}


def _extract_include_info(line):
    am = re.search(r"include\s+\{([^}]+)\}", line, re.IGNORECASE)
    if not am:
        return None, None
    content = am.group(1)
    names = []
    for name in re.split(r"[;\s]+", content):
        name = name.strip()
        if name:
            names.append(name.split()[0].lower())
    fm = re.search(r"""from\s+['"]([^'"]+)['"]""", line, re.IGNORECASE)
    inc_path = fm.group(1) if fm else None
    return names, inc_path


def _resolve_include_path(current_nf_file, inc_path):
    base = current_nf_file.parent / inc_path
    for candidate in [base, base.with_suffix(".nf"), base / "main.nf"]:
        try:
            resolved = candidate.resolve()
            if resolved.is_file():
                return resolved
        except (OSError, RuntimeError):
            continue
    return None


def _find_process_in_file(lines, tool_name):
    for lineno, line in enumerate(lines, 1):
        m = re.match(r"(?:process|workflow)\s+(\w+)", line.strip(), re.IGNORECASE)
        if m:
            pname = m.group(1).lower()
            if pname == tool_name or tool_name in pname or pname in tool_name:
                block = extract_process_block(lines, lineno)
                if block:
                    return lineno, line, block[0], block[1]
    return None


def _scan_dir_for_process(clone_path, dir_path, tool_name):
    search_dir = clone_path / dir_path if not dir_path.is_absolute() else dir_path
    if not search_dir.is_dir():
        return None
    for nf in sorted(search_dir.rglob("*.nf"))[:20]:
        try:
            nf_lines = nf.read_text().splitlines()
        except Exception:
            continue
        for lineno, line in enumerate(nf_lines, 1):
            m = re.match(r"(?:process|workflow)\s+(\w+)", line.strip(), re.IGNORECASE)
            if m:
                pname = m.group(1).lower()
                if pname == tool_name or tool_name in pname or pname in tool_name:
                    block = extract_process_block(nf_lines, lineno)
                    if block:
                        return nf, nf_lines, lineno, line, block[0], block[1]
    return None


def _has_heredoc(block_lines):
    for line in block_lines:
        if '"""' in line or "template" in line.lower():
            return True
    return False


def _try_score_include(
    nf, inc_path, base, clone_path, nfcore_base_names, cache_key=None, config=None
):
    target_file = _resolve_include_path(nf, inc_path) if inc_path else None
    if not target_file:
        return None, None, None, None, None
    try:
        target_lines = target_file.read_text().splitlines()
    except Exception:
        return None, None, None, None, None

    r = _find_process_in_file(target_lines, base)
    if r:
        t_lineno, t_line, t_start, t_end = r
        comp = compute_mrs(
            target_lines[t_start : t_end + 1],
            nfcore_base_names,
            cache_key=cache_key,
            config=config,
        )
        if comp.get("tool_cmds") or _has_heredoc(target_lines[t_start : t_end + 1]):
            return 0.0, target_file, t_lineno, t_line, comp

    target_dir = target_file.parent if target_file.is_file() else target_file
    scan_result = _scan_dir_for_process(clone_path, target_dir, base)
    if scan_result:
        nf_file, nf_lines, lineno, line, t_start, t_end = scan_result
        comp = compute_mrs(
            nf_lines[t_start : t_end + 1],
            nfcore_base_names,
            cache_key=cache_key,
            config=config,
        )
        return 0.0, nf_file, lineno, line, comp

    return None, None, None, None, None
