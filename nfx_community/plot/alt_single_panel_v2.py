from pathlib import Path

import matplotlib.patheffects as path_effects
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.patches import Patch

from ._colors import C_HIGH, C_LOW, C_MID

BUCKET_COLORS = [C_LOW, "#d35400", "#e67e22", "#f1c40f", "#2ecc71", C_HIGH]
BUCKET_HATCHES = ["", "\\\\", "..", "xx", "++", ""]
BUCKET_LABELS = [
    "0% nf-core",
    "<25% nf-core",
    "25\u201350% nf-core",
    "50\u201375% nf-core",
    "75\u201399% nf-core",
    "100% nf-core",
]

RIGHT_AXIS_COLOR = "#2980b9"


def _get_nfcore_bases(data, nfcore_modules):
    if nfcore_modules.exists():
        return {
            line.strip().lower()
            for line in nfcore_modules.read_text().splitlines()
            if line.strip()
        }
    bases = set()
    for r in data["module_analysis"]["repos"]:
        for e in r.get("nfcore_tool_evidence", []):
            if e[4] == "exact":
                bases.add(e[3].lower())
    return bases


def _round_pcts(vals, total):
    total = max(1, total)
    pcts = [round(100 * v / total) for v in vals]
    diff = 100 - sum(pcts)
    if diff != 0:
        i = max(range(len(pcts)), key=lambda i: pcts[i])
        pcts[i] += diff
    assert sum(pcts) == 100
    return pcts


MAX_FONTSIZE = 22


def _ratio_bucket(ratio):
    if ratio == 0.0:
        return 0
    if ratio < 0.25:
        return 1
    if ratio < 0.5:
        return 2
    if ratio < 0.75:
        return 3
    if ratio < 1.0:
        return 4
    return 5


def plot_tool_single_panel_v2(data, output_dir, name, nfcore_modules):
    if isinstance(output_dir, str):
        output_dir = Path(output_dir)
    repos = data["module_analysis"]["repos"]
    nfcore_bases = _get_nfcore_bases(data, nfcore_modules)

    single_custom = 0
    single_nfcore = 0
    multi_buckets = [0, 0, 0, 0, 0, 0]
    multi_tool_counts = []

    for r in repos:
        for e in r.get("nfcore_tool_evidence", []):
            if e[4] != "metric":
                continue
            comp = e[6] if len(e) > 6 else {}
            tools = comp.get("tool_cmds", [])
            stripped = [t.split("/")[0].lower() for t in tools if t]
            n = len(stripped)
            if n == 0:
                continue
            has_nf = any(t in nfcore_bases for t in stripped)
            n_nf = sum(1 for t in stripped if t in nfcore_bases)
            if n == 1:
                if has_nf:
                    single_nfcore += 1
                else:
                    single_custom += 1
            else:
                ratio = n_nf / n
                multi_tool_counts.append(n)
                multi_buckets[_ratio_bucket(ratio)] += 1

    total_single = single_custom + single_nfcore
    total_multi = sum(multi_buckets)
    total = total_single + total_multi
    assert (
        total_single == single_custom + single_nfcore
    ), f"single custom {single_custom} + nfcore {single_nfcore} != total {total_single}"
    assert total_multi == sum(
        multi_buckets
    ), f"multi buckets sum {sum(multi_buckets)} != total {total_multi}"

    multi_tools_arr = (
        np.array(multi_tool_counts) if multi_tool_counts else np.array([0.0])
    )
    mean_multi = np.mean(multi_tools_arr) if len(multi_tools_arr) > 0 else 0.0
    std_multi = np.std(multi_tools_arr) if len(multi_tools_arr) > 0 else 0.0

    fig, ax_left = plt.subplots(figsize=(10, 6))
    ax_right = ax_left.twinx()

    x = np.arange(2)
    bar_width = 0.55

    # ── Light blue background for multi-tool area ──
    ax_left.axvspan(0.5, 1.5, color=RIGHT_AXIS_COLOR, alpha=0.1, zorder=0)
    ax_left.set_xlim(-0.475, 1.475)

    # ── Left axis: single-tool bar ──
    ax_left.bar(
        x[0],
        total_single,
        width=bar_width,
        color="#7f8c8d",
        edgecolor="white",
        linewidth=1.2,
        zorder=3,
    )
    ax_left.bar(
        x[0],
        single_custom,
        width=bar_width,
        color=C_LOW,
        edgecolor="white",
        linewidth=0.5,
        zorder=3,
    )
    ax_left.bar(
        x[0],
        single_nfcore,
        width=bar_width,
        color=C_HIGH,
        bottom=single_custom,
        edgecolor="white",
        linewidth=0.5,
        zorder=3,
    )

    # ── Right axis: multi-tool bar (6 buckets) ──
    ax_right.bar(
        x[1],
        total_multi,
        width=bar_width,
        color="#7f8c8d",
        edgecolor="white",
        linewidth=1.2,
        zorder=3,
    )
    cum = 0
    for i in range(6):
        v = multi_buckets[i]
        if v == 0:
            continue
        lbl = None if i in (0, 5) else BUCKET_LABELS[i]
        kw = dict(
            width=bar_width,
            color=BUCKET_COLORS[i],
            edgecolor="white",
            linewidth=0.5,
            zorder=3,
            label=lbl,
        )
        if BUCKET_HATCHES[i]:
            kw["hatch"] = BUCKET_HATCHES[i]
        ax_right.bar(x[1], v, bottom=cum, **kw)
        cum += v

    # ── Annotations (white text with black stroke for readability on hatches) ──
    def _annotate_stack(ax, xi, vals, bar_total, colors):
        cum = 0
        pcts = _round_pcts(vals, bar_total)
        for idx, v in enumerate(vals):
            if v > 0:
                # label = f"{v} ({pcts[idx]}%)"
                label = f"{pcts[idx]}%"
                y = cum + v / 2
                ax.text(
                    xi,
                    y,
                    label,
                    ha="center",
                    va="center",
                    fontsize=MAX_FONTSIZE - 2,
                    fontweight="bold",
                    color="white",
                    path_effects=[
                        path_effects.withStroke(linewidth=2, foreground="black")
                    ],
                )
            cum += v

    _annotate_stack(
        ax_left, x[0], [single_custom, single_nfcore], total_single, [C_LOW, C_HIGH]
    )
    _annotate_stack(ax_right, x[1], multi_buckets, total_multi, BUCKET_COLORS)

    # ── Axis styling ──
    ax_left.set_xticks(x)
    ax_left.set_xticklabels(
        [f"Single-tool\nn={total_single}", f"Multi-tool\nn={total_multi}"],
        fontsize=MAX_FONTSIZE - 2,
    )
    ax_left.set_ylabel("Step scripts", fontsize=MAX_FONTSIZE)
    ax_left.tick_params(axis="y", labelsize=MAX_FONTSIZE - 2)
    ax_left.spines["top"].set_visible(False)

    ax_right.set_ylabel(
        "Step scripts (multi-tool)", fontsize=MAX_FONTSIZE, color=RIGHT_AXIS_COLOR
    )
    ax_right.tick_params(axis="y", labelsize=MAX_FONTSIZE - 2, colors=RIGHT_AXIS_COLOR)
    ax_right.spines["right"].set_color(RIGHT_AXIS_COLOR)
    ax_right.spines["top"].set_visible(False)

    tick_labels = ax_left.get_xticklabels()
    if len(tick_labels) > 1:
        tick_labels[1].set_color(RIGHT_AXIS_COLOR)
        # tick_labels[1].set_fontweight('bold')

    ax_left.set_ylim(0, total_single * 1.22)
    ax_right.set_ylim(0, total_multi * 1.3)

    # ── Legend centered between the two bars ──
    handles, labels = [], []
    for a in (ax_left, ax_right):
        h, l = a.get_legend_handles_labels()
        handles += h
        labels += l

    combined_handles = [
        Patch(color=C_HIGH),
        Patch(color=C_LOW),
    ]
    combined_labels = [
        "nf-core tool\n100% nf-core tools",
        "custom tool\n0% nf-core tools",
    ]
    order = [0, 1, 2, 3]
    filtered = [(handles[i], labels[i]) for i in order]
    leg = ax_right.legend(
        combined_handles + [h for h, _ in filtered],
        combined_labels + [l for _, l in filtered],
        title_fontsize=MAX_FONTSIZE - 4,
        fontsize=MAX_FONTSIZE - 8,
        loc="center",
        title="Tool category",
    )
    leg.get_frame().set_edgecolor("grey")
    leg.get_frame().set_facecolor("#fafafa")

    # ── Stats box (top right) ──
    stats_line = f"#tools per step: mean={mean_multi:.2f} std={std_multi:.2f}"
    ax_left.text(
        0.98,
        0.98,
        stats_line,
        transform=ax_left.transAxes,
        ha="right",
        va="top",
        fontsize=MAX_FONTSIZE - 4,
        bbox=dict(
            boxstyle="round,pad=0.3", facecolor="white", edgecolor="grey", alpha=0.7
        ),
    )

    fig.tight_layout()
    fig.savefig(output_dir / f"{name}.pdf", dpi=150)
    plt.close(fig)

    bucket_str = "  ".join(f"{BUCKET_LABELS[i]}={multi_buckets[i]}" for i in range(6))
    print(
        f"    Saved {name}.pdf — {total} processes, "
        f"{total_single} single, {total_multi} multi"
    )
    print(f"      {bucket_str}")
