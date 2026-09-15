import matplotlib.pyplot as plt

from . import integer_percentages
from ._colors import C_EXACT, C_LOW, C_MID


def plot_nfcore_adoption_horizontal(data, output_dir, name, **kargs):
    repos = data["module_analysis"]["repos"]

    formal = 0
    name_only = 0
    zero_evidence = 0

    for r in repos:
        uses_nfcore = r.get("uses_nfcore", False)
        if not uses_nfcore:
            style = r.get("module_style", "")
            uses_nfcore = style.startswith("nf-core")
        if uses_nfcore:
            formal += 1
        elif r.get("nfcore_tool_evidence"):
            name_only += 1
        else:
            zero_evidence += 1

    total = formal + name_only + zero_evidence

    segments = [
        (formal, C_EXACT, "Formal nf-core adoption"),
        (name_only, C_MID, "No nf-core modules:\nPotential candidate"),
        (zero_evidence, C_LOW, "No nf-core modules:\nZero evidance"),
    ]

    fig, ax = plt.subplots(figsize=(10, 2.5))

    left = 0.0
    pcts = integer_percentages([count for count, _, _ in segments], total)
    for idx, (count, color, label) in enumerate(segments):
        width = count / total if total else 0
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
    ax.set_title(
        "nf-core Module Adoption Across Community Pipelines",
        fontsize=13,
        fontweight="bold",
        pad=15,
    )
    ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.15), ncol=3, fontsize=14)
    ax.spines[:].set_visible(False)

    fig.tight_layout()
    fig.savefig(output_dir / f"{name}.pdf", dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"    Saved {name}.pdf - {total} repos")
