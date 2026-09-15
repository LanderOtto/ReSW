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


def plot_tool_stacked_hist(data, output_dir, name, nfcore_modules):
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

    # Per-process data for stacked histogram
    # For each tool count k, how many are: custom-only, mixed, nfcore-only
    from collections import defaultdict

    hist_custom = defaultdict(int)  # all tools are custom
    hist_mixed = defaultdict(int)  # mix of custom + nf-core
    hist_nfcore = defaultdict(int)  # all tools are nf-core

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
            all_nf = all(t in nfcore_bases for t in stripped)
            n_nf = sum(1 for t in stripped if t in nfcore_bases)

            if n == 1:
                if has_nf:
                    single_nfcore += 1
                    hist_nfcore[1] += 1
                else:
                    single_custom += 1
                    hist_custom[1] += 1
            else:
                if all_nf:
                    multi_nfcore_any += 1
                    nfcore_ratios.append(1.0)
                    hist_nfcore[n] += 1
                elif has_nf:
                    multi_nfcore_any += 1
                    nfcore_ratios.append(n_nf / n)
                    hist_mixed[n] += 1
                else:
                    multi_pure_custom += 1
                    hist_custom[n] += 1

    total_single = single_custom + single_nfcore
    total_multi = multi_pure_custom + multi_nfcore_any
    total = total_single + total_multi

    nfcore_ratios_arr = np.array(nfcore_ratios) if nfcore_ratios else np.array([0.0])
    mean_ratio = np.mean(nfcore_ratios_arr)
    std_ratio = np.std(nfcore_ratios_arr)

    multi_tools_arr = (
        np.array([c for c in n_tool_counts if c > 1])
        if total_multi > 0
        else np.array([0.0])
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

    # ── Right panel: stacked histogram of tools/process ──
    max_bin = max(
        list(hist_custom.keys())
        + list(hist_mixed.keys())
        + list(hist_nfcore.keys())
        + [1]
    )
    bins = list(range(1, 11))
    bin_labels = [str(i) for i in range(1, 10)] + ["10+"]

    def _bin_counts(hist):
        result = [0] * 10
        for n, cnt in hist.items():
            if n >= 10:
                result[9] += cnt
            elif n >= 1:
                result[n - 1] = cnt
        return result

    cust_bins = _bin_counts(hist_custom)
    mix_bins = _bin_counts(hist_mixed)
    nfc_bins = _bin_counts(hist_nfcore)

    # Build stacked bars
    ax2.bar(
        bin_labels,
        cust_bins,
        color=C_LOW,
        edgecolor="white",
        linewidth=0.5,
        label="All custom",
        zorder=3,
    )
    ax2.bar(
        bin_labels,
        mix_bins,
        bottom=cust_bins,
        color=C_MID,
        edgecolor="white",
        linewidth=0.5,
        label="Mixed",
        zorder=3,
    )
    bottom_mixed = [a + b for a, b in zip(cust_bins, mix_bins)]
    ax2.bar(
        bin_labels,
        nfc_bins,
        bottom=bottom_mixed,
        color=C_HIGH,
        edgecolor="white",
        linewidth=0.5,
        label="All nf-core",
        zorder=3,
    )

    # Annotate μ±σ for multi-tool
    max_y = max([a + b + c for a, b, c in zip(cust_bins, mix_bins, nfc_bins)])
    if total_multi > 0:
        ax2.axvline(
            min(mean_multi, 10.5) - 0.5,
            color="black",
            linestyle="--",
            linewidth=1.5,
            alpha=0.7,
            label=f"μ={mean_multi:.2f}",
        )
        ax2.axvline(
            min(max(mean_multi - std_multi, 0.5), 10.5) - 0.5,
            color="grey",
            linestyle=":",
            linewidth=1.2,
            alpha=0.6,
        )
        ax2.axvline(
            min(max(mean_multi + std_multi, 0.5), 10.5) - 0.5,
            color="grey",
            linestyle=":",
            linewidth=1.2,
            alpha=0.6,
        )

    ax2.set_xlabel("Tools per process", fontsize=12)
    ax2.set_ylabel("Process blocks", fontsize=11)
    ax2.set_title("Tool Count Distribution\n(by nf-core overlap)", fontsize=12)
    ax2.tick_params(labelsize=10)
    ax2.legend(fontsize=8, loc="upper right")
    ax2.spines["top"].set_visible(False)
    ax2.spines["right"].set_visible(False)
    ax2.set_ylim(0, max_y * 1.15)

    fig.tight_layout()
    fig.savefig(output_dir / f"{name}.pdf", dpi=150)
    plt.close(fig)
    print(
        f"    Saved {name}.pdf — {total} processes, "
        f"{total_single} single, {total_multi} multi"
    )
