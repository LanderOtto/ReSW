"""Tool inventory of the nf-core reference module library.

Each nf-core module ``main.nf`` (a single process) declares the software it
reports via ``emit: versions_*`` output channels, e.g.::

    tuple val("${task.process}"), val('bwa'), eval('bwa 2>&1 | ...'),
          topic: versions, emit: versions_bwa
    tuple val("${task.process}"), val('samtools'), eval('samtools version ...'),
          topic: versions, emit: versions_samtools

``declared`` parses those ``val('tool')`` literals (the authoritative signal).
``script`` derives tools from the ``script:`` heredoc via the shared bashlex
extractor (a cross-check: it can miss tools invoked through Groovy variables,
e.g. ``bwa__mem`` calls ``samtools`` via ``$pipe_command``).
"""

import re
import urllib.request
from collections import Counter
from pathlib import Path

from .parsing import _extract_all_tools, _extract_shell_script, extract_process_block

_VERSIONS_EMIT = re.compile(r"\bemit:\s*versions\w*", re.IGNORECASE)
_VAL_OF = re.compile(r"""val\((['"])(.*?)\1\)""", re.DOTALL)
_IDENTIFIER = re.compile(r"^[A-Za-z0-9_.+\-]+$")
_VERSION_LIKE = re.compile(r"^v?\d")
_SECTION_HEADER = re.compile(
    r"^\s*(input|output|script|when|exec|workflow)\s*:", re.IGNORECASE
)
_PROCESS_LINE = re.compile(r"\s*process\s+\w+", re.IGNORECASE)

_NFCORE_MODULES_RAW_BASE = "https://raw.githubusercontent.com/nf-core/modules/master"

# Groovy / shell-scripting tokens that leak through the bashlex extractor and
# are not real bioinformatics tools.
_SHELL_TOKEN_STOP = frozenset(
    {
        "def",
        "assert",
        "true",
        "false",
        "null",
        "return",
        "string",
        "integer",
        "boolean",
        "double",
        "float",
        "list",
        "map",
        "println",
        "log",
        "import",
        "class",
        "for",
        "while",
        "foreach",
        "if",
        "then",
        "else",
        "fi",
        "do",
        "done",
        "case",
        "esac",
        "in",
        "and",
        "or",
        "not",
        "end",
        "each",
    }
)


def _declared_tools(lines):
    """Parse ``val('tool')`` literals from ``emit: versions_*`` output lines."""
    tools = set()
    in_output = False
    for line in lines:
        ls = line.strip()
        m = _SECTION_HEADER.match(ls)
        if m:
            in_output = m.group(1).lower() == "output"
            continue
        if not in_output or not _VERSIONS_EMIT.search(ls):
            continue
        for mm in _VAL_OF.finditer(ls):
            v = mm.group(2)
            if not v or v.startswith("$") or "$" in v:
                continue
            if not _IDENTIFIER.match(v) or _VERSION_LIKE.match(v):
                continue
            tools.add(v.lower())
    return tools


def _script_tools(lines):
    """Distinct tools invoked in the module's ``script:`` heredoc."""
    for lineno, line in enumerate(lines, 1):
        if not _PROCESS_LINE.match(line):
            continue
        block = extract_process_block(lines, lineno)
        if not block:
            return set()
        shell = _extract_shell_script(lines[block[0] : block[1] + 1])
        if not shell:
            return set()
        _all, tools, _full = _extract_all_tools(shell)
        return {
            t.lower()
            for t in tools
            if t.lower() not in _SHELL_TOKEN_STOP and not _VERSION_LIKE.match(t)
        }
    return set()


def _discrepancy_reason(declared, script):
    if declared and script:
        if declared != script:
            return "mismatch"
        return None
    if declared:
        return "script_empty"
    if script:
        return "no_declared"
    return "both_empty"


def ensure_nfcore_module_files(module_dir, module_names):
    """Download missing nf-core module ``main.nf`` files into ``module_dir``.

    Only downloads files that are absent (mirrors ``nfx_bash_analysis``
    without importing it, avoiding a circular dependency). Returns the number
    of files present after the call.
    """
    from concurrent.futures import ThreadPoolExecutor

    module_dir = Path(module_dir)
    module_dir.mkdir(parents=True, exist_ok=True)

    missing = []
    for name in module_names:
        fpath = module_dir / f"{name.replace('/', '__')}.nf"
        if not fpath.exists():
            missing.append(name)

    def fetch_one(name):
        fpath = module_dir / f"{name.replace('/', '__')}.nf"
        url = f"{_NFCORE_MODULES_RAW_BASE}/modules/nf-core/{name}/main.nf"
        try:
            with urllib.request.urlopen(url, timeout=60) as resp:
                fpath.write_text(resp.read().decode())
        except Exception:
            return None
        return name

    if missing:
        with ThreadPoolExecutor(max_workers=16) as exec:
            list(exec.map(fetch_one, missing))

    return len(list(module_dir.glob("*.nf")))


def count_nfcore_module_tools(module_dir):
    """Tool inventory for every nf-core module ``main.nf`` under ``module_dir``.

    Returns per-module records plus aggregates suitable for the CLI report and
    ``nextflow_analysis.json``.
    """
    module_dir = Path(module_dir)
    per_module = {}
    declared_counter = Counter()
    union_counter = Counter()
    top_declared = Counter()
    top_script = Counter()
    multi_tool = {}
    discrepancies = {}
    parse_fail = 0

    files = sorted(module_dir.glob("*.nf")) if module_dir.is_dir() else []
    for f in files:
        name = f.stem
        try:
            lines = f.read_text().splitlines()
        except Exception:
            parse_fail += 1
            continue
        declared = _declared_tools(lines)
        script = _script_tools(lines)
        union = declared | script

        declared_counter[len(declared)] += 1
        union_counter[len(union)] += 1
        top_declared.update(declared)
        top_script.update(script)

        reason = _discrepancy_reason(declared, script)
        per_module[name] = {
            "declared": sorted(declared),
            "script": sorted(script),
            "union": sorted(union),
            "n_declared": len(declared),
            "n_script": len(script),
            "discrepancy": reason,
        }
        if reason == "mismatch":
            discrepancies[name] = {
                "declared": sorted(declared),
                "script": sorted(script),
                "reason": reason,
            }
        if len(declared) >= 2:
            multi_tool[name] = sorted(union)

    return {
        "modules_total": len(files),
        "parse_fail": parse_fail,
        "with_declared_tools": declared_counter.total() - declared_counter[0],
        "by_n_declared": dict(sorted(declared_counter.items())),
        "by_n_union": dict(sorted(union_counter.items())),
        "top_declared_tools": top_declared.most_common(),
        "top_script_tools": top_script.most_common(),
        "multi_tool_modules": multi_tool,
        "discrepancies": discrepancies,
        "per_module": per_module,
    }
