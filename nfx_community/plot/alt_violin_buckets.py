from pathlib import Path

import matplotlib.patheffects as path_effects
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.patches import Patch

from . import integer_percentages
from ._colors import C_HIGH, C_LOW

BUCKET_COLORS = [C_LOW, "#d35400", "#e67e22", "#f1c40f", "#2ecc71", C_HIGH]
BUCKET_LABELS = [
    "0% nf-core",
    "<25% nf-core",
    "25\u201350% nf-core",
    "50\u201375% nf-core",
    "75\u201399% nf-core",
    "100% nf-core",
]
BUCKET_XTICK_LABELS = [
    "0%",
    "<25%",
    "25\u201350%\n",
    "50\u201375%\n",
    "75\u201399%\n",
    "100%",
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


def _round_pcts(vals, total):
    return integer_percentages(vals, total)


def plot_tool_violin_buckets(data, output_dir, name, nfcore_modules):
    if isinstance(output_dir, str):
        output_dir = Path(output_dir)
    repos = data["module_analysis"]["repos"]
    nfcore_bases = _get_nfcore_bases(data, nfcore_modules)

    single_custom = 0
    single_nfcore = 0
    multi_buckets = [0, 0, 0, 0, 0, 0]
    bucket_tool_counts = [[] for _ in range(6)]

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
                b = _ratio_bucket(ratio)
                multi_buckets[b] += 1
                bucket_tool_counts[b].append(n)

    total_single = single_custom + single_nfcore
    total_multi = sum(multi_buckets)
    total = total_single + total_multi
    assert (
        total_single == single_custom + single_nfcore
    ), f"single custom {single_custom} + nfcore {single_nfcore} != total {total_single}"
    assert total_multi == sum(
        multi_buckets
    ), f"multi buckets sum {sum(multi_buckets)} != total {total_multi}"

    fig, ax_left = plt.subplots(figsize=(10, 6))
    ax_right = ax_left.twinx()

    x_single = 0
    x_violins = np.linspace(0.65, 1.35, 6)

    # ── Light blue background for multi-tool area ──
    ax_left.axvspan(0.5, 1.5, color=RIGHT_AXIS_COLOR, alpha=0.1, zorder=0)
    ax_left.set_xlim(-0.475, 1.475)

    # ── Left axis: single-tool stacked bar ──
    ax_left.bar(
        x_single,
        total_single,
        width=0.55,
        color="#7f8c8d",
        edgecolor="white",
        linewidth=1.2,
        zorder=3,
    )
    ax_left.bar(
        x_single,
        single_custom,
        width=0.55,
        color=C_LOW,
        edgecolor="white",
        linewidth=0.5,
        zorder=3,
    )
    ax_left.bar(
        x_single,
        single_nfcore,
        width=0.55,
        color=C_HIGH,
        bottom=single_custom,
        edgecolor="white",
        linewidth=0.5,
        zorder=3,
    )

    # single bar annotations
    pcts = _round_pcts([single_custom, single_nfcore], total_single)
    cum = 0
    for v, pct in zip([single_custom, single_nfcore], pcts):
        if v > 0:
            y = cum + v / 2
            ax_left.text(
                x_single,
                y,
                f"{v} ({pct}%)",
                ha="center",
                va="center",
                fontsize=12,
                fontweight="bold",
                color="white",
                path_effects=[path_effects.withStroke(linewidth=2, foreground="black")],
            )
            cum += v

    # Right axis: violins per bucket
    vp = ax_right.violinplot(
        bucket_tool_counts,
        positions=x_violins,
        showmeans=True,
        showmedians=False,
        showextrema=False,
        widths=0.13,
    )

    for i, pc in enumerate(vp["bodies"]):
        pc.set_facecolor(BUCKET_COLORS[i])
        pc.set_edgecolor("white")
        pc.set_alpha(0.8)

    if "cmeans" in vp:
        vp["cmeans"].set_color("white")
        vp["cmeans"].set_linewidth(1.5)
        vp["cmeans"].set_zorder(5)

    # n= count labels under each violin
    for i, pos in enumerate(x_violins):
        n = multi_buckets[i]
        if n > 0:
            ax_right.text(
                pos,
                0,
                f"n={n}",
                ha="center",
                va="bottom",
                fontsize=12,
                color=RIGHT_AXIS_COLOR,
                fontweight="bold",
                transform=ax_right.get_xaxis_transform(),
                path_effects=[path_effects.withStroke(linewidth=1, foreground="white")],
            )

    # ── Axis styling ──
    all_xticks = [x_single] + list(x_violins)
    all_xticklabels = [f"Single-tool\nn={total_single}"] + BUCKET_XTICK_LABELS
    ax_left.set_xticks(all_xticks)
    ax_left.set_xticklabels(all_xticklabels, fontsize=12)
    for lbl in ax_left.get_xticklabels()[1:]:
        lbl.set_rotation(20)
        # lbl.set_ha("right")
    ax_left.set_ylabel("Step scripts", fontsize=13)
    ax_left.tick_params(axis="y", labelsize=12)
    ax_left.spines["top"].set_visible(False)
    ax_right.set_ylabel("#tools per process", fontsize=13, color=RIGHT_AXIS_COLOR)
    ax_right.tick_params(axis="y", labelsize=12, colors=RIGHT_AXIS_COLOR)
    ax_right.spines["right"].set_color(RIGHT_AXIS_COLOR)
    ax_right.spines["top"].set_visible(False)

    # Blue multi-tool label
    ax_left.text(
        0.75,
        0.97,
        f"Multi-tool n={total_multi}",
        transform=ax_left.transAxes,
        ha="center",
        va="top",
        fontsize=13,
        fontweight="bold",
        color=RIGHT_AXIS_COLOR,
    )

    tick_labels = ax_left.get_xticklabels()
    if len(tick_labels) > 1:
        for lbl in tick_labels[1:]:
            lbl.set_color(RIGHT_AXIS_COLOR)

    # y-limits (log scale on right to handle outlier bucket 75-99%)
    max_tools = max((max(b) for b in bucket_tool_counts if b), default=2)
    ax_left.set_ylim(0, total_single * 1.22)
    ax_right.set_yscale("log")
    ax_right.set_ylim(1.5, max_tools * 2)

    # ── Legend centered between bars ──
    leg_handles = [
        Patch(color=C_HIGH),
        Patch(color=C_LOW),
        Patch(color=BUCKET_COLORS[1]),
        Patch(color=BUCKET_COLORS[2]),
        Patch(color=BUCKET_COLORS[3]),
        Patch(color=BUCKET_COLORS[4]),
    ]
    leg_labels = [
        "nf-core tool\n100% nf-core tools",
        "custom tool\n0% nf-core tools",
    ] + BUCKET_LABELS[1:5]
    leg = ax_left.legend(
        leg_handles,
        leg_labels,
        fontsize=12,
        loc="upper center",
        title="Tool category",
        title_fontsize=12,
    )
    leg.get_frame().set_edgecolor("grey")
    leg.get_frame().set_facecolor("#fafafa")

    fig.tight_layout()
    fig.savefig(output_dir / f"{name}.pdf", dpi=150)
    plt.close(fig)

    bucket_str = "  ".join(f"{BUCKET_LABELS[i]}={multi_buckets[i]}" for i in range(6))
    print(
        f"    Saved {name}.pdf — {total} processes, "
        f"{total_single} single, {total_multi} multi"
    )
    print(f"      {bucket_str}")
