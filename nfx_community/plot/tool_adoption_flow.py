from collections import Counter

import matplotlib.pyplot as plt
import numpy as np

from ._colors import C_EXACT, C_MID


def plot_tool_adoption_flow(data, output_dir, name, **kargs):
    tool_flows = {}
    for r in data["module_analysis"]["repos"]:
        for e in r.get("nfcore_tool_evidence", []):
            tool = e[3].lower()
            etype = e[4]
            tool_flows.setdefault(tool, Counter())[etype] += 1

    top15 = sorted(tool_flows.items(), key=lambda x: -sum(x[1].values()))[:15]
    if not top15:
        print("    No tool flow data.")
        return

    labels = [t[0] for t in top15]
    exact_vals = [t[1].get("exact", 0) for t in top15]
    metric_vals = [t[1].get("metric", 0) for t in top15]

    fig, ax = plt.subplots(figsize=(12, 8))
    y_pos = np.arange(len(labels))
    bar_height = 0.3

    ax.barh(
        y_pos, exact_vals, bar_height, color=C_EXACT, label="Exact", edgecolor="white"
    )
    ax.barh(
        y_pos + bar_height,
        metric_vals,
        bar_height,
        color=C_MID,
        label="Metric (no exact name match)",
        edgecolor="white",
    )

    ax.set_yticks(y_pos + bar_height / 2)
    ax.set_yticklabels(labels)
    ax.set_xlabel("Number of evidence entries")
    ax.set_title("Top 15 Tools — Adoption Flow (Exact vs Metric)")
    ax.legend(loc="lower right")
    ax.invert_yaxis()

    fig.tight_layout()
    fig.savefig(output_dir / f"{name}.pdf", dpi=150)
    plt.close(fig)
    print(f"    Saved {name}.pdf — {len(labels)} tools")
