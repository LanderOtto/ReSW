from collections import Counter

import matplotlib.pyplot as plt
import numpy as np

from ._colors import C_HIGH, C_LOW, C_MID


def plot_infra_only_count(data, output_dir, name, **kargs):
    pipe_infra = Counter()
    infra_total = 0

    for r in data["module_analysis"]["repos"]:
        pipe = r["full_name"]
        for _ in r.get("nfcore_tool_infra_only", []):
            pipe_infra[pipe] += 1
            infra_total += 1

    top_n = 20
    top = pipe_infra.most_common(top_n)
    if not top:
        print("  No infra-only processes found.")
        return

    pipes = [p for p, _ in top]
    counts = [c for _, c in top]

    fig, ax = plt.subplots(figsize=(10, 8))

    y = np.arange(len(pipes))
    bars = ax.barh(
        y, counts, height=0.6, color=C_LOW, edgecolor="white", linewidth=0.5, zorder=3
    )

    for bar, c in zip(bars, counts):
        ax.text(
            bar.get_width() + max(counts) * 0.01,
            bar.get_y() + bar.get_height() / 2,
            str(c),
            ha="left",
            va="center",
            fontsize=10,
        )

    ax.set_yticks(y)
    ax.set_yticklabels(pipes, fontsize=10)
    ax.invert_yaxis()
    ax.set_xlabel("Infra-only processes", fontsize=12)
    ax.set_title(
        f"Pipelines with Most Infra-Only Processes\n({infra_total} total)", fontsize=13
    )
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.tick_params(axis="x", labelsize=11)

    fig.tight_layout()
    fig.savefig(output_dir / f"{name}.pdf", dpi=150)
    plt.close(fig)

    print(
        f"    Saved {name}.pdf — top {top_n} of {len(pipe_infra)} pipelines with infra-only processes"
    )
