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


def plot_top_tools_by_score(data, output_dir, name, **kargs):
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

    top_high = high.most_common(15)
    top_low = low.most_common(15)

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(15, 8))

    # --- Left panel: score >= 0.5, all tools ---
    if top_high:
        labels_h = []
        for tool_name, cnt in top_high:
            labels_h.append(tool_name.replace("_", " ").title())
        counts_h = [t[1] for t in top_high]
        bars1 = ax1.barh(
            range(len(labels_h)), counts_h, color=C_HIGH, edgecolor="white"
        )
        ax1.set_yticks(range(len(labels_h)))
        ax1.set_yticklabels(labels_h, fontsize=16)
        ax1.set_xlabel("Process blocks with this tool")
        ax1.set_title("Heavily customized processes\n(score \u2265 0.5)", fontsize=16)
        ax1.invert_yaxis()
        for bar, cnt in zip(bars1, counts_h):
            ax1.text(
                bar.get_width() + 0.2,
                bar.get_y() + bar.get_height() / 2,
                str(cnt),
                va="center",
                fontsize=14,
            )
    else:
        ax1.text(0.5, 0.5, "No data", ha="center", va="center", transform=ax1.transAxes)
        ax1.set_title("Heavily customized processes\n(score \u2265 0.5)", fontsize=16)

    # --- Right panel: score < 0.5, non-nf-core tools only ---
    if top_low:
        labels_l = []
        for tool_name, cnt in top_low:
            labels_l.append(tool_name.replace("_", " ").title())
        counts_l = [t[1] for t in top_low]
        bars2 = ax2.barh(range(len(labels_l)), counts_l, color=C_LOW, edgecolor="white")
        ax2.set_yticks(range(len(labels_l)))
        ax2.set_yticklabels(labels_l, fontsize=14)
        ax2.set_xlabel("Process blocks with this tool")
        ax2.set_title(
            "Custom tools in nf-core-like processes\n(score < 0.5)", fontsize=16
        )
        ax2.invert_yaxis()
        for bar, cnt in zip(bars2, counts_l):
            ax2.text(
                bar.get_width() + 0.2,
                bar.get_y() + bar.get_height() / 2,
                str(cnt),
                va="center",
                fontsize=14,
            )
    else:
        ax2.text(0.5, 0.5, "No data", ha="center", va="center", transform=ax2.transAxes)
        ax2.set_title(
            "Custom tools in nf-core-like processes\n(score < 0.5)", fontsize=16
        )

    fig.tight_layout()
    fig.savefig(output_dir / f"{name}.pdf", dpi=150)
    plt.close(fig)
    print(
        f"    Saved {name}.pdf — "
        f"{len(top_high)} high-score, {len(top_low)} low-score tools"
    )
