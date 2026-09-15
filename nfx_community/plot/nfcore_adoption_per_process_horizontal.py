import matplotlib.pyplot as plt

from . import integer_percentages
from ._colors import C_EXACT, C_LOW, C_MID


def plot_nfcore_adoption_per_process_horizontal(data, output_dir, name, **kargs):
    repos = data["module_analysis"]["repos"]

    formal_entries = 0
    candidate_entries = 0

    for r in repos:
        ev = r.get("nfcore_tool_evidence", [])
        uses_nfcore = r.get("uses_nfcore", None)
        if uses_nfcore is None:
            uses_nfcore = r.get("module_style", "").startswith("nf-core")
        if uses_nfcore:
            formal_entries += len(ev)
        elif ev:
            candidate_entries += len(ev)

    total = formal_entries + candidate_entries

    segments = [
        (formal_entries, C_EXACT, "Explicit nf-core\nmodule usage"),
        (candidate_entries, C_MID, "No nf-core modules:\nProcess name coincidence"),
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
    ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.15), ncol=3, fontsize=14)
    ax.spines[:].set_visible(False)

    fig.tight_layout()
    fig.savefig(output_dir / f"{name}.pdf", dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(
        f"    Saved {name}.pdf - "
        f"{total} evidence entries ({formal_entries} formal, "
        f"{candidate_entries} candidate)"
    )
