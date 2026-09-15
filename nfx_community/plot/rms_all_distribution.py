import matplotlib.pyplot as plt
import numpy as np

from ._colors import C_EXACT, C_HIGH, C_LOW, C_MID


def plot_rms_all_distribution(data, output_dir, name, **kargs):
    all_evidence = _collect_evidence(data)
    scores = [e[5] for e in all_evidence if e[5] is not None]
    if not scores:
        print("    No scores to plot.")
        return

    exact_scores = [s for e, s in zip(all_evidence, scores) if e[4] == "exact"]
    metric_scores = [s for e, s in zip(all_evidence, scores) if e[4] == "metric"]

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 5))

    bins = np.arange(0, 1.05, 0.05)

    # Left: all scores histogram
    n, bin_edges, patches = ax1.hist(
        scores, bins=bins, edgecolor="white", linewidth=0.5, alpha=0.85
    )
    for i, p in enumerate(patches):
        center = (bin_edges[i] + bin_edges[i + 1]) / 2
        if center < 0.4:
            p.set_facecolor(C_LOW)
        elif center < 0.7:
            p.set_facecolor(C_MID)
        else:
            p.set_facecolor(C_HIGH)

    ax1.axvline(0.4, color="gray", linestyle="--", alpha=0.5)
    ax1.axvline(0.7, color="gray", linestyle="--", alpha=0.5)
    ax1.set_xlabel("RMS")
    ax1.set_ylabel("Number of evidence entries")
    ax1.set_title(f"All evidence (n={len(scores)})")
    ax1.set_xlim(0, 1)

    # Right: stacked histogram exact vs metric
    ax2.hist(
        [exact_scores, metric_scores],
        bins=bins,
        stacked=True,
        color=[C_EXACT, C_MID],
        edgecolor="white",
        linewidth=0.5,
        label=["Exact", "Metric"],
    )
    ax2.axvline(0.4, color="gray", linestyle="--", alpha=0.5)
    ax2.axvline(0.7, color="gray", linestyle="--", alpha=0.5)
    ax2.set_xlabel("RMS")
    ax2.set_ylabel("Number of evidence entries")
    ax2.set_title("Exact vs Metric by RMS")
    ax2.set_xlim(0, 1)
    ax2.legend()

    fig.tight_layout()
    fig.savefig(output_dir / f"{name}.pdf", dpi=150)
    plt.close(fig)

    low = sum(1 for s in scores if s < 0.4)
    mid = sum(1 for s in scores if 0.4 <= s < 0.7)
    high = sum(1 for s in scores if s >= 0.7)
    print(
        f"    Saved {name}.pdf — {len(scores)} total scores "
        f"({len(exact_scores)} exact, {len(metric_scores)} metric, "
        f"{low} low, {mid} mid, {high} high)"
    )

    stdout_bins = np.arange(0, 1.05, 0.1)
    counts, edges = np.histogram(scores, bins=stdout_bins)

    print("\nScore Distribution:")
    for count, start, end in zip(counts, edges[:-1], edges[1:]):
        # Subtract 0.1 from the 'end' value for all but the last bin
        # so [0.0, 0.3) prints as "0.0 - 0.2"
        display_end = end - 0.1 if end < 1.0 else end
        print(f"{start:.1f} - {display_end:.1f} : {count}")


def _collect_evidence(data):
    evidence = []
    for r in data["module_analysis"]["repos"]:
        for e in r.get("nfcore_tool_evidence", []):
            evidence.append(e)
    return evidence
