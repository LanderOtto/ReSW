import matplotlib.pyplot as plt
import numpy as np

from . import integer_percentages
from ._colors import C_HIGH, C_LOW, C_MID


def plot_score_distribution(data, output_dir, name, **kargs):
    all_evidence = _collect_evidence(data)
    exact_scores = [e[5] for e in all_evidence if e[4] == "exact" and e[5] is not None]
    if not exact_scores:
        print("    No exact scores to plot.")
        return

    fig, ax = plt.subplots(figsize=(10, 6))
    bins = np.arange(0, 1.05, 0.05)
    n, bin_edges, patches = ax.hist(
        exact_scores, bins=bins, edgecolor="white", linewidth=0.5
    )

    for i, p in enumerate(patches):
        center = (bin_edges[i] + bin_edges[i + 1]) / 2
        if center < 0.4:
            p.set_facecolor(C_LOW)
        elif center < 0.7:
            p.set_facecolor(C_MID)
        else:
            p.set_facecolor(C_HIGH)

    high = sum(1 for s in exact_scores if s >= 0.7)
    mid = sum(1 for s in exact_scores if 0.4 <= s < 0.7)
    low = sum(1 for s in exact_scores if s < 0.4)

    ax.axvline(
        0.4, color=C_LOW, linestyle="--", alpha=0.5, label=f"Near nf-core <0.4 ({low})"
    )
    ax.axvline(
        0.7,
        color=C_HIGH,
        linestyle="--",
        alpha=0.5,
        label=f"Heavily custom >=0.7 ({high})",
    )
    ax.set_xlabel("RMS (Reusability Miss Score)")
    ax.set_ylabel("Number of matches")
    ax.set_title("RMS Distribution — nf-core Module Matches")
    ax.legend(loc="upper right")
    ax.set_xlim(0, 1)

    ymax = ax.get_ylim()[1]
    low_p, mid_p, high_p = integer_percentages([low, mid, high], len(exact_scores))
    ax.text(
        0.15,
        ymax * 0.9,
        f"Near nf-core\n{low} ({low_p}%)",
        ha="center",
        color=C_LOW,
        fontweight="bold",
    )
    ax.text(
        0.55,
        ymax * 0.9,
        f"Partial match\n{mid} ({mid_p}%)",
        ha="center",
        color=C_MID,
        fontweight="bold",
    )
    ax.text(
        0.85,
        ymax * 0.9,
        f"Heavily custom\n{high} ({high_p}%)",
        ha="center",
        color=C_HIGH,
        fontweight="bold",
    )

    fig.tight_layout()
    fig.savefig(output_dir / f"{name}.pdf", dpi=150)
    plt.close(fig)
    print(f"    Saved {name}.pdf — {len(exact_scores)} scores")


def _collect_evidence(data):
    evidence = []
    for r in data["module_analysis"]["repos"]:
        for e in r.get("nfcore_tool_evidence", []):
            evidence.append(e)
    return evidence
