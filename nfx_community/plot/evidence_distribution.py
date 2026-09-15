from collections import Counter

import matplotlib.pyplot as plt
import numpy as np

from ._colors import C_EXACT, C_MID


def _has_nfcore_style(style):
    return style.startswith("nf-core")


def plot_evidence_distribution(data, output_dir, name, **kargs):
    repos = data["module_analysis"]["repos"]

    kind_counts = Counter()
    style_kind = {}

    for r in repos:
        style = r.get("module_style", "unknown")
        for e in r.get("nfcore_tool_evidence", []):
            ek = e[4] if _has_nfcore_style(style) else "metric"
            kind_counts[ek] += 1
            style_kind.setdefault(style, Counter())[ek] += 1

    total = sum(kind_counts.values())
    if not kind_counts:
        print("    No evidence data.")
        return

    label_map = {"exact": "Exact match", "metric": "Metric (no exact name match)"}
    labels_plot = [label_map.get(t, t) for t in kind_counts.keys()]
    values = [kind_counts[t] for t in kind_counts.keys()]
    colors_plot = [C_EXACT if t == "exact" else C_MID for t in kind_counts.keys()]

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 5))

    wedges, texts, autotexts = ax1.pie(
        values,
        labels=labels_plot,
        colors=colors_plot,
        autopct="%1.1f%%",
        startangle=90,
        textprops=dict(fontsize=10),
    )
    for at in autotexts:
        at.set_fontweight("bold")
    ax1.set_title("Evidence Type Distribution")

    styles_bar = sorted(s for s in style_kind if sum(style_kind[s].values()) >= 5)
    if not styles_bar:
        styles_bar = sorted(style_kind.keys())

    bar_labels = [s.replace("+", " +\n") for s in styles_bar]
    x = np.arange(len(styles_bar))
    width = 0.6

    bottoms = np.zeros(len(styles_bar))
    for etype, color, label in [
        ("exact", C_EXACT, "Exact"),
        ("metric", C_MID, "Metric"),
    ]:
        vals = [style_kind[s].get(etype, 0) for s in styles_bar]
        ax2.bar(
            x, vals, width, bottom=bottoms, color=color, label=label, edgecolor="white"
        )
        bottoms += vals

    ax2.set_xticks(x)
    ax2.set_xticklabels(bar_labels, fontsize=8)
    ax2.set_ylabel("Number of evidence entries")
    ax2.set_title("Evidence Type by Repository Module Style")
    ax2.legend(fontsize=9)

    fig.tight_layout()
    fig.savefig(output_dir / f"{name}.pdf", dpi=150)
    plt.close(fig)
    print(f"    Saved {name}.pdf - {total} entries")
