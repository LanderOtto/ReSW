from collections import Counter

import matplotlib.pyplot as plt

from ._colors import C_EXACT


def plot_community_orgs(data, output_dir, name, **kargs):
    """Community organisations: pipelines per org (top-15) + average."""
    repos = data["module_analysis"].get("repos") or []
    orgs = Counter(r["full_name"].split("/")[0] for r in repos)
    if not orgs:
        print("    No repo/organisation data; skipping community-org plot.")
        return
    n_orgs = len(orgs)
    n_pipelines = sum(orgs.values())
    avg = n_pipelines / n_orgs if n_orgs else 0.0
    top = orgs.most_common(15)

    names = [o for o, _ in top][::-1]
    counts = [c for _, c in top][::-1]
    fig, ax = plt.subplots(figsize=(10, 7))
    bars = ax.barh(range(len(names)), counts, color=C_EXACT, edgecolor="white")
    ax.set_yticks(range(len(names)))
    ax.set_yticklabels(names, fontsize=16)
    ax.set_xlabel("pipelines (GitHub search, community orgs)")
    ax.set_title(
        f"Community organisations by pipeline count "
        f"({n_orgs} orgs, {n_pipelines} pipelines, "
        f"avg {avg:.2f}/org)"
    )
    ax.invert_yaxis()
    for b, c in zip(bars, counts):
        ax.text(
            b.get_width() + 0.02 * max(counts),
            b.get_y() + b.get_height() / 2,
            str(c),
            va="center",
            fontsize=16,
        )
    ax.grid(axis="x", alpha=0.3)
    fig.tight_layout()
    fig.savefig(output_dir / f"{name}.pdf", dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(
        f"    Saved {name}.pdf - {n_orgs} orgs, {n_pipelines} pipelines, "
        f"avg {avg:.2f}"
    )
