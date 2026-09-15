"""DOT to JSON DAG conversion and tool extraction."""

import json
import os
import re
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

from nfcore_toolkit.common import safe_name

NXF_RUN_TIMEOUT = 300


def _github_headers():
    token = os.environ.get("GITHUB_TOKEN", "")
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "nfcore-toolkit",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


ENTRY_POINT_CANDIDATES = [
    "workflows/main.nf",
    "workflow/main.nf",
    "pipeline.nf",
    "workflow.nf",
]


def detect_entry_point(pipeline, clone_path=None):
    """Probe for the pipeline's entry point.

    When ``clone_path`` is provided, uses the local filesystem (no API calls).
    Otherwise falls back to the GitHub Contents API.

    Returns the path (e.g. ``workflows/main.nf``) relative to repo root,
    or ``None`` if ``main.nf`` at root (standard layout).
    """
    if "/" not in pipeline:
        return None
    owner, repo = pipeline.split("/", 1)
    repo = repo.split("#")[0]

    if clone_path:
        return _detect_entry_point_local(Path(clone_path))

    return _detect_entry_point_api(owner, repo)


def _detect_entry_point_local(clone_path):
    """Use local filesystem to detect entry point."""

    # 1. Root nextflow.config with manifest.mainScript → authoritative
    root_config = clone_path / "nextflow.config"
    if root_config.is_file():
        text = root_config.read_text()
        m = re.search(
            r"manifest\s*\{[^}]*mainScript\s*=\s*['\"]([^'\"]+)['\"]",
            text,
        )
        if m:
            return m.group(1)

    # 2. Any nextflow.config in the repo (recursive) with manifest.mainScript
    for config in clone_path.rglob("nextflow.config"):
        if config == root_config:
            continue
        text = config.read_text()
        m = re.search(
            r"manifest\s*\{[^}]*mainScript\s*=\s*['\"]([^'\"]+)['\"]",
            text,
        )
        if m:
            return m.group(1)

    # 3. Any nextflow.config exists (without manifest.mainScript) → trust config
    if root_config.is_file():
        return None
    if list(clone_path.rglob("nextflow.config")):
        return None

    # 4. main.nf at root → standard
    if (clone_path / "main.nf").is_file():
        return None

    # 5. Probe common candidates
    for candidate in ENTRY_POINT_CANDIDATES:
        if (clone_path / candidate).is_file():
            return candidate

    # 6. Single .nf at root
    nf_files = list(clone_path.glob("*.nf"))
    if len(nf_files) == 1:
        return nf_files[0].name

    return None


def _detect_entry_point_api(owner, repo):
    """Use GitHub Contents API to detect entry point (no local clone available)."""
    import base64

    base_url = f"https://api.github.com/repos/{owner}/{repo}"
    headers = _github_headers()
    req = urllib.request.Request(f"{base_url}/contents/", headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            items = json.loads(resp.read())
    except (urllib.error.URLError, urllib.error.HTTPError) as e:
        print(f"  detect_entry_point: cannot list repo root ({e})", file=sys.stderr)
        return None

    root_names = {item.get("name") for item in items if isinstance(item, dict)}

    # main.nf at root → standard
    if "main.nf" in root_names:
        return None

    # nextflow.config → parse manifest.mainScript
    manifest_script = None
    if "nextflow.config" in root_names:
        try:
            req = urllib.request.Request(
                f"{base_url}/contents/nextflow.config", headers=headers
            )
            with urllib.request.urlopen(req, timeout=15) as resp:
                data = json.loads(resp.read())
            raw = base64.b64decode(data["content"]).decode()
            m = re.search(
                r"manifest\s*\{[^}]*mainScript\s*=\s*['\"]([^'\"]+)['\"]",
                raw,
            )
            if m:
                manifest_script = m.group(1)
        except (urllib.error.URLError, urllib.error.HTTPError):
            pass

    if manifest_script:
        return manifest_script

    if "nextflow.config" in root_names:
        return None

    for candidate in ENTRY_POINT_CANDIDATES:
        try:
            req = urllib.request.Request(
                f"{base_url}/contents/{candidate}", headers=headers
            )
            with urllib.request.urlopen(req, timeout=15):
                return candidate
        except urllib.error.HTTPError:
            continue
        except urllib.error.URLError:
            continue

    nf_files = [n for n in root_names if n.endswith(".nf")]
    if len(nf_files) == 1:
        return nf_files[0]

    return None


def _exec_nextflow(cmd, timeout=None, env=None):
    proc_env = os.environ.copy()
    if env:
        proc_env.update(env)
    try:
        print(
            f"Executing command {' '.join(cmd)} (timeout {timeout})",
            file=sys.stderr,
        )
        output = subprocess.check_output(
            cmd, stderr=subprocess.STDOUT, text=True, timeout=timeout, env=proc_env
        )
        return output, 0
    except subprocess.TimeoutExpired as e:
        partial = e.output.decode() if isinstance(e.output, bytes) else (e.output or "")
        partial += f"Timeout {timeout} seconds"
        return partial, -1
    except subprocess.CalledProcessError as e:
        return e.output, e.returncode


def run_nextflow_preview(
    pipeline,
    profile,
    outdir,
    timeout=NXF_RUN_TIMEOUT,
    syntax_parser=None,
    nextflow_version=None,
    nextflow_required=None,
    revision=None,
    output_log=None,
    java_home=None,
    main_script=None,
):
    dot_path = "dag.dot"
    log_path = output_log or "nextflow_output.log"

    # Pre-flight: check if NF version supports -preview before launching
    from nfcore_toolkit.utils_nextflow import get_system_nfx_version, supports_preview

    check_version = nextflow_version or get_system_nfx_version()
    if check_version and not supports_preview(check_version):
        status = {
            "pipeline": pipeline,
            "exit_code": 1,
            "error": f"Nextflow {check_version} too old for -preview (need >= 22.04.0)",
        }
        return dot_path, status

    # Pre-flight: check if NF version needs Java <= 17
    from nfcore_toolkit.utils_nextflow import needs_java17

    check_version = nextflow_version or get_system_nfx_version()
    if check_version and needs_java17(check_version):
        if java_home:
            print(
                f"  {pipeline} requires NF {check_version} (Java ≤ 17), setting JAVA_HOME={java_home}",
                file=sys.stderr,
            )
        else:
            print(
                f"  WARNING: {pipeline} requires NF {check_version} (Java ≤ 17) but no --java-home provided",
                file=sys.stderr,
            )

    nxf_env = {}
    if syntax_parser:
        nxf_env["NXF_SYNTAX_PARSER"] = syntax_parser
    if nextflow_version:
        nxf_env["NXF_VER"] = nextflow_version
    if java_home and check_version and needs_java17(check_version):
        nxf_env["JAVA_HOME"] = java_home

    pull_cmd = ["nextflow", "pull", pipeline]
    run_cmd = [
        "nextflow",
        "run",
        pipeline,
        "-profile",
        profile,
        "-preview",
        "-with-dag",
        dot_path,
        "--outdir",
        outdir,
    ]
    if main_script:
        run_cmd.insert(run_cmd.index("-profile"), "-main-script")
        run_cmd.insert(run_cmd.index("-profile"), main_script)
    if revision:
        pull_cmd.extend(["-r", revision])
        run_cmd.insert(run_cmd.index("-profile"), "-r")
        run_cmd.insert(run_cmd.index("-profile"), revision)

    _exec_nextflow(pull_cmd, timeout=timeout, env=nxf_env)
    output, rc = _exec_nextflow(run_cmd, timeout=timeout, env=nxf_env)

    with open(log_path, "w") as f:
        f.write(output)

    err_msg = None
    dag_ok = os.path.exists(dot_path) and os.path.getsize(dot_path) > 0
    if not dag_ok:
        lines = [line for line in output.splitlines() if line.strip()]
        error_lines = [
            line for line in lines if "[ERROR]" in line or "ERROR" in line.upper()
        ]
        picked = error_lines[-1] if error_lines else (lines[-1] if lines else "")
        err_msg = picked or "dag.dot not generated"

    status = {"pipeline": pipeline, "exit_code": rc}
    if err_msg:
        status["error"] = err_msg
        status["output_log"] = os.path.abspath(log_path)
    if nextflow_version:
        status["nextflow_version_used"] = nextflow_version
    if nextflow_required:
        status["pipeline_nfx_required"] = nextflow_required
    if syntax_parser:
        status["syntax_parser"] = syntax_parser
    if revision:
        status["revision"] = revision
    return dot_path, status


def run_nextflow_previews(pipelines, profile, outdir, timeout=NXF_RUN_TIMEOUT):
    """Run nextflow preview sequentially for a list of pipelines.

    Each pipeline's outputs are written to uniquely named files
    (dag_<safe>.json, dag_<safe>.dot) to avoid collisions.

    Returns a list of (dag_json_path, status_dict) tuples.
    """
    results = []
    for i, pipeline in enumerate(pipelines):
        safe = safe_name(pipeline)
        dag_json_path = f"dag_{safe}.json"

        if i > 0:
            time.sleep(10)  # small inter-pipeline gap

        dag_path, status = run_nextflow_preview(
            pipeline, profile, outdir, timeout=timeout
        )

        if os.path.exists(dag_path):
            os.rename(dag_path, f"dag_{safe}.dot")

        # Parse DOT to JSON and write pipeline-specific JSON
        dag_data = parse_dot_to_json(f"dag_{safe}.dot", status=status)
        if status:
            from nfcore_toolkit.common import STATUS_KEYS

            for key in STATUS_KEYS:
                if key in status:
                    dag_data[key] = status[key]
        dag_data["pipeline"] = pipeline
        with open(dag_json_path, "w") as f:
            json.dump(dag_data, f, indent=2)

        results.append((dag_json_path, status))

    return results


def parse_dot_to_json(dot_path, status=None):
    try:
        content = Path(dot_path).read_text()
    except FileNotFoundError:
        msg = (
            status.get("error", "DOT file not found")
            if status
            else f"DOT file not found: {dot_path}"
        )
        return {
            "error": msg,
            "steps": [],
            "edges": [],
            "total_processes": 0,
            "total_edges": 0,
        }

    # Parse labeled process nodes and all raw edges
    label_map = {}  # v_id -> process label
    raw_edges = []  # (src_vid, dst_vid, channel)

    for line in content.splitlines():
        m = re.match(r"\s*[pv](\d+)\s+\[.*?\]\s*;", line)
        if m:
            vid = m.group(1)
            lbl = re.search(r'\blabel\s*=\s*"([^"]*)"', line)
            if lbl and lbl.group(1) and lbl.group(1) != "dag":
                label_map[vid] = lbl.group(1)

    for line in content.splitlines():
        m = re.match(r"\s*[pv](\d+)\s+->\s+[pv](\d+)\s*(?:\[.*?\]\s*)?;", line)
        if m:
            ch = ""
            ch_m = re.search(r'\blabel\s*=\s*"([^"]*)"', line)
            if ch_m:
                ch = ch_m.group(1)
            raw_edges.append((m.group(1), m.group(2), ch))

    if not label_map:
        msg = (
            status.get(
                "error",
                "nextflow preview failed — empty workflow (no processes in DAG)",
            )
            if status
            else "No process nodes found in DOT file"
        )
        return {
            "error": msg,
            "steps": [],
            "edges": [],
            "total_processes": 0,
            "total_edges": 0,
        }

    process_ids = set(label_map.keys())
    v_ids = set()
    for src, dst, _ in raw_edges:
        v_ids.add(src)
        v_ids.add(dst)
    unlabeled = v_ids - process_ids

    # Build adjacency from unlabeled v nodes
    adj = {}
    for src, dst, _ in raw_edges:
        adj.setdefault(src, []).append(dst)

    def reachable_processes(start):
        """BFS through unlabeled v nodes from *start* to all reachable process nodes."""
        seen = {start}
        queue = list(adj.get(start, []))
        results = []
        while queue:
            node = queue.pop(0)
            if node in seen:
                continue
            seen.add(node)
            if node in process_ids:
                results.append(node)
            elif node in unlabeled:
                for nxt in adj.get(node, []):
                    if nxt not in seen:
                        queue.append(nxt)
        return results

    # Build direct process->process edges by resolving through unlabeled v nodes
    resolved_edges = []
    seen_edges = set()
    for pid in process_ids:
        for target_pid in reachable_processes(pid):
            key = (pid, target_pid)
            if key not in seen_edges:
                seen_edges.add(key)
                resolved_edges.append(
                    {
                        "source": label_map[pid],
                        "target": label_map[target_pid],
                        "channel": "",
                    }
                )

    step_names = sorted(set(label_map.values()))

    return {
        "processes": sorted(
            ({"id": vid, "label": label} for vid, label in label_map.items()),
            key=lambda x: int(x["id"]),
        ),
        "steps": step_names,
        "edges": resolved_edges,
        "total_processes": len(label_map),
        "total_edges": len(resolved_edges),
    }


def extract_tools_from_steps(steps):
    tools = {}
    for step in steps:
        parts = step.split(":")
        last = parts[-1]
        tname = last.rsplit("_", 1)[0] if "_" in last else last
        if tname not in tools:
            tools[tname] = []
        tools[tname].append(step)
    return {name: {"instances": sorted(steps)} for name, steps in tools.items()}


def load_status(path):
    try:
        with open(path) as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return None
