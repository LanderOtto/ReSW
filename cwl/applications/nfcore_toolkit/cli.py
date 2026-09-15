import argparse
import json
import os
import subprocess
import sys
import urllib.error
import urllib.request
from datetime import datetime, timedelta

from nfcore_toolkit.api import extract_all_tools, fetch_pipelines
from nfcore_toolkit.collect import collect_results
from nfcore_toolkit.common import DEFAULT_TIMEOUT, safe_name
from nfcore_toolkit.dag import (
    extract_tools_from_steps,
    parse_dot_to_json,
    run_nextflow_preview,
)
from nfcore_toolkit.graph import dag_to_graph
from nfcore_toolkit.tools import analyze_tools, print_report


def _to_graph_dot(graph_data: dict) -> str:
    lines = ["digraph dag_graph {", "rankdir=LR;"]
    for n in graph_data.get("nodes", []):
        lines.append(f'  "{n["id"]}" [label="{n["app"]}",shape=box];')
    for e in graph_data.get("links", []):
        lines.append(f'  "{e["source"]}" -> "{e["target"]}";')
    lines.append("}")
    return "\n".join(lines)


def cmd_list(args):
    workflows = fetch_pipelines(args.filter, args.all, args.include_unreleased)
    enriched = extract_all_tools(workflows)

    if args.max is not None:
        enriched = enriched[: args.max]

    if args.select_out is not None:
        selected = enriched
        with open(args.select_out, "w") as f:
            for wf in selected:
                f.write(wf["full_name"] + "\n")

    if args.json:
        print(json.dumps(enriched, indent=2))
        return

    print(f"nf-core pipelines: {len(enriched)}")
    for wf in sorted(enriched, key=lambda x: x["full_name"]):
        arch = " [ARCHIVED]" if wf["archived"] else ""
        tools = ", ".join(wf["tools"][:8])
        more = f" … +{len(wf['tools']) - 8} more" if len(wf["tools"]) > 8 else ""
        print(f"  {wf['full_name']}{arch} ({wf['stars']}★)")
        print(f"    tools: {tools}{more}")


def cmd_dag(args):
    safe = safe_name(args.pipeline)
    out_dir = f"{safe}_dir"
    dot_path = "dag.dot"
    output_log = "nextflow_output.log"

    # Fetch pipeline info: from pre-fetched pipelines.json or API
    nxf_version = args.nextflow_version
    nxf_required = None
    extra_meta = {}

    wf = None
    if args.community:
        print(f"  Community pipeline mode: skipping nf-core API fetch", file=sys.stderr)
    elif args.pipelines_json:
        with open(args.pipelines_json) as f:
            pipelines_list = json.load(f)
        for entry in pipelines_list:
            if entry.get("full_name") == args.pipeline:
                wf = entry
                break
    else:
        from nfcore_toolkit.api import fetch_pipeline_info

        wf = fetch_pipeline_info(args.pipeline)

    extra_meta["archived"] = wf.get("archived", False) if wf else False
    extra_meta["latest_release"] = wf.get("latest_release", "") if wf else ""

    # Resolve NXF_VER: auto → pin from API constraint, or use explicit string
    if args.community:
        if nxf_version == "auto":
            nxf_version = "26.04.0"
            print(f"  Community mode: using NXF_VER={nxf_version}", file=sys.stderr)
    elif nxf_version == "auto":
        from nfcore_toolkit.utils_nextflow import resolve_nfx_version

        if wf:
            if args.pipelines_json:
                raw = (wf.get("nextflow_version", "") or "").strip()
            else:
                from nfcore_toolkit.api import extract_pipeline_tools

                info = extract_pipeline_tools(wf)
                raw = (info.get("nextflow_version", "") or "").strip()
            if raw.startswith("!") and not raw.startswith("!="):
                raw = raw[1:]
            nxf_required = raw.strip() or None
        nxf_version = resolve_nfx_version(nxf_required)
        if nxf_version:
            print(
                f"  Pinning NXF_VER={nxf_version}",
                file=sys.stderr,
            )

    # --syntax-parser auto: detect from the constraint's target version
    syntax_parser = None
    if args.syntax_parser == "auto":
        if nxf_required:
            import re

            from nfcore_toolkit.utils_nextflow import needs_groovy_parser

            m = re.search(r"(\d+\.\d+\.\d+)", nxf_required)
            if m and needs_groovy_parser(m.group(1)):
                syntax_parser = "v1"
                print(
                    f"  {args.pipeline} requires {nxf_required}, targeted NXF {m.group(1)}, using NXF_SYNTAX_PARSER=v1",
                    file=sys.stderr,
                )
    elif args.syntax_parser != "auto":
        syntax_parser = args.syntax_parser

    # java17_home: only from CLI arg, no auto-detection or fallback
    java_home = args.java17_home
    if java_home and java_home.endswith("/bin/java"):
        java_home = java_home[: -len("/bin/java")]

    revision = None
    from nfcore_toolkit.graph import resolve_clone_path

    clone = resolve_clone_path(args.pipeline)
    if clone:
        revision = clone.name
        print(f"  Using revision {revision}", file=sys.stderr)

    # Detect entry point for community pipelines (non-standard repo layout)
    main_script = None
    if args.community:
        from nfcore_toolkit.dag import detect_entry_point

        main_script = detect_entry_point(args.pipeline, clone_path=clone)
        if main_script:
            print(f"  Detected entry point: {main_script}", file=sys.stderr)
        else:
            print(f"  No entry point detected, using standard layout", file=sys.stderr)

    # --- First attempt with resolved nxf_version ---
    dot_path, status = run_nextflow_preview(
        args.pipeline,
        args.profile,
        "results",
        timeout=args.timeout,
        syntax_parser=syntax_parser,
        nextflow_version=nxf_version,
        nextflow_required=nxf_required,
        revision=revision,
        output_log=output_log,
        java_home=java_home,
        main_script=main_script,
    )

    dag_data = parse_dot_to_json(dot_path, status=status)

    if status:
        from nfcore_toolkit.common import STATUS_KEYS

        for key in STATUS_KEYS:
            if key in status:
                dag_data[key] = status[key]

    # --- Retry on DSL1 failure with NF 22.10.8 + Java 17 ---
    exit_code = dag_data.get("exit_code", 0)
    error_str = dag_data.get("error", "")
    final_log = output_log

    if exit_code != 0 and "DSL1 is no longer supported" in error_str:
        if java_home:
            print(
                f"  DSL1 detected for {args.pipeline}, retrying with NF 22.10.8 + JAVA_HOME={java_home}",
                file=sys.stderr,
            )
            retry_log = output_log.replace(".log", ".retry.log")
            dot_path, retry_status = run_nextflow_preview(
                args.pipeline,
                args.profile,
                "results",
                timeout=args.timeout,
                syntax_parser=None,
                nextflow_version="22.10.8",
                nextflow_required=nxf_required,
                revision=revision,
                output_log=retry_log,
                java_home=java_home,
            )
            dag_data = parse_dot_to_json(dot_path, status=retry_status)
            dag_data["retried"] = True
            if retry_status:
                from nfcore_toolkit.common import STATUS_KEYS

                for key in STATUS_KEYS:
                    if key in retry_status:
                        dag_data[key] = retry_status[key]
            final_log = retry_log
        else:
            dag_data["error"] = (
                "DSL1 pipeline requires rollback to NF 22.10.x "
                "but no --java17-home provided (impossible to rollback to nfx22)"
            )

    # If DAG still failed after retry, write error graph.json and return early
    if args.community and dag_data.get("error"):
        os.makedirs(out_dir, exist_ok=True)
        error_graph = {
            "directed": True,
            "graph": {"id": args.pipeline, "error": dag_data["error"]},
            "nodes": [],
            "links": [],
        }
        for key in (
            "exit_code",
            "nextflow_version_used",
            "syntax_parser",
            "pipeline_nfx_required",
            "output_log",
            "revision",
        ):
            if key in dag_data:
                error_graph["graph"][key] = dag_data[key]
        graph_json_path = f"{out_dir}/{safe}.graph.json"
        with open(graph_json_path, "w") as f:
            json.dump(error_graph, f, indent=2)
        print(f"  DAG extraction failed: {dag_data['error']}", file=sys.stderr)
        print(f"  Wrote error graph.json → {graph_json_path}", file=sys.stderr)
        return

    dag_data["pipeline"] = args.pipeline
    dag_data["tool_info"] = extract_tools_from_steps(dag_data["steps"])

    nfcore_path_map = {}
    local_path_map = {}
    from nfcore_toolkit.graph import build_module_maps

    nn, np, ln, lp = build_module_maps(args.pipeline)
    if nn:
        nfcore_path_map = np
        print(
            f"  Loaded {len(nn)} nf-core module/tool mappings for {args.pipeline}",
            file=sys.stderr,
        )
    if ln:
        local_path_map = lp
        print(
            f"  Loaded {len(ln)} local module/tool mappings for {args.pipeline}",
            file=sys.stderr,
        )

    os.makedirs(out_dir, exist_ok=True)

    # Run failure classification and remove redundant keys
    exit_code = dag_data.get("exit_code", 0)
    generate_png = bool(
        args.generate_png and exit_code == 0 and not dag_data.get("error")
    )
    if exit_code != 0 or dag_data.get("error"):
        from failure_classifier.classifier import classify

        result = classify(
            pipeline_dir=".",
            error_str=dag_data.get("error", ""),
            exit_code=exit_code,
            log_path=final_log,
            pipeline_name=args.pipeline,
        )
        extra_meta["failure_classification"] = result
        dag_data.pop("exit_code", None)
        dag_data.pop("error", None)

    graph_json_path = f"{out_dir}/{safe}.graph.json"
    from nfcore_toolkit.graph import dag_data_to_graph

    dag_data_to_graph(
        dag_data,
        graph_json_path,
        nfcore_map=nfcore_path_map,
        local_map=local_path_map,
        extra_meta=extra_meta,
    )

    if generate_png:
        subprocess.run(
            ["dot", "-Tpng", dot_path, "-o", f"{out_dir}/{safe}.dag.png"],
            check=True,
        )
        with open(graph_json_path) as f:
            gdata = json.load(f)
        gdot_path = f"{out_dir}/{safe}.dag.graph.dot"
        with open(gdot_path, "w") as f:
            f.write(_to_graph_dot(gdata))
        subprocess.run(
            ["dot", "-Tpng", gdot_path, "-o", f"{out_dir}/{safe}.graph.png"],
            check=True,
        )
        os.remove(gdot_path)


def cmd_list_community(args):
    query = "language:nextflow fork:false -user:nf-core" f" stars:>={args.min_stars}"
    url = (
        f"https://api.github.com/search/repositories?q={urllib.request.quote(query)}"
        f"&sort=stars&order=desc&per_page=100"
    )

    token = args.token or os.environ.get("GITHUB_TOKEN", "")
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "nfcore-toolkit",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"

    raw_repos = []
    for page in range(1, args.max_pages + 1):
        req = urllib.request.Request(f"{url}&page={page}", headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                items = json.loads(resp.read()).get("items", [])
                if not items:
                    break
                raw_repos.extend(items)
        except (urllib.error.URLError, urllib.error.HTTPError) as e:
            print(f"GitHub API error (page {page}): {e}", file=sys.stderr)
            break

    activity_threshold = datetime.now() - timedelta(days=args.activity_days)
    processed = []
    for item in raw_repos:
        pushed = item.get("pushed_at", "")
        try:
            pushed_date = datetime.strptime(pushed, "%Y-%m-%dT%H:%M:%SZ")
        except (ValueError, TypeError):
            continue
        if pushed_date >= activity_threshold:
            processed.append(
                {
                    "name": item["full_name"],
                    "stars": item["stargazers_count"],
                    "description": (item.get("description") or "")[:120],
                    "url": item["html_url"],
                    "last_commit": pushed,
                }
            )

    processed.sort(key=lambda x: -x["stars"])
    selected = processed[: args.top]

    if args.select_out is not None:
        with open(args.select_out, "w") as f:
            for repo in selected:
                f.write(repo["name"] + "\n")

    if args.json:
        print(json.dumps(selected, indent=2))
        return

    print(f"Community pipelines found: {len(processed)} (top {args.top} by stars):")
    for repo in selected:
        print(f"  {repo['name']:<40} ★ {repo['stars']:>4}  {repo['description']}")


def cmd_collect(args):
    result = collect_results(args.manifest)
    if args.summary_out:
        with open(args.summary_out, "w") as f:
            json.dump(result, f, indent=2)
    else:
        print(json.dumps(result, indent=2))


def cmd_merge_graphs(args):
    from nfcore_toolkit.merge import merge_graphs

    merge_graphs(args.input_dir, args.output)
    print(f"Wrote {args.output}  (merged {args.input_dir}/)", file=sys.stderr)


def cmd_graph(args):
    output = dag_to_graph(args.dag, args.output)
    print(f"Wrote {output}  (workflow_language=Nextflow)")


def cmd_tools(args):
    data = analyze_tools(args.filter, args.archived)
    if args.json:
        print(json.dumps(data, indent=2))
    else:
        print_report(data, top=args.top)


def cmd_analyze_patterns(args):
    from nfcore_toolkit.analyze import main

    main(args)


def main():
    parser = argparse.ArgumentParser(
        description="nf-core pipeline toolkit: list pipelines, convert DOT→DAG, collect results"
    )
    sub = parser.add_subparsers(dest="command", required=True)

    # --- list ---
    list_p = sub.add_parser("list", help="List all nf-core pipelines")
    list_p.add_argument("--json", action="store_true", help="JSON output")
    list_p.add_argument("--filter", help="Keyword filter")
    list_p.add_argument("--all", action="store_true", help="Include archived")
    list_p.add_argument(
        "--include-unreleased",
        action="store_true",
        help="Include unreleased pipelines (latest_release=='dev')",
    )
    list_p.add_argument("--max", type=int, default=None, help="Max pipelines to select")
    list_p.add_argument(
        "--select-out", help="Write selected pipeline names to file (one per line)"
    )
    list_p.set_defaults(func=cmd_list)

    # --- list-community ---
    lc_p = sub.add_parser(
        "list-community",
        help="List top community Nextflow pipelines from GitHub (non-nf-core)",
    )
    lc_p.add_argument("--json", action="store_true", help="JSON output")
    lc_p.add_argument(
        "--top",
        type=int,
        default=15,
        help="Number of top repos to return (default: 15)",
    )
    lc_p.add_argument(
        "--min-stars", type=int, default=5, help="Minimum stars filter (default: 5)"
    )
    lc_p.add_argument(
        "--activity-days",
        type=int,
        default=540,
        help="Max days since last commit (default: 540)",
    )
    lc_p.add_argument(
        "--max-pages",
        type=int,
        default=2,
        help="Max GitHub API pages to fetch (default: 2, per_page=100)",
    )
    lc_p.add_argument(
        "--token",
        default=None,
        help="GitHub API token (default: $GITHUB_TOKEN env var)",
    )
    lc_p.add_argument(
        "--select-out", help="Write selected pipeline names to file (one per line)"
    )
    lc_p.set_defaults(func=cmd_list_community)

    # --- dag ---
    dag_p = sub.add_parser(
        "dag", help="Run nextflow preview and convert DOT to DAG JSON + graph JSON"
    )
    dag_p.add_argument(
        "--pipeline",
        required=True,
        help="Pipeline name (output filenames derived from it)",
    )
    dag_p.add_argument(
        "--profile", default="test", help="Nextflow profile (default: test)"
    )
    dag_p.add_argument(
        "--timeout",
        type=int,
        default=DEFAULT_TIMEOUT,
        help=f"Timeout seconds for nextflow run (default: {DEFAULT_TIMEOUT})",
    )
    dag_p.add_argument(
        "--syntax-parser",
        default="auto",
        choices=["auto", "v1", "v2"],
        help="NXF_SYNTAX_PARSER value (default: auto — don't set, let version decide)",
    )
    dag_p.add_argument(
        "--nextflow-version",
        default="auto",
        help="NXF_VER value (default: auto — resolve from API + hardcoded version list)",
    )
    dag_p.add_argument(
        "--java17-home",
        default=None,
        help="JAVA_HOME for Java 17 (required for DSL1 rollback with NF 22.10.x)",
    )
    dag_p.add_argument(
        "--generate-png",
        action="store_true",
        help="Generate {safe}.png + {safe}_dir/ with PNGs",
    )
    dag_p.add_argument(
        "--pipelines-json",
        default=None,
        help="Pre-fetched pipelines.json (skip API call for metadata)",
    )
    dag_p.add_argument(
        "--community",
        action="store_true",
        help="Community pipeline mode: skip nf-core API/module dependency resolution",
    )
    dag_p.set_defaults(func=cmd_dag)

    # --- graph ---
    graph_p = sub.add_parser(
        "graph",
        help="Convert nf-core DAG JSON to graph.json (pattern_aggregator format)",
    )
    graph_p.add_argument("--dag", required=True, help="Input nf-core DAG JSON file")
    graph_p.add_argument("--output", required=True, help="Output .graph.json path")
    graph_p.set_defaults(func=cmd_graph)

    # --- tools ---
    tools_p = sub.add_parser(
        "tools", help="Analyze tool usage across nf-core pipelines"
    )
    tools_p.add_argument("--json", action="store_true", help="JSON output")
    tools_p.add_argument("--filter", help="Keyword filter")
    tools_p.add_argument(
        "--archived", action="store_true", help="Include archived pipelines"
    )
    tools_p.add_argument(
        "--top", type=int, default=30, help="Number of top tools to show (default: 30)"
    )
    tools_p.set_defaults(func=cmd_tools)

    # --- collect ---
    col_p = sub.add_parser("collect", help="Collect DAG results into summary JSON")
    col_p.add_argument(
        "manifest", help="Path to manifest.json with embedded graph objects"
    )
    col_p.add_argument(
        "--summary-out", help="Summary JSON output path (omit to print to stdout)"
    )
    col_p.set_defaults(func=cmd_collect)

    # --- merge-graphs ---
    mg_p = sub.add_parser(
        "merge-graphs", help="Merge .graph.json files into a single manifest.json"
    )
    mg_p.add_argument("--input-dir", required=True, help="Directory with .json files")
    mg_p.add_argument("--output", default="manifest.json", help="Output path")
    mg_p.set_defaults(func=cmd_merge_graphs)

    # --- analyze-patterns ---
    ap_p = sub.add_parser(
        "analyze-patterns",
        help="Cross-pipeline pattern analysis (co-occurrence, topology, domains)",
    )
    ap_p.add_argument(
        "--input-dir", required=True, help="Directory with graph.json files"
    )
    ap_p.add_argument(
        "--patterns-dag",
        required=True,
        help="patterns_dag.json from pattern_aggregator",
    )
    ap_p.add_argument(
        "--output", default=None, help="Write report to file (default: stdout)"
    )
    ap_p.add_argument(
        "--plot-dir",
        default=None,
        help="Generate plots in this directory (requires matplotlib + seaborn)",
    )
    ap_p.add_argument(
        "--cores",
        type=int,
        default=1,
        help="Number of parallel worker processes for plot generation (default: 1)",
    )
    ap_p.add_argument(
        "--font-path",
        type=str,
        default=None,
        help="Path to the font file (.ttf) to customize the plot fonts",
    )
    ap_p.set_defaults(func=cmd_analyze_patterns)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
