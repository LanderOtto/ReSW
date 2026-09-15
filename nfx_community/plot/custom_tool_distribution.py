from collections import Counter
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np

from nfx_community.nfcore_tools.parsing import _BUILTINS

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


def plot_custom_tool_distribution(data, output_dir, name, nfcore_modules):
    repos = data["module_analysis"]["repos"]
    nfcore_bases = _get_nfcore_bases(data, nfcore_modules)

    # Collect tool_cmds from metric entries with score < 0.5
    tools_per_proc = Counter()
    tool_usage = Counter()

    for r in repos:
        for e in r.get("nfcore_tool_evidence", []):
            if e[4] == "exact":
                continue
            if e[4] != "metric":
                continue
            comp = e[6] if len(e) > 6 else {}
            score = comp.get("score", 0.0)
            if score is None or score >= 0.5:
                continue
            tools = comp.get("tool_cmds", [])
            seen_in_block = set()
            custom_tools = []
            for t in tools:
                tl = t.lower()
                if tl in _BUILTINS:
                    continue
                if tl in nfcore_bases:
                    continue
                if tl in seen_in_block:
                    continue
                seen_in_block.add(tl)
                custom_tools.append(tl)
            if custom_tools:
                tools_per_proc[len(custom_tools)] += 1
                for tl in custom_tools:
                    tool_usage[tl] += 1

    # --- Left panel: tools per process histogram ---
    max_bin = max(tools_per_proc.keys()) if tools_per_proc else 1
    # Bin all processes with >= 10 tools into a "10+" group
    bins = list(range(1, 11))
    bin_labels = [str(i) for i in range(1, 10)] + ["10+"]
    bin_counts = [0] * 10
    for n, cnt in tools_per_proc.items():
        if n >= 10:
            bin_counts[9] += cnt
        elif n >= 1:
            bin_counts[n - 1] = cnt

    # Right panel: tool frequency rank (log-log)
    sorted_tools = tool_usage.most_common()
    ranks = np.arange(1, len(sorted_tools) + 1)
    freqs = np.array([c for _, c in sorted_tools])

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(18, 8))

    # --- Left: histogram ---
    colors = [C_HIGH if n > 1000 else C_MID if n > 100 else C_LOW for n in bin_counts]
    bars = ax1.bar(
        bin_labels, bin_counts, color=colors, edgecolor="white", linewidth=0.5
    )
    for bar, cnt in zip(bars, bin_counts):
        if cnt > 0:
            ax1.text(
                bar.get_x() + bar.get_width() / 2,
                bar.get_height() + max(bin_counts) * 0.01,
                str(cnt),
                ha="center",
                va="bottom",
                fontsize=12,
            )
    ax1.set_xlabel("Tools per process", fontsize=13)
    ax1.set_ylabel("Process blocks", fontsize=13)
    ax1.set_title(
        "Custom Tools per Process Block\n(score < 0.5, metric only)", fontsize=14
    )
    ax1.tick_params(axis="x", labelsize=12)
    ax1.tick_params(axis="y", labelsize=12)

    # --- Right: tool frequency vs rank (log-log) ---
    ax2.loglog(ranks, freqs, color=C_MID, linewidth=1.5, alpha=0.8)
    ax2.scatter(ranks, freqs, color=C_HIGH, s=8, alpha=0.6, edgecolors="none", zorder=3)
    ax2.set_xlabel("Tool rank", fontsize=13)
    ax2.set_ylabel("Occurrence count", fontsize=13)
    ax2.set_title("Tool Frequency Distribution (log-log)", fontsize=14)
    ax2.tick_params(axis="both", labelsize=12)

    # Explanation text box (top-right empty space)
    ax2.text(
        0.97,
        0.97,
        "Tool rank = position when\n"
        "sorted by occurrence count.\n"
        "Rank 1 = most frequent tool.\n"
        "A flat line at the bottom\n"
        "means many tools appear\n"
        "only once.",
        transform=ax2.transAxes,
        fontsize=12,
        alpha=0.75,
        ha="right",
        va="top",
        bbox=dict(
            boxstyle="round,pad=0.3", facecolor="white", edgecolor="grey", alpha=0.7
        ),
    )

    # Annotate top 10 tools
    top_n = 10
    for i in range(min(top_n, len(sorted_tools))):
        tool_name, cnt = sorted_tools[i]
        label = tool_name.replace("_", " ").title()
        ax2.annotate(
            label,
            (ranks[i], freqs[i]),
            xytext=(5, 5),
            textcoords="offset points",
            fontsize=12,
            alpha=0.8,
            arrowprops=dict(arrowstyle="-", color="grey", alpha=0.3),
        )

    # Add count annotations
    total_procs = sum(tools_per_proc.values())
    single_tool_procs = tools_per_proc.get(1, 0)
    single_occ_tools = sum(1 for c in freqs if c == 1)

    fig.text(
        0.5,
        0.01,
        f"{total_procs} metric blocks with score < 0.5  |  "
        f"{single_tool_procs} ({100*single_tool_procs//max(1,total_procs)}%) have exactly 1 tool  |  "
        f"{single_occ_tools} unique tools appear only once  |  "
        f"{len(sorted_tools)} unique tools total",
        ha="center",
        fontsize=12,
        style="italic",
    )

    fig.tight_layout(rect=[0, 0.04, 1, 1])
    fig.savefig(output_dir / f"{name}.pdf", dpi=150)
    plt.close(fig)
    print(
        f"    Saved {name}.pdf — "
        f"{total_procs} blocks, {len(sorted_tools)} unique tools"
    )
