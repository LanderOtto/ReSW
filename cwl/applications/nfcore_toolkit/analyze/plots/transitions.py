import sys

from ..core import _build_chains
from .common import _init_mpl, format_set


def _plot_transition_network(transitions, plot_dir):
    import os

    plt = _init_mpl()
    if not transitions:
        return
    try:
        import networkx as nx
    except ImportError:
        return
    G = nx.DiGraph()
    top_trans = transitions[:20]
    max_count = top_trans[0][0] if top_trans else 1
    for cnt, src, dst, _ in top_trans:
        G.add_edge(src, dst, weight=cnt)
    components = sorted(nx.weakly_connected_components(G), key=sorted)
    pos = {}
    offset_x = 0
    for component in components:
        nodes = sorted(component, key=str)
        subgraph = G.subgraph(nodes)
        sub_pos = nx.spring_layout(subgraph, k=3.0, seed=42, center=(offset_x, 0))
        pos.update(sub_pos)
        offset_x += 4.0
    fig, ax = plt.subplots(figsize=(16, 12))
    weights = [G[u][v]["weight"] for u, v in G.edges()]
    nx.draw_networkx_nodes(
        G, pos, ax=ax, node_color="steelblue", node_size=800, alpha=0.9
    )
    nx.draw_networkx_labels(G, pos, ax=ax, font_size=9)
    nx.draw_networkx_edges(
        G,
        pos,
        ax=ax,
        width=[2 * w / max_count for w in weights],
        alpha=0.6,
        edge_color="gray",
        arrows=True,
        arrowsize=15,
        connectionstyle="arc3,rad=0.1",
    )
    ax.set_title("Transition network (top 20 edges)")
    ax.axis("off")
    plt.tight_layout()
    fig.savefig(os.path.join(plot_dir, "transition_network.png"), dpi=150)
    plt.close(fig)


def _plot_sankey(transitions, plot_dir):
    import os

    if not transitions:
        return
    try:
        import plotly.graph_objects as go
    except ImportError:
        print("  plotly not available, skipping sankey diagram", file=sys.stderr)
        return

    top = transitions[:30]
    sources = []
    targets = []
    values = []
    all_nodes = []
    node_set = set()
    for cnt, src, dst, _ in top:
        if src not in node_set:
            node_set.add(src)
            all_nodes.append(src)
        if dst not in node_set:
            node_set.add(dst)
            all_nodes.append(dst)
        sources.append(all_nodes.index(src))
        targets.append(all_nodes.index(dst))
        values.append(cnt)

    node_map = {n: i for i, n in enumerate(all_nodes)}
    fig = go.Figure(
        data=[
            go.Sankey(
                arrangement="perpendicular",
                node=dict(
                    pad=40,
                    thickness=20,
                    line=dict(color="black", width=0.5),
                    label=all_nodes,
                ),
                link=dict(
                    source=[node_map[t[1]] for t in top],
                    target=[node_map[t[2]] for t in top],
                    value=[t[0] for t in top],
                ),
            )
        ]
    )
    fig.update_layout(title_text="Transition Sankey diagram", font_size=10)
    fig.update_layout(paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)")
    for trace in fig.data:
        trace.uid = "sankey"
    try:
        fig.write_image(os.path.join(plot_dir, "sankey.png"), width=1200, height=800)
    except Exception as e:
        print(f"  sankey PNG export failed: {e}", file=sys.stderr)
    try:
        fig.write_html(os.path.join(plot_dir, "sankey.html"))
    except Exception:
        pass


def _plot_transitions_frequency(transitions, tool_wfs, plot_dir):
    import os

    plt = _init_mpl()
    import seaborn as sns

    if not transitions:
        return
    top20 = transitions[:20]
    labels = []
    counts = []
    for cnt, src, dst, wfs in top20:
        overlap = len(set(wfs))
        union = len(tool_wfs.get(src, set()) | tool_wfs.get(dst, set()))
        jac = overlap / union if union > 0 else 0
        labels.append(f"{src} \u2192 {dst}  J={jac:.2f}")
        counts.append(cnt)
    fig, ax = plt.subplots(figsize=(11, 7))
    colors = sns.color_palette("viridis", len(labels))
    bars = ax.barh(range(len(labels)), counts, color=colors)
    ax.set_yticks(range(len(labels)))
    ax.set_yticklabels(labels, fontsize=8)
    for bar, v in zip(bars, counts, strict=True):
        ax.text(
            bar.get_width() + 0.3,
            bar.get_y() + bar.get_height() / 2,
            str(v),
            va="center",
            fontsize=9,
        )
    ax.set_xlabel("Edge count")
    ax.set_title("Top 20 transitions with Jaccard similarity")
    ax.invert_yaxis()
    plt.tight_layout()
    fig.savefig(os.path.join(plot_dir, "transitions_frequency.png"), dpi=150)
    plt.close(fig)


def _plot_tool_chains(transitions, plot_dir):
    import os

    plt = _init_mpl()
    import seaborn as sns

    if not transitions:
        return
    chains = _build_chains(transitions)
    if not chains:
        return
    top_chains = chains[:15]
    labels = [f"{a} \u2192 {b} \u2192 {c}" for _, a, b, c, _ in top_chains]
    counts = [cnt for cnt, _, _, _, _ in top_chains]
    fig, ax = plt.subplots(figsize=(10, 7))
    colors = sns.color_palette("mako", len(labels))
    bars = ax.barh(range(len(labels)), counts, color=colors)
    ax.set_yticks(range(len(labels)))
    ax.set_yticklabels(labels)
    for bar, v in zip(bars, counts, strict=True):
        ax.text(
            bar.get_width() + 0.3,
            bar.get_y() + bar.get_height() / 2,
            str(v),
            va="center",
            fontsize=9,
        )
    ax.set_xlabel("Pipelines with chain")
    ax.set_title("Most common 2-step tool chains")
    ax.invert_yaxis()
    plt.tight_layout()
    fig.savefig(os.path.join(plot_dir, "tool_chains.png"), dpi=150)
    plt.close(fig)


def _plot_fan_pattern(patterns, title, xlabel, filename, plot_dir):
    """Horizontal bar chart for divergence or convergence patterns."""
    import os

    plt = _init_mpl()
    import seaborn as sns

    flat = []
    for tool, items in patterns.items():
        for cnt, nset, _ in items:
            flat.append((cnt, tool, nset))
    flat.sort(key=lambda x: (-x[0], x[1], sorted(x[2])))
    if not flat:
        return
    top = flat[:15]
    labels = [
        (
            f"{t} \u2192 {format_set(s)}"
            if "\u2192" not in title
            else f"{format_set(s)} \u2192 {t}"
        )
        for cnt, t, s in top
    ]
    # Actually determine whether this is divergence or convergence by title
    if "convergence" in title.lower():
        labels = [f"{format_set(s)} \u2192 {t}" for cnt, t, s in top]
    else:
        labels = [f"{t} \u2192 {format_set(s)}" for cnt, t, s in top]
    counts = [cnt for cnt, _, _ in top]
    fig, ax = plt.subplots(figsize=(10, 7))
    colors = sns.color_palette("mako", len(labels))
    bars = ax.barh(range(len(labels)), counts, color=colors)
    ax.set_yticks(range(len(labels)))
    ax.set_yticklabels(labels, fontsize=8)
    for bar, v in zip(bars, counts, strict=True):
        ax.text(
            bar.get_width() + 0.3,
            bar.get_y() + bar.get_height() / 2,
            str(v),
            va="center",
            fontsize=9,
        )
    ax.set_xlabel(xlabel)
    ax.set_title(title)
    ax.invert_yaxis()
    plt.tight_layout()
    fig.savefig(os.path.join(plot_dir, filename), dpi=150)
    plt.close(fig)


def _plot_divergence_patterns(divergence, plot_dir):
    _plot_fan_pattern(
        divergence,
        "Most common divergence patterns (tool \u2192 {successors})",
        "Pipelines with pattern",
        "divergence_patterns.png",
        plot_dir,
    )


def _plot_convergence_patterns(convergence, plot_dir):
    _plot_fan_pattern(
        convergence,
        "Most common convergence patterns ({predecessors} \u2192 tool)",
        "Pipelines with pattern",
        "convergence_patterns.png",
        plot_dir,
    )


def _write_transition_trace(transitions, tool_wfs, plot_dir):
    import json
    import os

    if not transitions:
        return
    trans_data = []
    for cnt, src, dst, wfs in transitions:
        trans_data.append(
            {
                "source": src,
                "target": dst,
                "count": cnt,
                "pipelines": sorted(wfs),
            }
        )
    chains = _build_chains(transitions)
    chains_dicts = [
        {"a": a, "b": b, "c": c, "count": cnt, "pipelines": pl}
        for cnt, a, b, c, pl in chains
    ]
    trace = {
        "transitions": trans_data,
        "chains": chains_dicts,
    }
    path = os.path.join(plot_dir, "transition_trace.json")
    with open(path, "w") as f:
        json.dump(trace, f, indent=2)
    print(f"  Wrote {path}", file=sys.stderr)


def _plot_self_loops(transitions, plot_dir):
    import os

    from ..core import _find_self_loops

    plt = _init_mpl()
    self_loops = _find_self_loops(transitions)
    if not self_loops:
        return
    sorted_loops = sorted(self_loops, key=lambda x: -x[0])
    labels = [t for cnt, t in sorted_loops]
    counts = [cnt for cnt, t in sorted_loops]
    fig, ax = plt.subplots(figsize=(10, max(6, len(labels) * 0.25)))
    colors = [
        plt.cm.Reds(0.3 + 0.7 * (1 - i / len(labels))) for i in range(len(labels))
    ]
    bars = ax.barh(range(len(labels)), counts, color=colors)
    ax.set_yticks(range(len(labels)))
    ax.set_yticklabels(labels, fontsize=7)
    for bar, v in zip(bars, counts, strict=True):
        ax.text(
            bar.get_width() + 0.3,
            bar.get_y() + bar.get_height() / 2,
            str(v),
            va="center",
            fontsize=7,
        )
    ax.set_xlabel("Self-loop edges")
    ax.set_title("Tools with self-loop edges (potential collapsed toolkits)")
    ax.invert_yaxis()
    plt.tight_layout()
    fig.savefig(os.path.join(plot_dir, "self_loops.png"), dpi=150, bbox_inches="tight")
    plt.close(fig)
