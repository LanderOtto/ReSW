from ..core import _tool_domain
from .common import _init_mpl


def _plot_domain_clusters(domains, plot_dir):
    import os

    plt = _init_mpl()
    dt_names = sorted(domains.keys())
    if not dt_names:
        return
    fig, ax = plt.subplots(figsize=(10, 6))
    import seaborn as sns

    colors = sns.color_palette("husl", len(dt_names))
    y_pos = range(len(dt_names))
    for i, dt in enumerate(dt_names):
        pipelines = domains[dt].get("pipelines", [])
        total = len(pipelines)
        certain = sum(1 for p in pipelines if p[2] >= 1.0)
        uncertain = total - certain
        if certain > 0:
            ax.barh(
                i, certain, color=colors[i], hatch="", label=dt if certain > 0 else ""
            )
        if uncertain > 0:
            ax.barh(i, uncertain, left=certain, color=colors[i], hatch="///", alpha=0.7)
        label = f"{total} pipeline{'s' if total != 1 else ''}"
        if uncertain > 0:
            label += f"\n({uncertain} uncertain)"
        ax.text(total + 0.3, i, label, va="center", fontsize=9)

    ax.set_yticks(list(y_pos))
    ax.set_yticklabels(dt_names)
    ax.set_xlabel("Pipelines")
    ax.set_title("Domain clusters  (solid = certain, hatched = mixed-domain)")
    from matplotlib.patches import Patch

    legend_elements = [
        Patch(facecolor="gray", alpha=0.5, label="certain (single-domain)"),
        Patch(
            facecolor="gray", alpha=0.5, hatch="///", label="uncertain (multi-domain)"
        ),
    ]
    ax.legend(handles=legend_elements, loc="lower right", fontsize=8)
    plt.tight_layout()
    fig.savefig(os.path.join(plot_dir, "domain_clusters.png"), dpi=150)
    plt.close(fig)


def _plot_domain_overlap_matrix(graphs, plot_dir):
    import os
    from collections import defaultdict

    plt = _init_mpl()
    import seaborn as sns

    pipeline_domain_counts = defaultdict(lambda: defaultdict(int))
    for g in graphs:
        pipeline_tools = {n.get("app", "") for n in g["nodes"] if n.get("app")}
        for tool in sorted(pipeline_tools):
            domain = _tool_domain(tool)
            if domain:
                pipeline_domain_counts[g["name"]][domain] += 1
    if not pipeline_domain_counts:
        return
    all_domains = sorted(
        {d for counts in pipeline_domain_counts.values() for d in counts}
    )
    n = len(all_domains)
    if n < 2:
        return
    import numpy as np

    overlap = np.zeros((n, n), dtype=int)
    for counts in pipeline_domain_counts.values():
        doms = [d for d in all_domains if counts.get(d, 0) > 0]
        for d1 in doms:
            for d2 in doms:
                i, j = all_domains.index(d1), all_domains.index(d2)
                overlap[i][j] += 1
    fig, ax = plt.subplots(figsize=(8, 7))
    sns.heatmap(
        overlap,
        xticklabels=all_domains,
        yticklabels=all_domains,
        annot=True,
        fmt="d",
        cmap="YlOrRd",
        ax=ax,
        square=True,
    )
    ax.set_title("Domain \u00d7 Domain co-occurrence (pipelines sharing both)")
    plt.setp(ax.get_xticklabels(), rotation=30, ha="right", fontsize=9)
    plt.setp(ax.get_yticklabels(), fontsize=9)
    plt.tight_layout()
    fig.savefig(os.path.join(plot_dir, "domain_overlap_matrix.png"), dpi=150)
    plt.close(fig)


def _plot_domain_tool_heatmap(tool_wfs, domains, plot_dir):
    import os

    plt = _init_mpl()
    import seaborn as sns

    domain_names = sorted(domains.keys())
    if not domain_names:
        return
    domain_pipelines = {}
    for dt in domain_names:
        domain_pipelines[dt] = {p[0] for p in domains[dt].get("pipelines", [])}
    tools_sorted = sorted(tool_wfs.items(), key=lambda x: -len(x[1]))
    top_tools = tools_sorted[:25]
    tool_names = [t for t, _ in top_tools]
    n_tools = len(tool_names)
    n_domains = len(domain_names)
    import numpy as np

    raw_mat = np.zeros((n_domains, n_tools), dtype=int)
    for j, dt in enumerate(domain_names):
        for i, (_tool, pipelines) in enumerate(top_tools):
            raw_mat[j, i] = len(set(pipelines) & domain_pipelines[dt])
    fig, ax = plt.subplots(figsize=(14, 5))
    sns.heatmap(
        raw_mat,
        annot=True,
        fmt="d",
        xticklabels=tool_names,
        yticklabels=domain_names,
        cmap="YlOrRd",
        ax=ax,
        cbar_kws={"label": "Pipeline count"},
    )
    ax.set_xticklabels(tool_names, rotation=45, ha="right", fontsize=8)
    ax.set_title("Tool usage by domain (raw pipeline count)")
    plt.tight_layout()
    fig.savefig(os.path.join(plot_dir, "domain_tool_heatmap.png"), dpi=150)
    plt.close(fig)


def _plot_pipeline_domain_detail(pipeline_detail, plot_dir):
    import os

    if not pipeline_detail:
        return
    plt = _init_mpl()
    import numpy as np
    import seaborn as sns

    detail = pipeline_detail
    pipelines = sorted(detail.keys())
    all_domains = sorted({d for entries in detail.values() for d, _ in entries})
    if not all_domains:
        return
    n_pipes = len(pipelines)
    n_doms = len(all_domains)
    mat = np.zeros((n_doms, n_pipes), dtype=int)
    for j, pname in enumerate(pipelines):
        for domain, tools in detail[pname]:
            if domain in all_domains:
                i = all_domains.index(domain)
                mat[i, j] = len(tools)

    fig, ax = plt.subplots(figsize=(max(10, n_pipes * 0.25), max(5, n_doms * 0.6)))
    sns.heatmap(
        mat,
        annot=True,
        fmt="d",
        xticklabels=[p.split("/")[-1] for p in pipelines],
        yticklabels=all_domains,
        cmap="YlOrRd",
        ax=ax,
        cbar_kws={"label": "Tool count"},
    )
    ax.set_xticklabels(
        [p.split("/")[-1] for p in pipelines], rotation=45, ha="right", fontsize=7
    )
    ax.set_yticklabels(all_domains, fontsize=9)
    ax.set_title("Pipeline-domain detail (tool count per cell)")
    plt.tight_layout()
    fig.savefig(
        os.path.join(plot_dir, "pipeline_domain_heatmap.png"),
        dpi=150,
        bbox_inches="tight",
    )
    plt.close(fig)
