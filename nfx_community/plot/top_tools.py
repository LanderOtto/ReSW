from collections import Counter

import matplotlib.pyplot as plt

from nfx_community.nfcore_tools.parsing import _BUILTINS

from ._colors import C_LOW, C_MID


def _get_nfcore_bases(data):
    bases = set()
    for r in data["module_analysis"]["repos"]:
        for e in r.get("nfcore_tool_evidence", []):
            if e[4] == "exact":
                bases.add(e[3].lower())
    return bases


def plot_top_tools(data, output_dir, name, **kargs):
    repos = data["module_analysis"]["repos"]
    nfcore_bases = _get_nfcore_bases(data)

    # --- Re-implemented: nf-core tools found inside metric process blocks ---
    reimp = Counter()
    for r in repos:
        for e in r.get("nfcore_tool_evidence", []):
            if e[4] != "metric":
                continue
            comp = e[6] if len(e) > 6 else {}
            seen_in_block = set()
            for t in comp.get("tool_cmds_fullname", comp.get("tool_cmds", [])):
                tl = t.lower()
                base = tl.split("/")[0]
                if base not in nfcore_bases:
                    continue
                if tl in seen_in_block:
                    continue
                seen_in_block.add(tl)
                reimp[tl] += 1

    top_reimp = reimp.most_common(15)

    # --- Custom tools: non-nf-core tool names inside metric process blocks ---
    tool_counter = Counter()
    for r in repos:
        for e in r.get("nfcore_tool_evidence", []):
            if e[4] != "metric":
                continue
            comp = e[6] if len(e) > 6 else {}
            seen_in_block = set()
            for t in comp.get("tool_cmds", []):
                tl = t.lower()
                if tl in _BUILTINS:
                    continue
                if tl in nfcore_bases:
                    continue
                if tl in seen_in_block:
                    continue
                seen_in_block.add(tl)
                tool_counter[tl] += 1

    top_tools = tool_counter.most_common(15)

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(15, 8))

    # --- Left panel: re-implemented ---
    if top_reimp:
        labels_r = []
        for tool_name, cnt in top_reimp:
            label = tool_name.replace("_", " ").title()
            labels_r.append(label)
        counts_r = [t[1] for t in top_reimp]
        bars1 = ax1.barh(range(len(labels_r)), counts_r, color=C_MID, edgecolor="white")
        ax1.set_yticks(range(len(labels_r)))
        ax1.set_yticklabels(labels_r, fontsize=9)
        ax1.set_xlabel("Process blocks with this tool")
        ax1.set_title("Most re-implemented processes", fontsize=11)
        ax1.invert_yaxis()
        for bar, cnt in zip(bars1, counts_r):
            ax1.text(
                bar.get_width() + 0.2,
                bar.get_y() + bar.get_height() / 2,
                str(cnt),
                va="center",
                fontsize=9,
            )
    else:
        ax1.text(0.5, 0.5, "No data", ha="center", va="center", transform=ax1.transAxes)
        ax1.set_title("Most re-implemented processes", fontsize=11)

    # --- Right panel: custom tools ---
    if top_tools:
        labels_t = []
        for tool_name, cnt in top_tools:
            label = tool_name.replace("_", " ").title()
            labels_t.append(label)
        counts_t = [t[1] for t in top_tools]
        bars2 = ax2.barh(range(len(labels_t)), counts_t, color=C_LOW, edgecolor="white")
        ax2.set_yticks(range(len(labels_t)))
        ax2.set_yticklabels(labels_t, fontsize=9)
        ax2.set_xlabel("Process blocks with this tool")
        ax2.set_title("Most custom tools", fontsize=11)
        ax2.invert_yaxis()
        for bar, cnt in zip(bars2, counts_t):
            ax2.text(
                bar.get_width() + 0.2,
                bar.get_y() + bar.get_height() / 2,
                str(cnt),
                va="center",
                fontsize=9,
            )
    else:
        ax2.text(0.5, 0.5, "No data", ha="center", va="center", transform=ax2.transAxes)
        ax2.set_title("Most custom tools", fontsize=11)

    fig.text(
        0.5,
        0.01,
        "Left: nf-core tools found in non-nf-core process blocks     "
        "Right: non-nf-core tools found in metric process blocks",
        ha="center",
        fontsize=8,
        style="italic",
    )
    fig.tight_layout(rect=[0, 0.04, 1, 1])
    fig.savefig(output_dir / f"{name}.pdf", dpi=150)
    plt.close(fig)
    print(
        f"    Saved {name}.pdf — "
        f"{len(top_reimp)} re-implemented, {len(top_tools)} custom tools"
    )
