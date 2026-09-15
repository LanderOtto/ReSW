from ..core import _tool_domain
from .common import _init_mpl, format_set


def _plot_tool_popularity(tool_wfs, plot_dir):
    import os

    plt = _init_mpl()
    tools_sorted = sorted(tool_wfs.items(), key=lambda x: -len(x[1]))
    total = len(tool_wfs)
    singletons = sum(1 for _, ps in tool_wfs.items() if len(ps) == 1)
    top30 = tools_sorted[:30]
    names = [t for t, _ in top30]
    counts = [len(ps) for _, ps in top30]
    fig, ax = plt.subplots(figsize=(10, 6))
    ax.barh(range(len(names)), counts, color="steelblue")
    ax.set_yticks(range(len(names)))
    ax.set_yticklabels(names)
    ax.set_xlabel("Pipelines")
    ax.set_title("Top 30 tools by pipeline count")
    ax.text(
        0.95,
        0.05,
        f"Total: {total} | Singletons: {singletons} ({100 * singletons // total}%)",
        transform=ax.transAxes,
        ha="right",
        va="bottom",
        fontsize=10,
        bbox=dict(boxstyle="round", facecolor="wheat", alpha=0.5),
    )
    ax.invert_yaxis()
    plt.tight_layout()
    fig.savefig(os.path.join(plot_dir, "tool_popularity.png"), dpi=150)
    plt.close(fig)


def _plot_edge_node_ratio(topo, plot_dir):
    import os

    plt = _init_mpl()
    nonempty = [(p, n, e, r) for p, n, e, r, _ in topo if n > 0]
    if not nonempty:
        return
    ratios = [r for _, _, _, r in nonempty]
    fig, ax = plt.subplots(figsize=(8, 5))
    ax.hist(ratios, bins=20, color="steelblue", edgecolor="white")
    ax.axvline(
        sum(ratios) / len(ratios),
        color="red",
        linestyle="--",
        label=f"mean={sum(ratios) / len(ratios):.2f}",
    )
    ax.axvline(
        sorted(ratios)[len(ratios) // 2],
        color="green",
        linestyle=":",
        label=f"median={sorted(ratios)[len(ratios) // 2]:.2f}",
    )
    ax.set_xlabel("Edge / node ratio")
    ax.set_ylabel("Pipelines")
    ax.set_title("DAG topology diversity")
    ax.legend()
    plt.tight_layout()
    fig.savefig(os.path.join(plot_dir, "edge_node_ratio.png"), dpi=150)
    plt.close(fig)


def _plot_failure_categories(graphs, plot_dir):
    import os
    from collections import defaultdict

    plt = _init_mpl()
    import seaborn as sns

    success_count = sum(1 for g in graphs if len(g["nodes"]) > 0)
    fail_counts = defaultdict(int)
    for g in graphs:
        fc = g["meta"].get("failure_classification", {})
        cat = fc.get("category", "")
        if cat:
            fail_counts[cat] += 1
    if not fail_counts:
        return
    cats = ["success"] + sorted(fail_counts.keys())
    vals = [success_count] + [fail_counts[c] for c in sorted(fail_counts.keys())]
    colors = ["mediumseagreen"] + [
        sns.color_palette("Set2")[i % len(sns.color_palette("Set2"))]
        for i in range(len(cats) - 1)
    ]
    fig, ax = plt.subplots(figsize=(10, 5))
    bars = ax.bar(cats, vals, color=colors)
    for bar, v in zip(bars, vals, strict=True):
        ax.text(
            bar.get_x() + bar.get_width() / 2,
            bar.get_height() + 0.5,
            str(v),
            ha="center",
            fontsize=10,
        )
    ax.set_ylabel("Pipelines")
    ax.set_title("Pipeline outcomes by category")
    plt.setp(ax.get_xticklabels(), rotation=30, ha="right")
    plt.tight_layout()
    fig.savefig(os.path.join(plot_dir, "failure_categories.png"), dpi=150)
    plt.close(fig)


def _plot_singleton_scatter(tool_wfs, topo, domains, plot_dir):
    import os
    from collections import defaultdict

    plt = _init_mpl()
    import seaborn as sns

    singleton_per_pipeline = defaultdict(int)
    for _tool, pipelines in tool_wfs.items():
        if len(pipelines) == 1:
            singleton_per_pipeline[next(iter(pipelines))] += 1
    pipeline_domain_map = {}
    for domain, data in domains.items():
        for pname, _, _, _ in data["pipelines"]:
            pipeline_domain_map.setdefault(pname, domain)
    scatter_data = []
    for pname, _, _, _, tools in topo:
        n_unique_tools = len(tools)
        scount = singleton_per_pipeline.get(pname, 0)
        pdomain = pipeline_domain_map.get(pname, "unknown")
        scatter_data.append((pname, n_unique_tools, scount, pdomain))
    if not scatter_data:
        return
    fig, ax = plt.subplots(figsize=(10, 7))
    dset = sorted(set(d for _, _, _, d in scatter_data))
    cmap = dict(zip(dset, sns.color_palette("husl", len(dset)), strict=True))
    for _pname, n_tools, scount, pdomain in scatter_data:
        ax.scatter(
            n_tools,
            scount,
            color=cmap[pdomain],
            s=80,
            alpha=0.7,
            edgecolors="black",
            linewidth=0.5,
            label=pdomain,
        )
    ax.set_xlabel("Unique tools in pipeline")
    ax.set_ylabel("Singleton tools (unique to this pipeline)")
    ax.set_title("Unique tools vs singleton count")
    handles = [
        plt.Line2D(
            [0], [0], marker="o", color="w", markerfacecolor=cmap[d], markersize=8
        )
        for d in dset
    ]
    ax.legend(handles, dset, title="Domain", loc="upper right")
    plt.tight_layout()
    fig.savefig(os.path.join(plot_dir, "singleton_scatter.png"), dpi=150)
    plt.close(fig)


def _plot_cooccurrence_heatmap(tool_wfs, cooccur, plot_dir):
    import os

    plt = _init_mpl()
    import seaborn as sns

    tools_in_10 = [t for t, ps in tool_wfs.items() if len(ps) >= 10]
    if len(tools_in_10) < 3:
        return
    n = len(tools_in_10)
    jmat = [[0.0] * n for _ in range(n)]
    idx = {t: i for i, t in enumerate(tools_in_10)}
    for _, jac, t1, t2, _, _ in cooccur:
        if t1 in idx and t2 in idx:
            i, j = idx[t1], idx[t2]
            jmat[i][j] = jac
            jmat[j][i] = jac
    fig, ax = plt.subplots(figsize=(12, 10))
    sns.heatmap(
        jmat,
        xticklabels=tools_in_10,
        yticklabels=tools_in_10,
        annot=False,
        cmap="YlOrRd",
        square=True,
        ax=ax,
        vmin=0,
        vmax=1,
    )
    ax.set_title("Tool co-occurrence (Jaccard index)")
    plt.setp(ax.get_xticklabels(), rotation=45, ha="right", fontsize=8)
    plt.setp(ax.get_yticklabels(), fontsize=8)
    plt.tight_layout()
    fig.savefig(os.path.join(plot_dir, "cooccurrence_heatmap.png"), dpi=150)
    plt.close(fig)


def _plot_singletons_per_pipeline(tool_wfs, plot_dir):
    import os
    from collections import defaultdict

    plt = _init_mpl()
    singleton_per_pipeline = defaultdict(int)
    for tool, pipelines in tool_wfs.items():
        if len(pipelines) == 1:
            singleton_per_pipeline[next(iter(pipelines))] += 1
    if not singleton_per_pipeline:
        return
    sorted_pipes = sorted(singleton_per_pipeline.items(), key=lambda x: -x[1])
    labels = [p.split("/")[-1] for p, _ in sorted_pipes]
    counts = [c for _, c in sorted_pipes]
    fig, ax = plt.subplots(figsize=(10, max(6, len(labels) * 0.3)))
    colors = [
        plt.cm.YlOrRd(0.3 + 0.7 * (1 - i / len(labels))) for i in range(len(labels))
    ]
    bars = ax.barh(range(len(labels)), counts, color=colors)
    ax.set_yticks(range(len(labels)))
    ax.set_yticklabels(labels, fontsize=8)
    for bar, v in zip(bars, counts, strict=True):
        ax.text(
            bar.get_width() + 0.1,
            bar.get_y() + bar.get_height() / 2,
            str(v),
            va="center",
            fontsize=8,
        )
    ax.set_xlabel("Singleton tools")
    ax.set_title("Pipelines by singleton tool count")
    ax.invert_yaxis()
    plt.tight_layout()
    fig.savefig(
        os.path.join(plot_dir, "singletons_per_pipeline.png"),
        dpi=150,
        bbox_inches="tight",
    )
    plt.close(fig)
