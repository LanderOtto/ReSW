#!/usr/bin/env python3
"""Generate a markdown report of all multi-tool processes."""
import ast
import json
from pathlib import Path

NF_CACHE = Path(".nfcore_study_cache/nfcore_modules.txt")


def _load_nfcore_bases(repos):
    if NF_CACHE.exists():
        return {
            l.strip().lower() for l in NF_CACHE.read_text().splitlines() if l.strip()
        }
    bases = set()
    for r in repos:
        for e in r.get("nfcore_tool_evidence", []):
            if e[4] == "exact":
                bases.add(e[3].lower())
    return bases


def _parse_tool_list(raw):
    if isinstance(raw, list):
        return raw
    if isinstance(raw, str):
        return ast.literal_eval(raw)
    return []


def generate_report(
    json_path="nextflow_analysis.json", out_path="docs/multi_tool_processes.md"
):
    data = json.loads(Path(json_path).read_text())
    repos = data["module_analysis"]["repos"]
    nfcore_bases = _load_nfcore_bases(repos)

    rows = []

    for r in repos:
        pipe = r["full_name"]
        for e in r.get("nfcore_tool_evidence", []):
            if e[4] != "metric":
                continue
            comp = e[6]
            tools = _parse_tool_list(comp.get("tool_cmds", []))
            stripped = [t.split("/")[0].lower() for t in tools if t]
            n = len(stripped)
            if n <= 1:
                continue
            n_nf = sum(1 for t in stripped if t in nfcore_bases)
            n_custom = n - n_nf
            ratio = n_nf / n
            proc_file = e[0]
            proc_name = e[2].strip() if e[2] else proc_file
            rows.append(
                (n, n_nf, n_custom, ratio, pipe, proc_file, proc_name, stripped)
            )

    rows.sort(key=lambda x: (-x[0], -x[3]))

    md = [
        "# Multi-Tool Process Report",
        "",
        f"Generated from `{json_path}` — {len(rows)} multi-tool processes across {len(set(r[4] for r in rows))} pipelines.",
        "",
        "| #tools | #nf-core | #custom | nf-core ratio | Pipeline | Process file | Process name |",
        "|--------|----------|---------|---------------|----------|-------------|--------------|",
    ]

    for n, n_nf, n_cust, ratio, pipe, pfile, pname, _tools in rows:
        ratio_str = f"{ratio:.0%}" if ratio == int(ratio) else f"{ratio:.0%}"
        # Ensure ratio is displayed as percentage
        pct = f"{ratio:.0%}"
        md.append(f"| {n} | {n_nf} | {n_cust} | {pct} | {pipe} | {pfile} | {pname} |")

    md.append("")
    md.append("---")
    md.append("")
    md.append("## Pipeline summary")
    md.append("")
    md.append("| Pipeline | Multi-tool processes |")
    md.append("|----------|---------------------|")

    from collections import Counter

    pipe_counts = Counter(r[4] for r in rows)
    for pipe, cnt in pipe_counts.most_common():
        md.append(f"| {pipe} | {cnt} |")

    content = "\n".join(md) + "\n"
    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    Path(out_path).write_text(content)
    print(
        f"Report written to {out_path} ({len(rows)} rows, {len(pipe_counts)} pipelines)"
    )


if __name__ == "__main__":
    generate_report()
