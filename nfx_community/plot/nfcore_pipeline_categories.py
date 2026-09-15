from collections import Counter

import matplotlib.pyplot as plt
import numpy as np
from matplotlib.patches import Patch

from ._categories import (
    CATEGORY_META,
    OVERLAP_HATCH,
    RMS_CATEGORIZE_THRESHOLD,
    categorize,
)


def plot_pipeline_categories(data, output_dir, name, **kargs):
    repos = data["module_analysis"]["repos"]

    counts = Counter()
    pipeline_in_sim = []
    pipeline_out_sim = []

    for r in repos:
        repo_cats = set()
        repo_in_sim = []
        repo_out_sim = []
        for e in r.get("nfcore_tool_evidence", []):
            score = e[5] if len(e) > 5 else 0
            if score < RMS_CATEGORIZE_THRESHOLD:
                continue
            comp = e[6] if len(e) > 6 else None
            if not comp:
                continue
            cats = categorize(comp)
            repo_cats |= cats
            if "input_mismatch" in cats:
                repo_in_sim.append(comp.get("input_similarity", 1.0))
            if "output_mismatch" in cats:
                repo_out_sim.append(comp.get("output_similarity", 1.0))
        for c in repo_cats:
            counts[c] += 1
        if repo_in_sim:
            pipeline_in_sim.append(np.mean(repo_in_sim))
        if repo_out_sim:
            pipeline_out_sim.append(np.mean(repo_out_sim))

    avg_in_sim = np.mean(pipeline_in_sim) if pipeline_in_sim else None
    avg_out_sim = np.mean(pipeline_out_sim) if pipeline_out_sim else None

    values = []
    colors = []
    hatches = []
    for key, label, color, hatch in CATEGORY_META:
        values.append(counts.get(key, 0))
        colors.append(color)
        hatches.append(hatch)

    fig, ax = plt.subplots(figsize=(10, 6))
    x = np.arange(len(values))
    bars = ax.bar(x, values, color=colors, edgecolor="white", width=0.55)

    for bar, val, h in zip(bars, values, hatches):
        if h:
            bar.set_hatch(h)
        ax.text(
            bar.get_x() + bar.get_width() / 2,
            bar.get_height() + 4,
            str(val),
            ha="center",
            fontsize=16,
            fontweight="bold",
        )

    legend_elements = []
    for key, label, color, hatch in CATEGORY_META:
        extra = ""
        if key == "input_mismatch" and avg_in_sim is not None:
            extra = f"  -  input sim: {avg_in_sim:.2f}"
        elif key == "output_mismatch" and avg_out_sim is not None:
            extra = f"  -  output sim: {avg_out_sim:.2f}"
        legend_elements.append(
            Patch(facecolor=color, hatch=hatch, edgecolor="white", label=label + extra)
        )
    legend_elements.append(
        Patch(
            facecolor="lightgray",
            hatch=OVERLAP_HATCH,
            edgecolor="white",
            label="Overlapping categories",
        )
    )

    ax.set_xticks(x)
    ax.set_xticklabels([])
    ax.set_ylabel("Number of pipelines", fontsize=15)
    ax.set_ylim(0, max(values) * 1.18)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)

    ax.legend(
        handles=legend_elements,
        loc="upper center",
        bbox_to_anchor=(0.5, -0.08),
        ncol=2,
        fontsize=13,
        handlelength=1.5,
        handleheight=1.2,
        title="Categories",
        title_fontsize=15,
    )

    fig.subplots_adjust(bottom=0.18)
    fig.savefig(output_dir / f"{name}.pdf", dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(
        f"    Saved {name}.pdf — {sum(values)} category "
        f"assignments across {len(repos)} repos"
    )
