def query_app(patterns, current_app, top=5):
    wf_count = patterns.get("wf_count", {})
    transition_count = patterns.get("transition_count", {})

    if current_app not in wf_count:
        available = sorted(wf_count.keys())
        return (
            f"'{current_app}' not found in patterns.\n"
            f"Available apps ({len(available)}): "
            + ", ".join(available[:20])
            + ("..." if len(available) > 20 else "")
        )

    src_count = wf_count[current_app]["count"]
    edges = transition_count.get(current_app, {})
    if not edges:
        return (
            f"after {current_app} ({src_count} workflow{'s' if src_count != 1 else ''}):\n"
            "  (no transitions recorded)"
        )

    sorted_edges = sorted(edges.items(), key=lambda x: -len(x[1]["workflows"]))

    lines = [
        f"after {current_app} ({src_count} workflow{'s' if src_count != 1 else ''}):\n"
    ]
    for app, info in sorted_edges[:top]:
        wf_count_transition = len(info["workflows"])
        pct = (wf_count_transition / src_count) * 100
        lines.append(
            f"  {app:<25} {pct:>5.0f}%  ({info['count']} edge{'s' if info['count'] != 1 else ''}, "
            f"{wf_count_transition} workflow{'s' if wf_count_transition != 1 else ''})"
        )

    return "\n".join(lines)
