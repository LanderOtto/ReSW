"""Tool-usage analysis across nf-core pipelines.

Fetches all pipelines from the nf-core API, extracts tools per pipeline,
and produces frequency tables + statistics.
"""

from nfcore_toolkit.api import extract_all_tools, fetch_pipelines


def analyze_tools(filter_keyword=None, include_archived=False):
    workflows = fetch_pipelines(filter_keyword, include_archived)
    enriched = extract_all_tools(workflows)

    total = len(enriched)

    # tool -> {count, pipelines}
    tool_usage = {}
    for wf in enriched:
        for tool in wf["tools"]:
            entry = tool_usage.setdefault(tool, {"count": 0, "pipelines": []})
            entry["count"] += 1
            entry["pipelines"].append(wf["full_name"])

    # per-pipeline tool counts
    pipeline_tool_counts = sorted(
        (
            {
                "pipeline": wf["full_name"],
                "tool_count": len(wf["tools"]),
                "stars": wf["stars"],
                "archived": wf["archived"],
            }
            for wf in enriched
        ),
        key=lambda x: x["tool_count"],
        reverse=True,
    )

    tool_counts = [len(wf["tools"]) for wf in enriched]
    usage_counts = [v["count"] for v in tool_usage.values()]

    stats = {
        "total_pipelines": total,
        "total_unique_tools": len(tool_usage),
        "mean_tools_per_pipeline": round(sum(tool_counts) / total, 1) if total else 0,
        "median_tools_per_pipeline": _median(tool_counts),
        "min_tools": min(tool_counts) if tool_counts else 0,
        "max_tools": max(tool_counts) if tool_counts else 0,
        "tools_used_by_single_pipeline": sum(1 for c in usage_counts if c == 1),
        "tools_used_by_all_pipelines": sum(1 for c in usage_counts if c == total),
    }

    return {
        "stats": stats,
        "tool_usage": dict(sorted(tool_usage.items(), key=lambda x: -x[1]["count"])),
        "pipeline_tool_counts": pipeline_tool_counts,
    }


def print_report(data, top=30):
    stats = data["stats"]
    print(f"nf-core tool usage analysis  ({stats['total_pipelines']} pipelines)")
    print(f"  Unique tools:       {stats['total_unique_tools']}")
    print(f"  Mean tools/pipeline: {stats['mean_tools_per_pipeline']}")
    print(f"  Median:             {stats['median_tools_per_pipeline']}")
    print(f"  Range:              {stats['min_tools']} – {stats['max_tools']}")
    print(
        f"  Singletons:         {stats['tools_used_by_single_pipeline']} tools used by only 1 pipeline"
    )
    print(
        f"  Ubiquitous:         {stats['tools_used_by_all_pipelines']} tools used by ALL pipelines"
    )
    print()

    print(f"Top {top} most common tools:")
    print(f"  {'Tool':<30} {'Pipelines':>9} {'%':>5}")
    print("  " + "-" * 46)
    for tool, info in list(data["tool_usage"].items())[:top]:
        pct = info["count"] / stats["total_pipelines"] * 100
        print(f"  {tool:<30} {info['count']:>9} {pct:>4.0f}%")

    print()
    print("Pipelines by tool count (top 10):")
    for p in data["pipeline_tool_counts"][:10]:
        arch = " [archived]" if p["archived"] else ""
        print(f"  {p['tool_count']:>3} tools  {p['pipeline']}{arch} ({p['stars']}★)")


def _median(sorted_vals):
    vals = sorted(sorted_vals)
    n = len(vals)
    if n == 0:
        return 0
    if n % 2 == 1:
        return vals[n // 2]
    return (vals[n // 2 - 1] + vals[n // 2]) / 2
