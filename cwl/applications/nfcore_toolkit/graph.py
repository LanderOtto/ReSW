"""Convert nf-core DAG JSON to the agnostic .graph.json format.

Output matches the format produced by graph_builder, so it can be fed
directly into pattern_aggregator build — the tool already used by the
CWL extraction pipeline.

Tool name resolution (module-path-based):
- nf-core/local steps: mod_path (e.g. "samtools/sort") → dotted name (e.g. "samtools.sort")
- heuristic steps: raw process name as-is
"""

import json
import os
import re
import subprocess
from pathlib import Path


def _find_nxf_home():
    return os.environ.get("NXF_HOME") or os.path.expanduser("~/.nextflow")


def resolve_clone_path(pipeline_name):
    """Find the clone directory matching the active git revision.

    Priority:
    1. Git bare repo HEAD → commit hash clone (authoritative)
    2. Newest clone that has modules/nf-core/
    3. Newest clone overall
    """
    nxf_home = _find_nxf_home()
    base = Path(nxf_home) / "assets" / ".repos" / pipeline_name
    clones_dir = base / "clones"
    if not clones_dir.is_dir():
        return None

    # Strategy 1: git bare repo HEAD → commit hash
    bare_dir = base / "bare"
    if bare_dir.is_dir():
        try:
            result = subprocess.run(
                ["git", "--git-dir", str(bare_dir), "rev-parse", "HEAD"],
                capture_output=True,
                text=True,
                timeout=10,
            )
            if result.returncode == 0:
                commit_hash = result.stdout.strip()
                clone_path = clones_dir / commit_hash
                if clone_path.is_dir():
                    return clone_path
        except Exception:
            pass

    # Strategy 2: newest clone with modules
    clones = sorted(clones_dir.iterdir(), key=lambda p: p.stat().st_mtime, reverse=True)
    for clone in clones:
        if (clone / "modules" / "nf-core").is_dir():
            return clone
    # Strategy 3: newest clone as last resort
    return clones[0] if clones else None


def _build_modules_map(clone_path, subdir):
    """Build {process_name: (canonical_name, submodule_path)} from a module subdirectory.

    Walks modules/<subdir>/<tool>/.../main.nf and extracts process name + tool path.
    Returns both a process-to-name map and a process-to-path map.
    Keys are lowercased for case-insensitive matching.
    """
    modules_base = clone_path / "modules" / subdir
    if not modules_base.is_dir():
        return {}, {}

    name_map = {}
    path_map = {}
    for main_nf in modules_base.rglob("main.nf"):
        if not main_nf.is_file():
            continue
        rel_path = main_nf.relative_to(modules_base)
        tool_name = rel_path.parts[0].lower()
        sub_path = "/".join(p.lower() for p in rel_path.parts[:-1])
        with open(main_nf) as f:
            first_line = f.readline().strip()
        m = re.match(r"process\s+(\S+)", first_line)
        if m:
            name_map[m.group(1).lower()] = tool_name
            path_map[m.group(1).lower()] = sub_path

    return name_map, path_map


def build_module_map(pipeline_name):
    """Build {process_name: canonical_tool} from cached nf-core module files.

    Resolves the active clone via git bare repo HEAD, then walks
    modules/nf-core/<tool>/.../main.nf to extract process -> tool mappings.
    Returns only the name_map for backward compatibility.
    """
    clone_path = resolve_clone_path(pipeline_name)
    if not clone_path:
        return {}
    name_map, _ = _build_modules_map(clone_path, "nf-core")
    return name_map


def build_local_module_map(pipeline_name):
    """Build {process_name: module_path} from local module files.

    Walks modules/local/<name>/.../main.nf and returns
    (name_map, path_map) for process classification.
    """
    clone_path = resolve_clone_path(pipeline_name)
    if not clone_path:
        return {}, {}
    return _build_modules_map(clone_path, "local")


def _build_modules_map_root(clone_path):
    """Walk modules/ root for main.nf, excluding modules/nf-core/ and modules/local/.

    Handles non-standard layouts where modules sit directly under modules/
    (e.g. modules/tool/main.nf instead of modules/nf-core/tool/main.nf).
    """
    modules_base = clone_path / "modules"
    if not modules_base.is_dir():
        return {}, {}

    name_map = {}
    path_map = {}
    for item in modules_base.iterdir():
        if not item.is_dir():
            continue
        if item.name in ("nf-core", "local"):
            continue
        for main_nf in item.rglob("main.nf"):
            if not main_nf.is_file():
                continue
            rel_path = main_nf.relative_to(modules_base)
            tool_name = rel_path.parts[0].lower()
            sub_path = "/".join(p.lower() for p in rel_path.parts[:-1])
            with open(main_nf) as f:
                first_line = f.readline().strip()
            m = re.match(r"process\s+(\S+)", first_line)
            if m:
                name_map[m.group(1).lower()] = tool_name
                path_map[m.group(1).lower()] = sub_path

    return name_map, path_map


def build_module_maps(pipeline_name):
    """Build all module maps for a pipeline in one call.

    Returns (nfcore_name_map, nfcore_path_map, local_name_map, local_path_map).
    The path maps are used by _classify_step for module origin tracking.
    Also discovers root-level modules (not under nf-core/ or local/).
    """
    clone_path = resolve_clone_path(pipeline_name)
    if not clone_path:
        return {}, {}, {}, {}
    nn, np = _build_modules_map(clone_path, "nf-core")
    ln, lp = _build_modules_map(clone_path, "local")
    rn, rp = _build_modules_map_root(clone_path)
    for k in rn:
        if k not in nn and k not in ln:
            nn[k] = rn[k]
            np[k] = rp[k]
    return nn, np, ln, lp


def _classify_step(step_label, nfcore_map, local_map):
    """Classify a DAG step by module origin.

    Returns (origin, module_path) where origin is one of:
    - "nf-core": found in modules/nf-core/ (shared community modules)
    - "local": found in modules/local/ (pipeline-specific modules)
    - "heuristic": no matching module file (fallback classification)
    """
    process_name = step_label.rsplit(":", 1)[-1].lower()
    if process_name in nfcore_map:
        return ("nf-core", nfcore_map[process_name])
    if process_name in local_map:
        return ("local", local_map[process_name])
    return ("heuristic", None)


_TOOL_ALIASES = {
    "gunzip_fasta": "gunzip",
    "unzip_fasta": "gunzip",
    "decompress": "gunzip",
    "convert_cram": "samtools.view",
    "custom_interleavefasta": "cat.fastq",
}

_TOOL_SUFFIXES = (
    "_normal",
    "_min",
    "_max",
    "_merge",
    "_sort",
    "_index",
    "_align",
    "_map",
    "_filter",
    "_split",
    "_extract",
    "_rename",
    "_replace",
    "_reformat",
)


def normalize_tool_name(name):
    """Syntactic normalization of tool names.

    Applies alias map, strips known path prefixes and suffixes,
    and converts uppercase names to lowercase.
    No model dependency — safe to call during graph building.
    """
    if not name:
        return name

    # Strip known prefixes from the original name (case-preserving),
    # so we can detect all-uppercase tool names behind path prefixes.
    # e.g. "modules/local/FOO" -> stripped_base = "FOO" -> is_all_upper
    stripped_base = name
    for prefix in ("custom_", "modules/local/", "local/"):
        if name.startswith(prefix):
            stripped_base = name[len(prefix) :]
            break

    is_all_upper = stripped_base.isupper()

    lower = name.lower().strip()

    # Strip known prefixes (on lowercased version)
    for prefix in ("custom_", "modules/local/", "local/"):
        if lower.startswith(prefix):
            lower = lower[len(prefix) :]
            break

    # Convert path separators to dots
    if "/" in lower:
        lower = lower.replace("/", ".")

    # Check alias map (exact match)
    if lower in _TOOL_ALIASES:
        return _TOOL_ALIASES[lower]

    # Strip known suffixes and check alias + return stem
    for suffix in _TOOL_SUFFIXES:
        if lower.endswith(suffix):
            stripped = lower[: -len(suffix)]
            if stripped in _TOOL_ALIASES:
                return _TOOL_ALIASES[stripped]
            if stripped:
                return stripped

    # All-uppercase names → lowercase (with or without underscores/dots)
    if is_all_upper:
        return lower.replace("_", ".")

    return name


def _resolve_app(step_label, origin=None, mod_path=None):
    """Resolve a DAG step label to a canonical tool name.

    Priority:
    1. mod_path (e.g. "samtools/sort") → dotted name (e.g. "samtools.sort")
    2. Normalized heuristic (aliases, suffixes, uppercase→dotted)
    3. Raw process name as-is (last resort)
    """
    if mod_path:
        return mod_path.replace("/", ".")
    process_name = step_label.rsplit(":", 1)[-1]
    return normalize_tool_name(process_name)


def dag_data_to_graph(
    dag,
    output_path,
    nfcore_map=None,
    local_map=None,
    extra_meta=None,
):
    """Convert an in-memory nf-core DAG dict to graph.json format.

    Args:
        nfcore_map: {process_name: module_path} from modules/nf-core/
        local_map:  {process_name: module_path} from modules/local/
    """
    from nfcore_toolkit.common import STATUS_KEYS

    pipeline = dag.get("pipeline", "unknown")
    steps = dag.get("steps", [])
    edges = dag.get("edges", [])

    nodes = []
    nfcore_map = nfcore_map or {}
    local_map = local_map or {}
    for step in steps:
        origin, mod_path = _classify_step(step, nfcore_map, local_map)
        app = _resolve_app(step, origin=origin, mod_path=mod_path)
        node = {
            "id": step,
            "app": app,
            "cmd_info": {"interpreter": None, "toolkit": None},
        }
        node["language_metadata"] = {"module_origin": origin}
        if mod_path:
            node["language_metadata"]["module_path"] = mod_path
        nodes.append(node)

    links = [{"source": e["source"], "target": e["target"]} for e in edges]

    graph_meta = {
        "id": pipeline,
        "name": pipeline,
        "workflow_language": "Nextflow",
    }
    for key in STATUS_KEYS:
        if key in dag:
            graph_meta[key] = dag[key]
    if extra_meta:
        graph_meta.update(extra_meta)

    graph = {
        "directed": True,
        "graph": graph_meta,
        "nodes": nodes,
        "links": links,
    }

    with open(output_path, "w") as f:
        json.dump(graph, f, indent=2)

    return output_path


def dag_to_graph(dag_path, output_path):
    with open(dag_path) as f:
        dag = json.load(f)
    return dag_data_to_graph(dag, output_path)
