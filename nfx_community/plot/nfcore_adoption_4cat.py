import matplotlib.pyplot as plt

from . import integer_percentages
from ._colors import C_EXACT, C_HIGH, C_LOW, C_MID


def plot_nfcore_adoption_4cat(data, output_dir, name, **kargs):
    repos = data["module_analysis"]["repos"]

    exact_entries = 0
    metric_high = 0
    metric_mid = 0
    metric_low = 0

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

    total = exact_entries + metric_high + metric_mid + metric_low

    segments = [
        (exact_entries, C_EXACT, "Uses nf-core"),
        (metric_high, C_HIGH, "High RMS >= 0.9\n(easily replaceable)"),
        (metric_mid, C_MID, "Mid RMS 0.5\u20130.9\n(refactoring needed)"),
        (metric_low, C_LOW, "Low RMS < 0.5\n(custom tools)"),
    ]

    fig, ax = plt.subplots(figsize=(10, 2.5))

    left = 0.0
    pcts = integer_percentages([count for count, _, _ in segments], total)
    for idx, (count, color, label) in enumerate(segments):
        width = count / total
        ax.barh(
            0, width, left=left, color=color, edgecolor="white", height=0.6, label=label
        )
        if count:
            cx = left + width / 2
            ax.text(
                cx,
                0,
                f"{count}\n({pcts[idx]}%)",
                ha="center",
                va="center",
                fontsize=14,
                fontweight="bold",
                color="white",
            )
        left += width

    ax.set_xlim(0, 1)
    ax.set_ylim(-0.8, 0.8)
    ax.set_yticks([])
    ax.set_xticks([])
    ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.15), ncol=4, fontsize=12)
    ax.spines[:].set_visible(False)

    fig.tight_layout()
    fig.savefig(output_dir / f"{name}.pdf", dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(
        f"    Saved {name}.pdf - "
        f"{total} total processes ({exact_entries} exact, "
        f"{metric_high} replaceable, {metric_mid} refactoring, {metric_low} custom)"
    )
