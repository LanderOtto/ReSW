import matplotlib.pyplot as plt

from . import integer_percentages
from ._colors import C_EXACT, C_LOW, C_MID


def plot_nfcore_adoption_per_process_horizontal_v07_1(data, output_dir, name, **kargs):
    repos = data["module_analysis"]["repos"]

    exact_entries = 0
    metric_entries = 0

    for r in repos:
        ev = r.get("nfcore_tool_evidence", [])
        exact_entries += sum(1 for e in ev if e[4] == "exact")
        metric_entries += sum(1 for e in ev if e[4] == "metric")

    total = exact_entries + metric_entries

    segments = [
        (exact_entries, C_EXACT, "Process matches an\nnf-core module"),
        (metric_entries, C_LOW, "Process does not\nmatch nf-core"),
    ]
    fig, ax = plt.subplots(figsize=(10, 4))

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
    ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.15), ncol=3, fontsize=14)
    ax.spines[:].set_visible(False)

    fig.tight_layout()
    fig.savefig(output_dir / f"{name}.pdf", dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(
        f"    Saved {name}.pdf - "
        f"{total} total processes ({exact_entries} match an nf-core "
        f"module, {metric_entries} do not)"
    )
