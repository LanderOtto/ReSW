from ..core import _format_subgraph, _is_samtools_only, cross_pair_convergence
from .common import _init_mpl


def _plot_template_diversity(templates, tem_dir):
    import os

    if not templates:
        return
    plt = _init_mpl()
    top20 = templates[:20]
    labels = [
        f"size={t['size']}  {', '.join(t['node_set'][:3])}{'...' if len(t['node_set']) > 3 else ''}"
        for t in top20
    ]
    n_variants = [t["n_variants"] for t in top20]
    n_pipelines = [t["total_pipelines"] for t in top20]
    fig, ax1 = plt.subplots(figsize=(10, 6))
    colors = [
        plt.cm.Oranges(0.5) if t["all_samtools"] else plt.cm.Blues(0.6) for t in top20
    ]
    bars = ax1.barh(range(len(labels)), n_variants, color=colors, label="Edge variants")
    ax1.set_yticks(range(len(labels)))
    ax1.set_yticklabels(labels, fontsize=6)
    ax1.set_xlabel("Edge variants per template")
    ax1.set_title("Template diversity: variants vs pipeline coverage", fontsize=12)
    for bar, v, p in zip(bars, n_variants, n_pipelines):
        ax1.text(
            bar.get_width() + 0.5,
            bar.get_y() + bar.get_height() / 2,
            f"{v} vars, {p} pipes",
            va="center",
            fontsize=7,
        )
    from matplotlib.patches import Patch

    legend_elements = [
        Patch(facecolor=plt.cm.Oranges(0.5), label="all-samtools"),
        Patch(facecolor=plt.cm.Blues(0.6), label="mixed (non-samtools)"),
    ]
    ax1.legend(handles=legend_elements, fontsize=8, loc="lower right")
    ax1.invert_yaxis()
    plt.tight_layout()
    fig.savefig(
        os.path.join(tem_dir, "template_diversity.png"),
        dpi=150,
        bbox_inches="tight",
    )
    plt.close(fig)


def _plot_top_templates(templates, tem_dir):
    import os

    plt = _init_mpl()
    top15 = templates[:15]
    labels = [", ".join(t["node_set"]) for t in top15]
    counts = [t["total_pipelines"] for t in top15]
    is_samtools = [t["all_samtools"] for t in top15]
    fig, ax = plt.subplots(figsize=(10, 7))
    colors = [
        (
            plt.cm.Blues(0.4 + 0.6 * (1 - i / len(top15)))
            if st
            else plt.cm.Oranges(0.4 + 0.6 * (1 - i / len(top15)))
        )
        for i, st in enumerate(is_samtools)
    ]
    bars = ax.barh(range(len(labels)), counts, color=colors)
    ax.set_yticks(range(len(labels)))
    ax.set_yticklabels(labels, fontsize=7)
    for bar, v in zip(bars, counts, strict=True):
        ax.text(
            bar.get_width() + 0.2,
            bar.get_y() + bar.get_height() / 2,
            str(v),
            va="center",
            fontsize=8,
        )
    ax.set_xlabel("Pipeline coverage")
    ax.set_title("Top template families by pipeline coverage", fontsize=12)
    from matplotlib.patches import Patch

    legend_elements = [
        Patch(facecolor=plt.cm.Blues(0.6), label="all-samtools"),
        Patch(facecolor=plt.cm.Oranges(0.6), label="mixed (non-samtools)"),
    ]
    ax.legend(handles=legend_elements, fontsize=8, loc="lower right")
    ax.invert_yaxis()
    plt.tight_layout()
    fig.savefig(
        os.path.join(tem_dir, "top_templates.png"),
        dpi=150,
        bbox_inches="tight",
    )
    plt.close(fig)


def _plot_template_topology(templates, tem_dir):
    import os

    plt = _init_mpl()
    top12 = templates[:12]
    entries = [t["representative"] for t in top12]
    ncols = 4
    nrows = (len(entries) + ncols - 1) // ncols
    fig, axes = plt.subplots(nrows, ncols, figsize=(5 * ncols, 4 * nrows))
    axes = axes.flatten() if hasattr(axes, "flatten") else [axes]

    for i, entry in enumerate(entries):
        ax = axes[i]
        import networkx as nx

        G = nx.DiGraph()
        for src, dst in sorted(entry["edges"]):
            G.add_edge(src, dst)
        pos = nx.spring_layout(G, k=1.5, seed=42)
        is_st = _is_samtools_only(entry["labels"])
        node_color = "lightblue" if is_st else "lightsalmon"
        nx.draw_networkx_nodes(G, pos, ax=ax, node_color=node_color, node_size=500)
        nx.draw_networkx_labels(G, pos, ax=ax, font_size=7)
        nx.draw_networkx_edges(
            G,
            pos,
            ax=ax,
            edge_color="gray",
            arrows=True,
            arrowsize=12,
            arrowstyle="-|>",
            connectionstyle="arc3,rad=0.1",
        )
        tpl = top12[i]
        tag = "samtools" if is_st else "mixed"
        ax.set_title(
            f"{tpl['n_variants']} variants, {tpl['total_pipelines']} pipes [{tag}]",
            fontsize=10,
        )
        ax.axis("off")

    for j in range(len(entries), len(axes)):
        axes[j].axis("off")

    fig.suptitle(
        "Topology of most common template families (representative variant)",
        fontsize=14,
        y=1.02,
    )
    plt.tight_layout()
    fig.savefig(
        os.path.join(tem_dir, "template_topology.png"), dpi=150, bbox_inches="tight"
    )
    plt.close(fig)


def _plot_template_cross_pair(templates, catalog, tem_dir):
    import os

    plt = _init_mpl()
    cross = cross_pair_convergence(catalog, templates)
    if not cross:
        return

    xs = [r["n_pairs"] for r in cross]
    ys = [r["n_variants"] for r in cross]
    sizes = [max(r["total_pipelines"] * 10, 10) for r in cross]
    colors = [r["size"] for r in cross]

    fig, ax = plt.subplots(figsize=(8, 6))
    sc = ax.scatter(
        xs,
        ys,
        s=sizes,
        c=colors,
        cmap="viridis",
        alpha=0.6,
        edgecolors="w",
        linewidth=0.5,
    )
    ax.set_xlabel("Pipeline pairs sharing this template")
    ax.set_ylabel("Edge variants per template")
    ax.set_title("Cross-pair convergence: variants vs pair span", fontsize=12)

    cbar = plt.colorbar(sc, ax=ax)
    cbar.set_label("Subgraph size (nodes)")

    from matplotlib.patches import Patch

    legend_elements = [
        Patch(facecolor="gray", alpha=0.6, label="Point size ∝ pipeline coverage"),
    ]
    ax.legend(handles=legend_elements, fontsize=8, loc="lower right")

    plt.tight_layout()
    fig.savefig(
        os.path.join(tem_dir, "template_cross_pair.png"),
        dpi=150,
        bbox_inches="tight",
    )
    plt.close(fig)
