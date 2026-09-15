from ..core import module_origin_summary, self_loop_origin_analysis, tool_origin_mixed
from .common import _init_mpl


def _plot_module_origin(graphs, plot_dir):
    import os

    mod_dir = os.path.join(plot_dir, "module_origin")

    plt = _init_mpl()
    import numpy as np

    _, mo_totals, pipeline_origins = module_origin_summary(graphs)
    if not pipeline_origins:
        return

    pipelines = sorted(pipeline_origins.keys())
    names = [p.split("/")[-1] for p in pipelines]
    origins = ["nf-core", "local", "heuristic", "unknown"]
    colors = {
        "nf-core": "#2ecc71",
        "local": "#3498db",
        "heuristic": "#e67e22",
        "unknown": "#95a5a6",
    }
    bottom = np.zeros(len(pipelines))
    fig, ax = plt.subplots(figsize=(max(12, len(pipelines) * 0.2), 7))
    for origin in origins:
        vals = np.array([pipeline_origins[p].get(origin, 0) for p in pipelines])
        if vals.sum() > 0:
            ax.bar(
                range(len(pipelines)),
                vals,
                bottom=bottom,
                color=colors[origin],
                label=origin,
                edgecolor="white",
                linewidth=0.3,
            )
            bottom += vals
    ax.set_xticks(range(len(pipelines)))
    ax.set_xticklabels(names, rotation=90, fontsize=6)
    ax.set_ylabel("Unique tools")
    ax.set_title("Module origin per pipeline")
    ax.legend(title="Origin", loc="upper right")
    total = sum(mo_totals.values())
    summary = "  ".join(
        f"{k}={v} ({100 * v // total}%)" for k, v in sorted(mo_totals.items())
    )
    ax.text(
        0.02,
        0.98,
        summary,
        transform=ax.transAxes,
        ha="left",
        va="top",
        fontsize=8,
        bbox=dict(boxstyle="round", facecolor="white", alpha=0.7),
    )
    plt.tight_layout()
    fig.savefig(os.path.join(mod_dir, "pipeline_origin.png"), dpi=150)
    plt.close(fig)


def _plot_module_origin_norm(graphs, plot_dir):
    import os

    mod_dir = os.path.join(plot_dir, "module_origin")

    plt = _init_mpl()
    import numpy as np

    _, _, pipeline_origins = module_origin_summary(graphs)
    if not pipeline_origins:
        return

    pipelines = sorted(pipeline_origins.keys())
    names = [p.split("/")[-1] for p in pipelines]
    origins = ["nf-core", "local", "heuristic", "unknown"]
    colors = {
        "nf-core": "#2ecc71",
        "local": "#3498db",
        "heuristic": "#e67e22",
        "unknown": "#95a5a6",
    }
    bottom = np.zeros(len(pipelines))
    fig, ax = plt.subplots(figsize=(max(12, len(pipelines) * 0.2), 7))
    for origin in origins:
        vals = np.array([pipeline_origins[p].get(origin, 0) for p in pipelines])
        totals = np.array([sum(pipeline_origins[p].values()) for p in pipelines])
        pcts = np.divide(vals, totals, where=(totals > 0)) * 100
        if pcts.sum() > 0:
            ax.bar(
                range(len(pipelines)),
                pcts,
                bottom=bottom,
                color=colors[origin],
                label=origin,
                edgecolor="white",
                linewidth=0.3,
            )
            bottom += pcts
    ax.set_xticks(range(len(pipelines)))
    ax.set_xticklabels(names, rotation=90, fontsize=6)
    ax.set_ylabel("% of pipeline tools")
    ax.set_title("Module origin per pipeline (normalized)")
    ax.legend(title="Origin", loc="upper right")
    ax.set_ylim(0, 100)
    plt.tight_layout()
    fig.savefig(os.path.join(mod_dir, "pipeline_origin_norm.png"), dpi=150)
    plt.close(fig)


def _plot_module_origin_aggregate(graphs, plot_dir):
    import os

    mod_dir = os.path.join(plot_dir, "module_origin")

    plt = _init_mpl()
    import numpy as np

    _, mo_totals, pipeline_origins = module_origin_summary(graphs)
    if not pipeline_origins:
        return

    origins = ["nf-core", "local", "heuristic", "unknown"]
    colors = {
        "nf-core": "#2ecc71",
        "local": "#3498db",
        "heuristic": "#e67e22",
        "unknown": "#95a5a6",
    }

    # Aggregate absolute counts across all pipelines
    abs_vals = np.array([mo_totals.get(o, 0) for o in origins])
    pct_vals = abs_vals / abs_vals.sum() * 100 if abs_vals.sum() > 0 else abs_vals

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(10, 5))

    # Left: absolute stacked bar
    bottom_abs = 0
    for i, origin in enumerate(origins):
        v = abs_vals[i]
        if v > 0:
            ax1.bar(
                0,
                v,
                bottom=bottom_abs,
                color=colors[origin],
                label=origin,
                edgecolor="white",
                linewidth=0.5,
            )
            ax1.text(
                0,
                bottom_abs + v / 2,
                str(int(v)),
                ha="center",
                va="center",
                fontsize=10,
                fontweight="bold",
            )
            bottom_abs += v
    ax1.set_xticks([])
    ax1.set_ylabel("Unique tools")
    ax1.set_title("Aggregate (absolute)")
    ax1.legend(title="Origin", loc="upper right")

    # Right: normalized stacked bar
    bottom_pct = 0
    for i, origin in enumerate(origins):
        v = pct_vals[i]
        if v > 0:
            ax2.bar(
                0,
                v,
                bottom=bottom_pct,
                color=colors[origin],
                label=origin,
                edgecolor="white",
                linewidth=0.5,
            )
            ax2.text(
                0,
                bottom_pct + v / 2,
                f"{v:.0f}%",
                ha="center",
                va="center",
                fontsize=10,
                fontweight="bold",
            )
            bottom_pct += v
    ax2.set_xticks([])
    ax2.set_ylabel("% of tools")
    ax2.set_title("Aggregate (normalized)")
    ax2.set_ylim(0, 100)

    plt.tight_layout()
    fig.savefig(os.path.join(mod_dir, "origin_aggregate.png"), dpi=150)
    plt.close(fig)


def _plot_tool_origin_mixed(graphs, plot_dir):
    import os

    mod_dir = os.path.join(plot_dir, "module_origin")

    plt = _init_mpl()
    import numpy as np

    mixed = tool_origin_mixed(graphs)
    if not mixed["tools"]:
        return

    tools_data = sorted(
        mixed["tools"].items(),
        key=lambda x: -sum(len(ps) for ps in x[1].values()),
    )

    colors = {
        "nf-core": "#2ecc71",
        "local": "#3498db",
        "heuristic": "#e67e22",
        "unknown": "#95a5a6",
    }
    origins_order = ["nf-core", "local", "heuristic", "unknown"]

    fig, ax = plt.subplots(figsize=(10, max(4, len(tools_data) * 0.4)))
    y_pos = np.arange(len(tools_data))

    for i, (app, origins) in enumerate(tools_data):
        left = 0
        for origin in origins_order:
            if origin in origins:
                val = len(origins[origin])
                ax.barh(
                    i,
                    val,
                    left=left,
                    color=colors[origin],
                    label=origin if i == 0 else "",
                    edgecolor="white",
                    linewidth=0.3,
                )
                left += val

    ax.set_yticks(y_pos)
    ax.set_yticklabels([app for app, _ in tools_data], fontsize=8)
    ax.set_xlabel("Pipeline count")
    ax.set_title("Tools with mixed module origins")
    ax.legend(title="Origin", loc="lower right")
    plt.tight_layout()
    fig.savefig(os.path.join(mod_dir, "tool_origin_mixed.png"), dpi=150)
    plt.close(fig)


def _plot_origin_set_distribution(graphs, plot_dir):
    import os

    mod_dir = os.path.join(plot_dir, "module_origin")

    plt = _init_mpl()
    import numpy as np
    from matplotlib.patches import Patch

    mixed = tool_origin_mixed(graphs)
    all_subsets = mixed["all_subsets"]
    if not all_subsets:
        return

    n_total = mixed["summary"]["total_tools"]
    size_colors = {1: "#3498db", 2: "#2ecc71", 3: "#e67e22", 4: "#e74c3c"}
    size_labels = {1: "1 origin", 2: "2 origins", 3: "3 origins", 4: "4 origins"}

    labels = [s[0].replace("+", " + ") for s in all_subsets]
    counts = [s[1] for s in all_subsets]

    fig, ax = plt.subplots(figsize=(10, max(4, len(labels) * 0.35)))
    y_pos = np.arange(len(labels))

    # Draw separator lines between size groups
    prev_size = None
    for i, (key, cnt) in enumerate(all_subsets):
        size = len(key.split("+"))
        if prev_size is not None and size != prev_size:
            ax.axhline(i - 0.5, color="#cccccc", linewidth=1)
        prev_size = size

    bars = []
    for i, (key, cnt) in enumerate(all_subsets):
        size = len(key.split("+"))
        bar = ax.barh(
            i,
            cnt,
            color=size_colors[size],
            edgecolor="white",
            linewidth=0.5,
            label=(
                size_labels[size] if size not in [b.get_label() for b in bars] else ""
            ),
        )
        bars.append(bar)
        pct = 100 * cnt / n_total if n_total else 0
        ax.text(cnt + 0.3, i, f"{cnt} ({pct:.0f}%)", va="center", fontsize=8)

    legend_handles = [
        Patch(facecolor=size_colors[s], label=size_labels[s])
        for s in sorted(size_colors)
    ]
    ax.legend(handles=legend_handles, title="Set size", loc="lower right")

    ax.set_yticks(y_pos)
    ax.set_yticklabels(labels, fontsize=8)
    ax.set_xlabel("Tool count")
    ax.set_title("Origin-set distribution")
    ax.margins(x=0.3)
    plt.tight_layout()
    fig.savefig(os.path.join(mod_dir, "tool_origin_sets.png"), dpi=150)
    plt.close(fig)


def _plot_self_loop_origin(transitions, graphs, plot_dir):
    import os

    mod_dir = os.path.join(plot_dir, "module_origin")

    plt = _init_mpl()
    import numpy as np

    slo = self_loop_origin_analysis(transitions, graphs)
    if not slo:
        return

    colors = {
        "nf-core": "#2ecc71",
        "local": "#3498db",
        "heuristic": "#e67e22",
        "unknown": "#95a5a6",
    }
    origins_order = ["nf-core", "local", "heuristic", "unknown"]

    fig, ax = plt.subplots(figsize=(10, max(4, len(slo) * 0.4)))
    y_pos = np.arange(len(slo))

    used_origins = set()
    for i, e in enumerate(slo):
        left = 0
        for origin in origins_order:
            if origin in e["origins"]:
                val = len(e["origins"][origin])
                ax.barh(
                    i,
                    val,
                    left=left,
                    color=colors[origin],
                    label=origin if origin not in used_origins else "",
                    edgecolor="white",
                    linewidth=0.3,
                )
                used_origins.add(origin)
                left += val
        tag = "\u2713" if e["known_subtool"] else "\u2717"
        ax.text(
            left + 0.3,
            i,
            f"{tag} ({e['self_loop_count']} edges)",
            va="center",
            fontsize=7,
        )

    ax.set_yticks(y_pos)
    ax.set_yticklabels([e["tool"] for e in slo], fontsize=8)
    ax.set_xlabel("Pipeline count (by origin)")
    ax.set_title("Self-loop tools by module origin")
    ax.legend(title="Origin", loc="lower right")
    ax.text(
        0.98,
        0.02,
        "\u2713 = KNOWN_SUBTOOLS    \u2717 = candidate",
        transform=ax.transAxes,
        ha="right",
        va="bottom",
        fontsize=7,
        fontstyle="italic",
        bbox=dict(boxstyle="round", facecolor="white", alpha=0.7),
    )
    ax.margins(x=0.3)
    plt.tight_layout()
    fig.savefig(os.path.join(mod_dir, "tool_self_loop_origin.png"), dpi=150)
    plt.close(fig)
