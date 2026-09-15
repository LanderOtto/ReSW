from .common import _init_mpl


def _plot_graph_quality(graph_quality, plot_dir):
    import os

    plt = _init_mpl()
    empty_by_category, empty_external, split_dags, isolated_dags, _status_br = (
        graph_quality
    )

    # Collect categories with counts
    cat_order = [
        "preview_failed",
        "timeout",
        "config_parsing",
        "permissions",
        "unknown_config",
        "unclassified",
    ]
    cat_labels = {
        "preview_failed": "Preview failed\n(no DAG produced)",
        "timeout": "Timeout\n(DAG too slow)",
        "config_parsing": "Config parsing\n(NF 26.x regression)",
        "permissions": "Permissions\n(work dir access)",
        "unknown_config": "Unknown config\n(attribute error)",
        "unclassified": "Unclassified\n(no match)",
    }
    cat_colors = {
        "preview_failed": "#e74c3c",
        "timeout": "#f39c12",
        "config_parsing": "#9b59b6",
        "permissions": "#e67e22",
        "unknown_config": "#95a5a6",
        "unclassified": "#7f8c8d",
    }

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 6))

    # Left panel: empty DAG failure categories (stacked horizontal)
    cats = []
    counts = []
    colors = []
    for cat in cat_order:
        items = empty_by_category.get(cat, [])
        if items:
            active = sum(1 for _, m in items if m.get("status") == "active")
            archived = sum(1 for _, m in items if m.get("status") == "archived")
            unreleased = sum(1 for _, m in items if m.get("status") == "unreleased")
            if active:
                cats.append(cat_labels.get(cat, cat))
                counts.append(active)
                colors.append(cat_colors.get(cat, "#3498db"))
            if archived:
                cats.append(cat_labels.get(cat, cat) + "\n(archived)")
                counts.append(archived)
                colors.append("#bdc3c7")
            if unreleased:
                cats.append(cat_labels.get(cat, cat) + "\n(unreleased)")
                counts.append(unreleased)
                colors.append("#d4a574")
    if empty_external:
        cats.append("External\n(structural only)")
        counts.append(len(empty_external))
        colors.append("#2ecc71")

    if counts:
        bars = ax1.barh(range(len(cats)), counts, color=colors)
        ax1.set_yticks(range(len(cats)))
        ax1.set_yticklabels(cats, fontsize=8)
        for bar, v in zip(bars, counts, strict=True):
            ax1.text(
                bar.get_width() + 0.2,
                bar.get_y() + bar.get_height() / 2,
                str(v),
                va="center",
                fontsize=9,
            )
        ax1.set_xlabel("Pipelines")
        ax1.set_title("Empty DAGs by failure category", fontsize=12)
        ax1.invert_yaxis()

    # Right panel: component count histogram for split DAGs
    if split_dags:
        comp_vals = [c for _, c, _, _ in split_dags]
        unique_comps = sorted(set(comp_vals))
        comp_hist = {c: comp_vals.count(c) for c in unique_comps}
        comp_cats = [f"{c} components" for c in unique_comps]
        comp_counts_list = [comp_hist[c] for c in unique_comps]
        colors2 = [
            plt.cm.Reds(0.3 + 0.7 * (1 - i / len(comp_cats)))
            for i in range(len(comp_cats))
        ]
        bars2 = ax2.barh(range(len(comp_cats)), comp_counts_list, color=colors2)
        ax2.set_yticks(range(len(comp_cats)))
        ax2.set_yticklabels(comp_cats, fontsize=9)
        for bar, v in zip(bars2, comp_counts_list, strict=True):
            ax2.text(
                bar.get_width() + 0.2,
                bar.get_y() + bar.get_height() / 2,
                str(v),
                va="center",
                fontsize=10,
            )
        ax2.set_xlabel("Pipelines")
        ax2.set_title("Split DAGs by component count", fontsize=12)
        ax2.invert_yaxis()
    else:
        ax2.text(
            0.5,
            0.5,
            "No split DAGs detected",
            ha="center",
            va="center",
            transform=ax2.transAxes,
            fontsize=12,
        )
        ax2.set_title("Split DAGs by component count", fontsize=12)

    plt.tight_layout()
    fig.savefig(
        os.path.join(plot_dir, "graph_quality.png"), dpi=150, bbox_inches="tight"
    )
    plt.close(fig)


def _plot_pipeline_status(status_breakdown, plot_dir):
    import os

    plt = _init_mpl()

    counts = status_breakdown["counts"]
    success = status_breakdown["success"]
    fail = status_breakdown["fail"]

    labels = []
    total_vals = []
    ok_vals = []
    fail_vals = []
    bar_colors = []
    for st in ["active", "archived", "unreleased"]:
        if counts.get(st, 0):
            labels.append(st.capitalize())
            total_vals.append(counts[st])
            ok_vals.append(success.get(st, 0))
            fail_vals.append(fail.get(st, 0))
            bar_colors.append(
                {"active": "#2ecc71", "archived": "#bdc3c7", "unreleased": "#d4a574"}[
                    st
                ]
            )

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(10, 4))

    # Left: total counts
    if total_vals:
        x = range(len(labels))
        ax1.barh(x, total_vals, color=bar_colors, edgecolor="white")
        ax1.set_yticks(list(x))
        ax1.set_yticklabels(labels, fontsize=10)
        for i, v in enumerate(total_vals):
            ax1.text(v + 0.3, i, str(v), va="center", fontsize=9)
        ax1.set_xlabel("Pipelines")
        ax1.set_title("Pipeline count by status", fontsize=11)
        ax1.invert_yaxis()
        ax1.margins(y=0.3)

    # Right: success vs failure grouped
    if ok_vals or fail_vals:
        x = range(len(labels))
        w = 0.35
        for i, (lb, ok, fl) in enumerate(zip(labels, ok_vals, fail_vals, strict=True)):
            ax2.bar(
                i - w / 2,
                ok,
                w,
                label="DAG success" if i == 0 else "",
                color="#2ecc71",
                edgecolor="white",
            )
            ax2.bar(
                i + w / 2,
                fl,
                w,
                label="Empty DAG" if i == 0 else "",
                color="#e74c3c",
                edgecolor="white",
            )
            ax2.text(i - w / 2, ok + 0.3, str(ok), ha="center", va="bottom", fontsize=8)
            if fl:
                ax2.text(
                    i + w / 2, fl + 0.3, str(fl), ha="center", va="bottom", fontsize=8
                )
        ax2.set_xticks(list(x))
        ax2.set_xticklabels(labels, fontsize=10)
        ax2.set_ylabel("Pipelines")
        ax2.set_title("DAG success vs failure by status", fontsize=11)
        ax2.legend(fontsize=8)
        ax2.margins(y=0.2)

    plt.tight_layout()
    fig.savefig(
        os.path.join(plot_dir, "pipeline_status.png"), dpi=150, bbox_inches="tight"
    )
    plt.close(fig)
