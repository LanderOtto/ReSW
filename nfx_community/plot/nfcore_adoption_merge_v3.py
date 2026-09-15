import matplotlib.pyplot as plt

from . import integer_percentages
from ._colors import C_DARK, C_EXACT, C_HIGH, C_LOW, C_MID

MAX_FONT_SIZE = 24


def plot_nfcore_adoption_merge_v3(data, output_dir, name, **kargs):
    repos = data["module_analysis"]["repos"]

    exact_entries = 0
    metric_high = 0
    metric_mid = 0
    metric_low = 0
    metric_very_low = 0

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
                elif score >= 0.1:
                    metric_low += 1
                else:
                    metric_very_low += 1

    metric_entries = metric_high + metric_mid + metric_low + metric_very_low
    total = exact_entries + metric_entries

    # Define segments for both bars
    segments_overall = [
        (exact_entries, C_EXACT, "Uses nf-core"),
        (metric_entries, "grey", "Does not use nf-core"),
    ]

    segments_detailed = [
        (exact_entries, C_EXACT, "Uses nf-core"),
        (metric_high, C_HIGH, "High MRS ≥ 0.9\n(easily replaceable)"),
        (metric_mid, C_MID, "Mid MRS 0.5–0.9\n(refactoring needed)"),
        (metric_low, C_LOW, "Low MRS 0.1–0.5\n(custom tools)"),
        (metric_very_low, C_DARK, "Very low MRS < 0.1\n(real custom)"),
    ]

    # CHANGED: Increased figure width to 22 to make bars match/exceed legend width
    fig, ax = plt.subplots(figsize=(16, 8))

    # Plot Top Bar: Overall (2 categories)
    pcts_overall = integer_percentages(
        [count for count, _, _ in segments_overall], total
    )
    left = 0.0
    for idx, (count, color, label) in enumerate(segments_overall):
        width = count / total if total > 0 else 0
        ax.barh(
            1, width, left=left, color=color, edgecolor="white", height=0.8, label=label
        )
        if count:
            cx = left + width / 2
            # CHANGED: Increased font size inside the bar
            ax.text(
                cx,
                1,
                f"{count}\n({pcts_overall[idx]}%)",
                ha="center",
                va="center",
                fontsize=MAX_FONT_SIZE + 4,
                fontweight="bold",
                color="white",
            )
        left += width

    # Plot Bottom Bar: Detailed (4 categories)
    pcts_detailed = integer_percentages(
        [count for count, _, _ in segments_detailed], total
    )
    left = 0.0
    for idx, (count, color, label) in enumerate(segments_detailed):
        width = count / total if total > 0 else 0
        ax.barh(
            0, width, left=left, color=color, edgecolor="white", height=0.8, label=label
        )
        if count:
            cx = left + width / 2
            # CHANGED: Increased font size inside the bar
            ax.text(
                cx,
                0,
                f"{count}\n({pcts_detailed[idx]}%)",
                ha="center",
                va="center",
                fontsize=MAX_FONT_SIZE + 8,
                fontweight="bold",
                color="white",
            )
        left += width

    ax.text(
        0.5,
        -0.7,
        "(a) No-heuristics      (b) with MRS",
        fontsize=MAX_FONT_SIZE,
        ha="center",
        va="center",
    )

    # Axes styling
    ax.set_xlim(0, 1)
    ax.set_ylim(-0.6, 1.6)

    # Label the two bars on the Y-axis
    ax.set_yticks([0, 1])
    ax.set_yticklabels(["(b)", "(a)"], fontsize=MAX_FONT_SIZE - 2, fontweight="bold")
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
        ncol=3,
        fontsize=MAX_FONT_SIZE,
    )

    ax.spines[:].set_visible(False)

    fig.tight_layout()
    fig.savefig(output_dir / f"{name}.pdf", dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(
        f"    Saved {name}.pdf - "
        f"{total} total processes ({exact_entries} exact, "
        f"{metric_high} replaceable, {metric_mid} refactoring, "
        f"{metric_low} 0.1-0.5, {metric_very_low} <0.1)"
    )
