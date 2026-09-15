import matplotlib.pyplot as plt

from ._colors import C_EXACT
from ._common import _tool_module_process_usage


def pre15_nfcore_top_modules_by_process(data, output_dir, name, nfcore_modules):
    """Top-15 nf-core modules by number of *processes* invoking them (from per-
    process tool evidence), with module names drawn inside the bars (white) or,
    when the name is longer than the bar, just outside its tip (dark)."""
    repos = data["module_analysis"].get("repos") or []
    use = _tool_module_process_usage(repos, nfcore_modules)
    if not use:
        print("    No module-level process usage found; skipping plot.")
        return
    top = use.most_common(15)
    names = [f"{t}/{s}" if s else t for (t, s), _ in top][::-1]
    counts = [n for _, n in top][::-1]
    fig, ax = plt.subplots(figsize=(10, 7))
    ax.barh(range(len(names)), counts, color=C_EXACT, edgecolor="white")
    ax.set_yticks([])
    ax.set_yticklabels([])
    ax.set_ylim(-0.6, len(names) - 0.4)
    ax.set_xlim(0, 400)
    fig.canvas.draw()
    renderer = fig.canvas.get_renderer()
    for i, (nm, c) in enumerate(zip(names, counts)):
        t = ax.text(
            c - 3, i, nm, va="center", ha="right", fontsize=16, fontweight="bold"
        )
        bb = t.get_window_extent(renderer)
        (x0, _), _ = ax.transData.inverted().transform([(bb.x0, bb.y0), (bb.x1, bb.y1)])
        size = t.get_fontsize()
        while x0 < 0 and size > 6:
            size -= 0.5
            t.set_fontsize(size)
            fig.canvas.draw()
            bb = t.get_window_extent(renderer)
            (x0, _), _ = ax.transData.inverted().transform(
                [(bb.x0, bb.y0), (bb.x1, bb.y1)]
            )
        t.set_color("white")
    ax.set_xlabel("Process steps invoking the module")
    ax.set_title(f"Top {len(top)} nf-core modules in the community pipelines")
    ax.grid(axis="x", alpha=0.3)
    fig.tight_layout()
    fig.savefig(output_dir / f"{name}.pdf", dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(
        f"    Saved {name}.pdf - top {len(top)} modules, "
        f"{sum(use.values())} process invocations"
    )
