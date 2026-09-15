from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np

from ._colors import C_HIGH, C_LOW, C_MID


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


def plot_tool_violin_hist(data, output_dir, name, nfcore_modules):
    if isinstance(output_dir, str):
        output_dir = Path(output_dir)
    repos = data["module_analysis"]["repos"]
    nfcore_bases = _get_nfcore_bases(data, nfcore_modules)

    single_custom = 0
    single_nfcore = 0
    multi_pure_custom = 0
    multi_nfcore_any = 0
    nfcore_ratios = []
    n_tool_counts = []
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
            n_tool_counts.append(n)
            has_nf = any(t in nfcore_bases for t in stripped)
            n_nf = sum(1 for t in stripped if t in nfcore_bases)
            if n == 1:
                if has_nf:
                    single_nfcore += 1
                else:
                    single_custom += 1
            else:
                multi_tool_counts.append(n)
                if has_nf:
                    multi_nfcore_any += 1
                    nfcore_ratios.append(n_nf / n)
                else:
                    multi_pure_custom += 1

    total_single = single_custom + single_nfcore
    total_multi = multi_pure_custom + multi_nfcore_any
    total = total_single + total_multi

    nfcore_ratios_arr = np.array(nfcore_ratios) if nfcore_ratios else np.array([0.0])
    mean_ratio = np.mean(nfcore_ratios_arr)
    std_ratio = np.std(nfcore_ratios_arr)

    multi_tools_arr = (
        np.array(multi_tool_counts) if multi_tool_counts else np.array([0.0])
    )
    mean_multi = np.mean(multi_tools_arr) if len(multi_tools_arr) > 0 else 0.0
    std_multi = np.std(multi_tools_arr) if len(multi_tools_arr) > 0 else 0.0

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 6))

    # ── Left panel (same as plot 18) ──
    categories = ["Single-tool", "Multi-tool"]
    x = np.arange(len(categories))
    bar_width = 0.55

    ax1.bar(
        x[0],
        total_single,
        width=bar_width,
        color="#7f8c8d",
        edgecolor="white",
        linewidth=1.2,
        zorder=3,
    )
    ax1.bar(
        x[1],
        total_multi,
        width=bar_width,
        color="#7f8c8d",
        edgecolor="white",
        linewidth=1.2,
        zorder=3,
    )

    ax1.bar(
        x[0],
        single_custom,
        width=bar_width,
        color=C_LOW,
        edgecolor="white",
        linewidth=0.5,
        zorder=3,
        label="Custom tool",
    )
    ax1.bar(
        x[0],
        single_nfcore,
        width=bar_width,
        color=C_HIGH,
        bottom=single_custom,
        edgecolor="white",
        linewidth=0.5,
        zorder=3,
        label="nf-core tool",
    )
    ax1.bar(
        x[1],
        multi_pure_custom,
        width=bar_width,
        color=C_LOW,
        edgecolor="white",
        linewidth=0.5,
        zorder=3,
    )
    ax1.bar(
        x[1],
        multi_nfcore_any,
        width=bar_width,
        color=C_MID,
        bottom=multi_pure_custom,
        edgecolor="white",
        linewidth=0.5,
        zorder=3,
        label="Has nf-core tool(s)",
    )

    def _annotate_stack(ax, xi, vals, bar_total, colors):
        cum = 0
        for v, c in zip(vals, colors):
            if v > 0:
                pct = 100 * v // max(1, bar_total)
                label = f"{v} ({pct}%)"
                y = cum + v / 2
                ax.text(
                    xi,
                    y,
                    label,
                    ha="center",
                    va="center",
                    fontsize=10,
                    fontweight="bold",
                    color="white",
                )
            cum += v

    _annotate_stack(
        ax1, x[0], [single_custom, single_nfcore], total_single, [C_LOW, C_HIGH]
    )
    _annotate_stack(
        ax1, x[1], [multi_pure_custom, multi_nfcore_any], total_multi, [C_LOW, C_MID]
    )

    ax1.set_xticks(x)
    ax1.set_xticklabels(
        [f"Single-tool\nn={total_single}", f"Multi-tool\nn={total_multi}"], fontsize=12
    )
    ax1.set_ylabel("Process blocks", fontsize=13)
    ax1.set_title(
        "Process Tool Usage Breakdown\n(metric entries, all scores)", fontsize=14
    )
    ax1.tick_params(axis="y", labelsize=12)
    ax1.legend(fontsize=10, loc="upper right")
    ax1.spines["top"].set_visible(False)
    ax1.spines["right"].set_visible(False)
    ax1.set_ylim(0, max(total_single, total_multi) * 1.22)

    stats_line = (
        f"Multi: μ={mean_multi:.2f} σ={std_multi:.2f}  |  "
        f"nf-core ratio (multi): μ={mean_ratio:.2f} σ={std_ratio:.2f}"
    )
    ax1.text(
        0.5,
        -0.14,
        stats_line,
        transform=ax1.transAxes,
        ha="center",
        va="top",
        fontsize=9.5,
        style="italic",
        bbox=dict(
            boxstyle="round,pad=0.3", facecolor="white", edgecolor="grey", alpha=0.7
        ),
    )

    # ── Right panel: violin (multi) + nf-core ratio histogram ──
    ax2.axis("off")

    if total_multi > 0:
        # Top: violin of tools/process for multi-tool
        ax_violin = ax2.inset_axes([0.08, 0.48, 0.84, 0.48])
        vp = ax_violin.violinplot(
            multi_tools_arr,
            positions=[0],
            showmeans=True,
            showmedians=True,
            widths=0.6,
        )
        for body in vp["bodies"]:
            body.set_facecolor(C_MID)
            body.set_alpha(0.4)
        vp["cmeans"].set_color(C_HIGH)
        vp["cmeans"].set_linewidth(2)
        vp["cmedians"].set_color("black")
        vp["cmedians"].set_linewidth(1)
        vp["cbars"].set_color("grey")
        vp["cmaxes"].set_color("grey")
        vp["cmins"].set_color("grey")

        # Jittered scatter overlay
        jitter = np.random.default_rng(42).uniform(
            -0.15, 0.15, size=len(multi_tools_arr)
        )
        ax_violin.scatter(
            jitter, multi_tools_arr, s=3, alpha=0.15, color="black", zorder=2
        )

        ax_violin.set_xticks([0])
        ax_violin.set_xticklabels([f"Multi-tool\n(μ={mean_multi:.2f})"], fontsize=10)
        ax_violin.set_ylabel("Tools per process", fontsize=11)
        ax_violin.tick_params(labelsize=9)
        ax_violin.spines["top"].set_visible(False)
        ax_violin.spines["right"].set_visible(False)
        max_multi = int(np.max(multi_tools_arr)) if len(multi_tools_arr) > 0 else 1
        ax_violin.set_ylim(0, max_multi * 1.15)

        # Bottom: nf-core ratio histogram
        if nfcore_ratios:
            ax_hist = ax2.inset_axes([0.08, 0.02, 0.84, 0.38])
            ax_hist.hist(
                nfcore_ratios_arr,
                bins=np.linspace(0, 1, 11),
                color=C_MID,
                edgecolor="white",
                linewidth=0.8,
                alpha=0.8,
            )
            ax_hist.axvline(
                mean_ratio,
                color=C_HIGH,
                linestyle="--",
                linewidth=1.5,
                label=f"μ={mean_ratio:.2f}",
            )
            ax_hist.axvline(
                mean_ratio + std_ratio,
                color=C_LOW,
                linestyle=":",
                linewidth=1.2,
                alpha=0.6,
            )
            ax_hist.axvline(
                mean_ratio - std_ratio,
                color=C_LOW,
                linestyle=":",
                linewidth=1.2,
                alpha=0.6,
            )
            ax_hist.set_xlabel("nf-core ratio", fontsize=10)
            ax_hist.set_ylabel("Process count", fontsize=10)
            ax_hist.tick_params(labelsize=9)
            ax_hist.legend(fontsize=8)
            ax_hist.set_title("nf-core tool ratio (multi-tool)", fontsize=10)
    else:
        ax2.text(
            0.5,
            0.5,
            "No multi-tool processes",
            transform=ax2.transAxes,
            ha="center",
            va="center",
            fontsize=13,
            alpha=0.6,
        )

    fig.tight_layout()
    fig.savefig(output_dir / f"{name}.pdf", dpi=150)
    plt.close(fig)
    print(
        f"    Saved {name}.pdf — {total} processes, "
        f"{total_single} single, {total_multi} multi"
    )
