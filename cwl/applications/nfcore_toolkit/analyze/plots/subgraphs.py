from ..core import _format_subgraph, _is_samtools_only, exact_subgraph_convergence
from .common import _init_mpl


def _plot_top_connected_subgraphs(catalog, sub_dir):
    import os

    plt = _init_mpl()
    entries = catalog[:15]
    is_samtools = [_is_samtools_only(e["labels"]) for e in entries]
    labels = [_format_subgraph(e["labels"], e["edges"]) for e in entries]
    counts = [e["count"] for e in entries]
    fig, ax = plt.subplots(figsize=(10, 7))
    colors = [
        (
            plt.cm.Blues(0.4 + 0.6 * (1 - i / len(entries)))
            if st
            else plt.cm.Oranges(0.4 + 0.6 * (1 - i / len(entries)))
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
    ax.set_xlabel("Pipelines sharing subgraph")
    ax.set_title("Most common connected subgraphs (all sizes)", fontsize=12)
    from matplotlib.patches import Patch

    legend_elements = [
        Patch(facecolor=plt.cm.Blues(0.6), label="all-samtools"),
        Patch(facecolor=plt.cm.Oranges(0.6), label="mixed (non-samtools)"),
    ]
    ax.legend(handles=legend_elements, fontsize=8, loc="lower right")
    ax.invert_yaxis()
    plt.tight_layout()
    fig.savefig(
        os.path.join(sub_dir, "top_connected_subgraphs.png"),
        dpi=150,
        bbox_inches="tight",
    )
    plt.close(fig)


def _plot_top_size2_subgraphs(catalog, sub_dir):
    import os

    plt = _init_mpl()
    size2 = sorted(
        [e for e in catalog if e["size"] == 2],
        key=lambda x: (-x["count"], sorted(x["labels"]), sorted(x["edges"])),
    )[:15]
    labels = [_format_subgraph(e["labels"], e["edges"]) for e in size2]
    counts = [e["count"] for e in size2]
    colors = [
        plt.cm.Greens(0.3 + 0.7 * (1 - i / len(size2))) for i in range(len(size2))
    ]
    fig, ax = plt.subplots(figsize=(10, 7))
    bars = ax.barh(range(len(labels)), counts, color=colors)
    ax.set_yticks(range(len(labels)))
    ax.set_yticklabels(labels, fontsize=8)
    for bar, v in zip(bars, counts, strict=True):
        ax.text(
            bar.get_width() + 0.2,
            bar.get_y() + bar.get_height() / 2,
            str(v),
            va="center",
            fontsize=8,
        )
    ax.set_xlabel("Pipelines sharing subgraph")
    ax.set_title("Most common size-2 subgraphs", fontsize=12)
    ax.invert_yaxis()
    plt.tight_layout()
    fig.savefig(
        os.path.join(sub_dir, "top_size2_subgraphs.png"), dpi=150, bbox_inches="tight"
    )
    plt.close(fig)


def _plot_top_pipeline_pairs(pairwise, sub_dir):
    import os

    plt = _init_mpl()
    top15 = pairwise[:15]
    labels = [f"{a.split('/')[-1]} \u2194 {b.split('/')[-1]}" for cnt, a, b, _ in top15]
    counts = [cnt for cnt, _, _, _ in top15]
    colors = [
        plt.cm.Oranges(0.3 + 0.7 * (1 - i / len(top15))) for i in range(len(top15))
    ]
    fig, ax = plt.subplots(figsize=(10, 7))
    bars = ax.barh(range(len(labels)), counts, color=colors)
    ax.set_yticks(range(len(labels)))
    ax.set_yticklabels(labels, fontsize=8)
    for bar, v in zip(bars, counts, strict=True):
        ax.text(
            bar.get_width() + 0.5,
            bar.get_y() + bar.get_height() / 2,
            str(v),
            va="center",
            fontsize=8,
        )
    ax.set_xlabel("Unique shared subgraphs")
    ax.set_title("Pipeline pairs with most shared subgraphs", fontsize=12)
    ax.invert_yaxis()
    plt.tight_layout()
    fig.savefig(
        os.path.join(sub_dir, "top_pipeline_pairs.png"), dpi=150, bbox_inches="tight"
    )
    plt.close(fig)


def _plot_subgraph_topology(catalog, sub_dir, font_path=None):
    import os

    if font_path:
        import matplotlib.pyplot as plt
        from matplotlib import font_manager

        font_manager.fontManager.addfont(font_path)
        prop = font_manager.FontProperties(fname=font_path)
        plt.rcParams["font.family"] = prop.get_name()

    plt = _init_mpl()
    entries = catalog[:12]
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
        tag = "samtools" if is_st else "mixed"
        ax.set_title(f"n={entry['count']} [{tag}]", fontsize=10)
        ax.axis("off")

    for j in range(len(entries), len(axes)):
        axes[j].axis("off")

    fig.suptitle("Topology of most common connected subgraphs", fontsize=14, y=1.02)
    plt.tight_layout()
    fig.savefig(
        os.path.join(sub_dir, "subgraph_topology.png"), dpi=150, bbox_inches="tight"
    )
    plt.close(fig)


def _plot_larger_subgraph_topology(catalog, sub_dir, font_path=None):
    import os

    plt = _init_mpl()

    if font_path:
        import matplotlib.pyplot as plt
        from matplotlib import font_manager

        font_manager.fontManager.addfont(font_path)
        prop = font_manager.FontProperties(fname=font_path)
        plt.rcParams["font.family"] = prop.get_name()

    base_font_size = 14
    scale_factor = base_font_size / 7.0
    scaled_node_size = int((scale_factor**2) * 500)
    scaled_arrow_size = int(scale_factor * 12)
    scaled_title_size = int(scale_factor * 10)

    entries = catalog[:6]
    ncols = 3
    nrows = (len(entries) + ncols - 1) // ncols

    fig, axes = plt.subplots(nrows, ncols, figsize=(5 * ncols, 4 * nrows))
    axes = axes.flatten() if hasattr(axes, "flatten") else [axes]

    for i, entry in enumerate(entries):
        ax = axes[i]
        import networkx as nx

        G = nx.DiGraph()
        for src, dst in sorted(entry["edges"]):
            G.add_edge(src, dst)

        # pos = nx.spring_layout(G, k=1.5, seed=42)
        try:
            # 1. The Gold Standard: Graphviz 'dot' layout
            # (Requires: pip install pygraphviz or pydot)
            # This perfectly structures directed graphs into hierarchical trees.
            from networkx.drawing.nx_agraph import graphviz_layout

            pos = graphviz_layout(G, prog="dot")

        except ImportError:
            try:
                # 2. Built-in Fallback for pipelines (DAGs)
                # Groups nodes into columns based on their execution order
                for layer, nodes in enumerate(nx.topological_generations(G)):
                    for node in nodes:
                        G.nodes[node]["layer"] = layer

                # Places layers side-by-side (left to right)
                pos = nx.multipartite_layout(G, subset_key="layer", align="vertical")

                # Optional: Add a bit of spacing to prevent vertical overlapping
                # pos = {k: (v[0], v[1] * 2) for k, v in pos.items()}

            except nx.NetworkXUnfeasible:
                # 3. Last Resort Fallback (if the graph contains cycles)
                # Kamada-Kawai usually yields much cleaner shapes than spring_layout
                pos = nx.kamada_kawai_layout(G)
        # ---------------------------------

        is_st = _is_samtools_only(entry["labels"])
        node_color = "lightblue" if is_st else "lightsalmon"
        nx.draw_networkx_nodes(
            G, pos, ax=ax, node_color=node_color, node_size=scaled_node_size
        )
        nx.draw_networkx_labels(G, pos, ax=ax, font_size=base_font_size)
        nx.draw_networkx_edges(
            G,
            pos,
            ax=ax,
            edge_color="gray",
            arrows=True,
            arrowsize=scaled_arrow_size,
            arrowstyle="-|>",
            connectionstyle="arc3,rad=0.1",
        )
        tag = "samtools" if is_st else "mixed"

        # ax.set_title(f"n={entry['count']} [{tag}]", fontsize=scaled_title_size)
        ax.axis("off")

    for j in range(len(entries), len(axes)):
        axes[j].axis("off")

    plt.tight_layout()
    fig.savefig(
        os.path.join(sub_dir, "larger_subgraph_topology.png"),
        dpi=150,
        bbox_inches="tight",
    )
    plt.close(fig)


def _plot_colored_subgraph_topology(catalog, sub_dir, font_path=None):
    import os

    import matplotlib.colors as mcolors
    import matplotlib.patches as mpatches

    plt = _init_mpl()

    # --- Scaling Configuration ---
    base_font_size = 14
    scale_factor = base_font_size / 7.0
    scaled_node_size = int((scale_factor**2) * 500)
    scaled_arrow_size = int(scale_factor * 12)
    # Scale the stroke thickness proportionally so it's clearly visible
    scaled_linewidth = scale_factor * 2.0

    if font_path:
        import matplotlib.pyplot as plt
        from matplotlib import font_manager

        font_manager.fontManager.addfont(font_path)
        prop = font_manager.FontProperties(fname=font_path)
        plt.rcParams["font.family"] = prop.get_name()

    # --- Top 6 entries, 3 columns ---
    entries = catalog[:6]
    ncols = 3
    nrows = (len(entries) + ncols - 1) // ncols

    fig, axes = plt.subplots(nrows, ncols, figsize=(5 * ncols, (4 * nrows) + 1))
    axes = axes.flatten() if hasattr(axes, "flatten") else [axes]

    # --- 1. BUILD STROKE AND FILL COLOR PALETTES ---
    unique_labels = set()
    for entry in entries:
        unique_labels.update(entry.get("labels", frozenset()))

    unique_labels = sorted(list(unique_labels))

    cmap = plt.get_cmap("tab10")

    label_stroke_map = {}
    label_fill_map = {}

    for i, label in enumerate(unique_labels):
        base_color = cmap(i % 10)
        label_stroke_map[label] = base_color

        r, g, b, a = mcolors.to_rgba(base_color)
        tint = 0.80
        label_fill_map[label] = (
            r + (1.0 - r) * tint,
            g + (1.0 - g) * tint,
            b + (1.0 - b) * tint,
            a,
        )
    # -----------------------------------------------

    for i, entry in enumerate(entries):
        ax = axes[i]
        import networkx as nx

        G = nx.DiGraph()

        for src, dst in sorted(entry["edges"]):
            G.add_edge(src, dst)

        try:
            from networkx.drawing.nx_agraph import graphviz_layout

            pos = graphviz_layout(G, prog="dot", args="-Gnodesep=1 -Granksep=2.0")
        except ImportError:
            try:
                for layer, nodes in enumerate(nx.topological_generations(G)):
                    for node in nodes:
                        G.nodes[node]["layer"] = layer
                pos = nx.multipartite_layout(G, subset_key="layer", align="vertical")
            except nx.NetworkXUnfeasible:
                pos = nx.kamada_kawai_layout(G)

        # --- 2. ASSIGN STROKES AND FILLS TO NODES ---
        node_fills = [label_fill_map.get(node, "#f0f0f0") for node in G.nodes()]
        node_strokes = [label_stroke_map.get(node, "gray") for node in G.nodes()]

        nx.draw_networkx_nodes(
            G,
            pos,
            ax=ax,
            node_color=node_fills,
            edgecolors=node_strokes,
            linewidths=scaled_linewidth,
            node_size=scaled_node_size,
        )

        # FIX: Added width=scaled_linewidth to match the edge thickness to the node borders
        nx.draw_networkx_edges(
            G,
            pos,
            ax=ax,
            edge_color="gray",
            arrows=True,
            node_size=scaled_node_size,
            arrowsize=scaled_arrow_size,
            arrowstyle="-|>",
            connectionstyle="arc3,rad=0.1",
            width=scaled_linewidth,
        )
        # --------------------------------------------

        # Expand the axis limits slightly to prevent nodes from being cut off
        x_values, y_values = zip(*pos.values())
        x_margin = (max(x_values) - min(x_values)) * 0.15
        y_margin = (max(y_values) - min(y_values)) * 0.15
        if x_margin == 0:
            x_margin = 0.5
        if y_margin == 0:
            y_margin = 0.5
        ax.set_xlim(min(x_values) - x_margin, max(x_values) + x_margin)
        ax.set_ylim(min(y_values) - y_margin, max(y_values) + y_margin)

        ax.axis("off")

    for j in range(len(entries), len(axes)):
        axes[j].axis("off")

    # Keep your tight_layout as is
    plt.tight_layout(rect=[0, 0.15, 1, 1])

    # --- 3. CREATE THE MATCHING GLOBAL LEGEND ---
    legend_handles = [
        mpatches.Patch(
            facecolor=label_fill_map[label],
            edgecolor=label_stroke_map[label],
            linewidth=scaled_linewidth * 0.75,
            label=label,
        )
        for label in unique_labels
    ]

    bbox_extra_artists = []

    if legend_handles:
        legend_font = 28
        leg = fig.legend(
            handles=legend_handles,
            loc="upper center",
            ncol=max(1, min(len(legend_handles), 3)),
            fontsize=legend_font,
            frameon=False,
            bbox_to_anchor=(0.5, 0.13),
        )
        bbox_extra_artists = [leg]
    # --------------------------------------------

    save_kwargs = {"dpi": 150, "bbox_inches": "tight"}
    if bbox_extra_artists:
        save_kwargs["bbox_extra_artists"] = bbox_extra_artists

    fig.savefig(os.path.join(sub_dir, "colored_subgraph_topology.png"), **save_kwargs)
    plt.close(fig)


def _plot_non_only_samtools_subgraphs(non_samtools_catalog, sub_dir):
    import os

    plt = _init_mpl()
    if not non_samtools_catalog:
        return
    top15 = non_samtools_catalog[:15]
    labels = [_format_subgraph(e["labels"], e["edges"]) for e in top15]
    counts = [e["count"] for e in top15]
    non_st_labels = [
        ", ".join(
            l for l in e["labels"] if not (l.startswith("samtools.") or l == "samtools")
        )
        for e in top15
    ]
    fig, ax = plt.subplots(figsize=(10, 7))
    colors = [
        plt.cm.Oranges(0.4 + 0.6 * (1 - i / len(top15))) for i in range(len(top15))
    ]
    bars = ax.barh(range(len(labels)), counts, color=colors)
    ax.set_yticks(range(len(labels)))
    ax.set_yticklabels(labels, fontsize=7)
    for bar, v, ns in zip(bars, counts, non_st_labels, strict=True):
        ax.text(
            bar.get_width() + 0.2,
            bar.get_y() + bar.get_height() / 2,
            f"{v}  [{ns}]",
            va="center",
            fontsize=7,
        )
    ax.set_xlabel("Pipelines sharing subgraph")
    ax.set_title(
        "Most common non-only-samtools subgraphs (at least one non-samtools tool)"
    )
    ax.invert_yaxis()
    plt.tight_layout()
    fig.savefig(
        os.path.join(sub_dir, "non_only_samtools_subgraphs.png"),
        dpi=150,
        bbox_inches="tight",
    )
    plt.close(fig)


def _plot_exact_convergence_top(catalog, sub_dir):
    import os

    plt = _init_mpl()
    exact = exact_subgraph_convergence(catalog, min_pipelines=3)
    if not exact:
        return
    top15 = exact[:15]
    labels = [_format_subgraph(e["labels"], e["edges"]) for e in top15]
    counts = [len(e["pipelines"]) for e in top15]
    size_colors = {
        2: "#4c72b0",
        3: "#55a868",
        4: "#c44e52",
        5: "#8172b2",
        6: "#ccb974",
    }
    colors = [size_colors.get(e["size"], "#7f7f7f") for e in top15]
    fig, ax = plt.subplots(figsize=(10, 7))
    bars = ax.barh(range(len(labels)), counts, color=colors)
    ax.set_yticks(range(len(labels)))
    ax.set_yticklabels(labels, fontsize=7)
    for bar, v in zip(bars, counts, strict=True):
        ax.text(
            bar.get_width() + 0.3,
            bar.get_y() + bar.get_height() / 2,
            str(v),
            va="center",
            fontsize=8,
        )
    ax.set_xlabel("Pipeline count")
    ax.set_title(
        "Top exact subgraph convergence (same labels, same edges, \u22653 pipelines)",
        fontsize=12,
    )
    from matplotlib.patches import Patch

    legend_elements = [
        Patch(facecolor=size_colors[s], label=f"size {s}") for s in sorted(size_colors)
    ]
    ax.legend(handles=legend_elements, fontsize=8, loc="lower right")
    ax.invert_yaxis()
    plt.tight_layout()
    fig.savefig(
        os.path.join(sub_dir, "exact_convergence_top.png"), dpi=150, bbox_inches="tight"
    )
    plt.close(fig)


def _plot_exact_convergence_distribution(catalog, sub_dir):
    import os
    from collections import Counter

    plt = _init_mpl()
    exact = exact_subgraph_convergence(catalog, min_pipelines=3)
    if not exact:
        return

    buckets = Counter()
    for e in exact:
        n = len(e["pipelines"])
        if n == 3:
            buckets["3"] += 1
        elif n == 4:
            buckets["4"] += 1
        elif n == 5:
            buckets["5"] += 1
        elif n <= 10:
            buckets["6\u201310"] += 1
        elif n <= 20:
            buckets["11\u201320"] += 1
        elif n <= 50:
            buckets["21\u201350"] += 1
        else:
            buckets["51+"] += 1

    order = ["3", "4", "5", "6\u201310", "11\u201320", "21\u201350", "51+"]
    labels = order
    values = [buckets.get(k, 0) for k in order]

    fig, ax = plt.subplots(figsize=(8, 5))
    colors = plt.cm.Blues([0.3 + 0.5 * i / len(order) for i in range(len(order))])
    bars = ax.bar(range(len(labels)), values, color=colors, width=0.6)
    ax.set_xticks(range(len(labels)))
    ax.set_xticklabels(labels, fontsize=10)
    ax.set_ylabel("Number of subgraph entries")
    ax.set_xlabel("Pipelines sharing exact subgraph")
    ax.set_title(
        "Distribution of exact subgraph convergence (same labels, same edges)",
        fontsize=12,
    )
    for bar, v in zip(bars, values, strict=True):
        ax.text(
            bar.get_x() + bar.get_width() / 2,
            bar.get_height() + max(values) * 0.01,
            str(v),
            ha="center",
            va="bottom",
            fontsize=10,
        )
    plt.tight_layout()
    fig.savefig(
        os.path.join(sub_dir, "exact_convergence_distribution.png"),
        dpi=150,
        bbox_inches="tight",
    )
    plt.close(fig)
