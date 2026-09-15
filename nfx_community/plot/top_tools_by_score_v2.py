from collections import Counter

import matplotlib.pyplot as plt

from nfx_community.nfcore_tools.parsing import _BUILTINS

from ._colors import C_HIGH, C_LOW


def _get_nfcore_bases(data):
    bases = set()
    for r in data["module_analysis"]["repos"]:
        for e in r.get("nfcore_tool_evidence", []):
            if e[4] == "exact":
                bases.add(e[3].lower())
    return bases


FONTSIZE = 26


def add_inner_ylabel(
    fig, ax, renderer, names, counts, fontsize, size_limit=14, offset=1
):
    for i, (nm, c) in enumerate(zip(names, counts)):
        t = ax.text(
            c - 3, i, nm, va="center", ha="right", fontsize=fontsize, fontweight="bold"
        )
        bb = t.get_window_extent(renderer)
        (x0, _), _ = ax.transData.inverted().transform([(bb.x0, bb.y0), (bb.x1, bb.y1)])
        size = t.get_fontsize()
        while x0 < 0 and size > size_limit:
            size -= 0.5
            t.set_fontsize(size)
            fig.canvas.draw()
            bb = t.get_window_extent(renderer)
            (x0, _), _ = ax.transData.inverted().transform(
                [(bb.x0, bb.y0), (bb.x1, bb.y1)]
            )
        if size <= size_limit:
            t.set_position((c + offset, i))  # Shift past the bar end
            t.set_ha("left")  # Anchor left so text flows outward
            t.set_fontsize(size_limit)  # Reset to a readable size
            t.set_color("black")
        else:
            t.set_color("white")


def plot_top_tools_by_score_v2(data, output_dir, name, **kargs):
    repos = data["module_analysis"]["repos"]
    nfcore_bases = _get_nfcore_bases(data)

    high = Counter()
    low = Counter()

    for r in repos:
        for e in r.get("nfcore_tool_evidence", []):
            if e[4] != "metric":
                continue
            score = e[5] if e[5] is not None else 0.0
            comp = e[6] if len(e) > 6 else {}
            seen = set()
            for t in comp.get("tool_cmds_fullname", comp.get("tool_cmds", [])):
                tl = t.lower()
                if tl in _BUILTINS:
                    continue
                if tl in seen:
                    continue
                seen.add(tl)
                if score >= 0.5:
                    high[tl] += 1
            if score < 0.5:
                seen2 = set()
                for t in comp.get("tool_cmds", []):
                    tl = t.lower()
                    if tl in _BUILTINS:
                        continue
                    if tl in seen2:
                        continue
                    seen2.add(tl)
                    if tl not in nfcore_bases:
                        low[tl] += 1

    top_k = 10
    top_high = high.most_common(top_k)
    top_low = low.most_common(top_k)

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(15, 8))

    fig.suptitle(
        f"Top {top_k} tools used in process steps based on the MRS", fontsize=FONTSIZE
    )

    fig.canvas.draw()
    renderer = fig.canvas.get_renderer()

    # --- Left panel: score >= 0.5, all tools ---
    if top_high:
        labels_h = []
        for tool_name, cnt in top_high:
            labels_h.append(tool_name.replace("_", " ").title())
        counts_h = [t[1] for t in top_high]
        bars1 = ax1.barh(
            range(len(labels_h)), counts_h, color=C_HIGH, edgecolor="white"
        )
        # ax1.set_yticks(range(len(labels_h)))
        # ax1.set_yticklabels(labels_h, fontsize=16)
        ax1.set_yticklabels([])
        ax1.set_xlabel("Process steps with the tool", fontsize=FONTSIZE)
        ax1.tick_params(axis="x", labelsize=FONTSIZE)
        # ax1.set_title(
        #     f"Top {top_k} tools used in processes with the highest MRS\n(score \u2265 0.5)",
        #     fontsize=20
        # )
        # ax1.set_title(
        #     f"MRS \u2265 0.5",
        #     fontsize=22
        # )
        ax1.invert_yaxis()

        add_inner_ylabel(fig, ax1, renderer, labels_h, counts_h, fontsize=FONTSIZE)

        ax1.grid(axis="x", alpha=0.3)
        ax1.text(
            0.95,
            0.05,
            "MRS \u2265 0.5",
            transform=ax1.transAxes,
            ha="right",
            va="bottom",
            fontsize=36,
            color=C_HIGH,
            fontweight="bold",
        )

        # for bar, cnt in zip(bars1, counts_h):
        #     ax1.text(bar.get_width() + 0.2, bar.get_y() + bar.get_height() / 2,
        #              str(cnt), va="center", fontsize=14)
    else:
        ax1.text(0.5, 0.5, "No data", ha="center", va="center", transform=ax1.transAxes)
        ax1.set_title(
            "Heavily customized processes\n(score \u2265 0.5)", fontsize=FONTSIZE
        )

    # --- Right panel: score < 0.5, non-nf-core tools only ---
    if top_low:
        labels_l = []
        for tool_name, cnt in top_low:
            labels_l.append(tool_name.replace("_", " ").title())
        counts_l = [t[1] for t in top_low]
        bars2 = ax2.barh(range(len(labels_l)), counts_l, color=C_LOW, edgecolor="white")
        # ax2.set_yticks(range(len(labels_l)))
        # ax2.set_yticklabels(labels_l, fontsize=14)
        ax2.set_yticklabels([])
        ax2.set_xlabel("Process steps with the tool", fontsize=FONTSIZE)
        ax2.tick_params(axis="x", labelsize=FONTSIZE)
        # ax2.set_title(
        #     f"Top {top_k} tools used in processes with the lowest MRS\n(score < 0.5)",
        #     fontsize=20
        # )
        # ax2.set_title(
        #     f"MRS < 0.5",
        #     fontsize=22
        # )
        ax2.invert_yaxis()
        ax2.grid(axis="x", alpha=0.3)

        add_inner_ylabel(fig, ax2, renderer, labels_l, counts_l, fontsize=FONTSIZE)

        ax2.text(
            0.95,
            0.05,
            "MRS < 0.5",
            transform=ax2.transAxes,
            ha="right",
            va="bottom",
            fontsize=36,
            color=C_LOW,
            fontweight="bold",
        )

        # for bar, cnt in zip(bars2, counts_l):
        #     ax2.text(bar.get_width() + 0.2, bar.get_y() + bar.get_height() / 2,
        #              str(cnt), va="center", fontsize=14)
    else:
        ax2.text(0.5, 0.5, "No data", ha="center", va="center", transform=ax2.transAxes)
        ax2.set_title(
            "Custom tools in nf-core-like processes\n(score < 0.5)", fontsize=FONTSIZE
        )

    fig.tight_layout()
    fig.savefig(output_dir / f"{name}.pdf", dpi=150)
    plt.close(fig)
    print(
        f"    Saved {name}.pdf — "
        f"{len(top_high)} high-score, {len(top_low)} low-score tools"
    )
