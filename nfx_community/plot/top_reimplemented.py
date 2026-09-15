from collections import Counter

import matplotlib.pyplot as plt

from ._colors import C_LOW


def plot_top_reimplemented(data, output_dir, name, **kargs):
    reimp = Counter()
    for r in data["module_analysis"]["repos"]:
        for m in r.get("reimplemented_modules", []):
            reimp[m] += 1
    top = reimp.most_common(20)
    if not top:
        print("    No reimplementation data.")
        return

    names = []
    for t in top:
        n = t[0].split("/")[-1] if "/" in t[0] else t[0]
        names.append(n[:25] + "..." if len(n) > 25 else n)
    counts = [t[1] for t in top]

    fig, ax = plt.subplots(figsize=(10, 8))
    bars = ax.barh(range(len(names)), counts, color=C_LOW, edgecolor="white")
    ax.set_yticks(range(len(names)))
    ax.set_yticklabels(names)
    ax.set_xlabel("Number of repos reimplementing this module")
    ax.set_title("Top 20 Most Frequently Reimplemented nf-core Modules")
    ax.invert_yaxis()

    for bar, cnt in zip(bars, counts):
        ax.text(
            bar.get_width() + 0.3,
            bar.get_y() + bar.get_height() / 2,
            str(cnt),
            va="center",
            fontsize=9,
        )

    fig.tight_layout()
    fig.savefig(output_dir / f"{name}.pdf", dpi=150)
    plt.close(fig)
    print(f"    Saved {name}.pdf — {len(top)} modules")
