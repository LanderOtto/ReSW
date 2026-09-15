import matplotlib.pyplot as plt

from ._colors import C_EXACT, C_MID


def plot_nfcore_module_tools(data, output_dir, name, **kargs):
    """Two-panel chart: tools per nf-core module and top declared tools.

    Reads ``module_analysis.nfcore_module_tools``. Left: distribution of
    modules by number of declared tools. Right: top tools by module count
    (declared ``val('tool')`` from ``emit: versions_*`` output channels).
    """
    mt = (data.get("module_analysis", {}) or {}).get("nfcore_module_tools") or {}
    if not mt.get("modules_total"):
        print("    No nf-core module tool data to plot.")
        return

    dist = {int(k): v for k, v in (mt.get("by_n_declared") or {}).items()}
    top = (mt.get("top_declared_tools") or [])[:20]
    if not dist and not top:
        print("    No declared tool data to plot.")
        return

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(15, 7))

    if dist:
        xs = sorted(dist)
        ys = [dist[x] for x in xs]
        ax1.bar(xs, ys, color=C_EXACT, edgecolor="white", width=0.7)
        ax1.set_xlabel("declared tools per module")
        ax1.set_ylabel("modules")
        ax1.set_xticks(xs)
        ax1.set_title("Tools per nf-core module (declared)", fontsize=12)
        for x, y in zip(xs, ys):
            if y:
                ax1.text(x, y, f" {y}", ha="center", va="bottom", fontsize=10)

    if top:
        tools = [t for t, _ in top][::-1]
        vals = [c for _, c in top][::-1]
        ax2.barh(tools, vals, color=C_MID, edgecolor="white", height=0.7)
        ax2.set_xlabel("modules using the tool")
        ax2.set_title("Top declared tools in nf-core modules", fontsize=12)
        for yi, v in zip(range(len(vals)), vals):
            if v:
                ax2.text(v, yi, f" {v}", va="center", fontsize=10)

    fig.suptitle(
        "nf-core module tool usage " f"(N = {mt['modules_total']} modules)",
        fontsize=13,
        fontweight="bold",
    )
    fig.tight_layout()
    fig.savefig(output_dir / f"{name}.pdf", dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(
        f"    Saved {name}.pdf - {mt['modules_total']} modules, "
        f"{mt['with_declared_tools']} declaring tools"
    )
