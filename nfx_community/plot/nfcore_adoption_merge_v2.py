import matplotlib.pyplot as plt

from ._colors import C_EXACT, C_HIGH, C_LOW, C_MID

MAX_FONTSIZE = 22


def plot_nfcore_adoption_merge_v2(data, output_dir, name, **kargs):
    repos = data["module_analysis"]["repos"]

    exact_entries = 0
    metric_high = 0
    metric_mid = 0
    metric_low = 0

    # Calculate metrics
    for r in repos:
        for e in r.get("nfcore_tool_evidence", []):
            if e[4] == "exact":
                exact_entries += 1
            elif e[4] == "metric":
                score = e[5] if e[5] is not None else 0.0
                if score >= 0.9:
                    metric_high += 1
                elif score >= 0.5:
                    metric_mid += 1
                else:
                    metric_low += 1

    metric_entries = metric_high + metric_mid + metric_low
    total = exact_entries + metric_entries

    # Define segments for both bars
    segments_overall = [
        (exact_entries, C_EXACT, "Uses nf-core"),
        (metric_entries, "grey", "Does not\nuse nf-core"),
    ]

    segments_detailed = [
        (exact_entries, C_EXACT, "Uses nf-core"),
        (metric_high, C_HIGH, "High RMS >= 0.9\n(easily replaceable)"),
        (metric_mid, C_MID, "Mid RMS 0.5–0.9\n(refactoring needed)"),
        (metric_low, C_LOW, "Low RMS < 0.5\n(custom tools)"),
    ]

    # Increase height slightly to fit both bars comfortably
    fig, ax = plt.subplots(figsize=(10, 4.5))

    bar_height = 0.8

    # Plot Top Bar: Overall (2 categories)
    # left = 0.0
    # for count, color, label in segments_overall:
    #     width = count / total if total > 0 else 0
    #     ax.barh(1, width, left=left, color=color, edgecolor="white",
    #             height=bar_height, label=label)
    #     if count:
    #         cx = left + width / 2
    #         ax.text(cx, 1, f"{count}\n({count/total*100:.0f}%)",
    #                 ha="center", va="center", fontsize=MAX_FONTSIZE-2, fontweight="bold",
    #                 color="white")
    #     left += width

    # Plot Bottom Bar: Detailed (4 categories)
    left = 0.0
    for count, color, label in segments_detailed:
        width = count / total if total > 0 else 0
        ax.barh(
            0,
            width,
            left=left,
            color=color,
            edgecolor="white",
            height=bar_height,
            label=label,
        )
        if count:
            cx = left + width / 2
            ax.text(
                cx,
                0,
                f"{count}\n({count/total*100:.0f}%)",
                ha="center",
                va="center",
                fontsize=MAX_FONTSIZE - 2,
                fontweight="bold",
                color="white",
            )
        left += width

    # ax.text(
    #     0.5,
    #     -0.7,
    #     "(a) No-heuristics      (b) with RMS",
    #     fontsize=MAX_FONTSIZE,
    #     ha="center",
    #     va="center"
    # )

    # Axes styling
    ax.set_xlim(0, 1)
    ax.set_ylim(-0.6, 1.6)

    # Label the two bars on the Y-axis
    ax.set_yticks([0, 1])
    # (a) No-heuristics
    # (b) with RMS
    ax.set_yticklabels([], fontsize=MAX_FONTSIZE - 2, fontweight="bold")
    ax.tick_params(axis="y", length=0)  # Hide the actual tick marks
    ax.set_xticks([])

    # Clean up legend to avoid duplicate "Uses nf-core" entries
    handles, labels = ax.get_legend_handles_labels()
    by_label = dict(zip(labels, handles))
    ax.legend(
        by_label.values(),
        by_label.keys(),
        loc="upper center",
        bbox_to_anchor=(0.5, -0.15),
        ncol=2,
        fontsize=MAX_FONTSIZE,
    )

    ax.spines[:].set_visible(False)

    fig.tight_layout()
    fig.savefig(output_dir / f"{name}.pdf", dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(
        f"    Saved {name}.pdf - "
        f"{total} total processes ({exact_entries} exact, "
        f"{metric_high} replaceable, {metric_mid} refactoring, {metric_low} custom)"
    )
