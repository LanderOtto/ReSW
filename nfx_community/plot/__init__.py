import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
from matplotlib import font_manager

from nfx_community.api import fetch_nfcore_module_list


def integer_percentages(counts, total):
    """Integer percentages that sum to exactly 100 (largest-remainder method).

    `counts` are the per-segment counts; `total` is their sum. Returns one int
    per segment (in the same order), summing to 100. Safe for ``total == 0``.
    """
    if total <= 0:
        return [0] * len(counts)
    floors = [int(100 * c / total) for c in counts]
    remain = 100 - sum(floors)
    ranked = sorted(
        range(len(counts)),
        key=lambda i: 100 * counts[i] / total - floors[i],
        reverse=True,
    )
    out = list(floors)
    for i in ranked[:remain]:
        out[i] += 1
    return out


from .alt_single_panel import plot_tool_single_panel
from .alt_single_panel_v2 import plot_tool_single_panel_v2
from .alt_violin_buckets import plot_tool_violin_buckets
from .community_orgs import plot_community_orgs
from .custom_tool_distribution import plot_custom_tool_distribution
from .evidence_distribution import plot_evidence_distribution
from .infra_only_count import plot_infra_only_count
from .nfcore_adoption_horizontal import plot_nfcore_adoption_horizontal
from .nfcore_adoption_merge import plot_nfcore_adoption_merge
from .nfcore_adoption_merge_v2 import plot_nfcore_adoption_merge_v2
from .nfcore_adoption_merge_v3 import plot_nfcore_adoption_merge_v3
from .nfcore_module_tools import plot_nfcore_module_tools
from .nfcore_pipeline_categories import plot_pipeline_categories
from .nfcore_pipeline_categories_non_nf import plot_pipeline_categories_non_nf
from .nfcore_process_categories import plot_process_categories
from .nfcore_process_categories_non_nf import plot_process_categories_non_nf
from .nfcore_top_modules_by_process import pre15_nfcore_top_modules_by_process
from .rms_all_distribution import plot_rms_all_distribution
from .score_distribution import plot_score_distribution
from .script_interpreters import plot_script_interpreters
from .tool_adoption_flow import plot_tool_adoption_flow
from .top_reimplemented import plot_top_reimplemented
from .top_tools import plot_top_tools
from .top_tools_by_score import plot_top_tools_by_score
from .top_tools_by_score_v2 import plot_top_tools_by_score_v2

ALL_PLOTS = [
    ("01_score_distribution", plot_score_distribution),
    ("02_top_reimplemented", plot_top_reimplemented),
    ("03_evidence_distribution", plot_evidence_distribution),
    ("05_tool_adoption_flow", plot_tool_adoption_flow),
    ("06_nfcore_adoption_per_pipeline", plot_nfcore_adoption_horizontal),
    ("09_process_categories", plot_process_categories),
    ("10_pipeline_categories", plot_pipeline_categories),
    ("11_process_categories_non_nf", plot_process_categories_non_nf),
    ("12_pipeline_categories_non_nf", plot_pipeline_categories_non_nf),
    ("13_rms_all_distribution", plot_rms_all_distribution),
    ("14_top_tools", plot_top_tools),
    ("15_top_tools_by_score", plot_top_tools_by_score),
    ("16_nfcore_adoption_per_process", plot_nfcore_adoption_merge),
    ("17_custom_tool_distribution", plot_custom_tool_distribution),
    ("22_tool_single_panel", plot_tool_single_panel),
    ("23_tool_violin_buckets", plot_tool_violin_buckets),
    ("24_infra_only_count", plot_infra_only_count),
    ("25_script_interpreters", plot_script_interpreters),
    ("26_nfcore_module_tools", plot_nfcore_module_tools),
    ("27_top_tools_by_score_v2", plot_top_tools_by_score_v2),
    ("28_plot_tool_single_panel_v2", plot_tool_single_panel_v2),
    ("29_nfcore_adoption_merge_v2", plot_nfcore_adoption_merge_v2),
    ("30_nfcore_adoption_merge_v3", plot_nfcore_adoption_merge_v3),
    ("31_nfcore_top_modules_by_process", pre15_nfcore_top_modules_by_process),
    ("32_community_orgs", plot_community_orgs),
]


def load_data(json_path):
    with open(json_path) as f:
        return json.load(f)


def generate_all(
    json_path="nextflow_analysis.json",
    output_dir="plots",
    font_path=None,
    nfcore_modules=None,
):
    if not nfcore_modules:
        raise Exception("Impossible to plot without access to the cache directory")
    data = load_data(json_path)
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    if font_path:
        font_manager.fontManager.addfont(font_path)
        prop = font_manager.FontProperties(fname=font_path)
        plt.rcParams["font.family"] = prop.get_name()

    for name, func in ALL_PLOTS:
        print(f"  Plotting {name} ...")
        func(data, out, name, **{"nfcore_modules": nfcore_modules})

    _validate_consistency(data)
    print(f"\nAll plots saved to {out}/")


def _validate_consistency(data):
    repos = data["module_analysis"]["repos"]

    exact_entries = 0
    metric_entries = 0
    metric_high = 0
    metric_mid = 0
    metric_low = 0

    for r in repos:
        for e in r.get("nfcore_tool_evidence", []):
            if e[4] == "exact":
                exact_entries += 1
            elif e[4] == "metric":
                metric_entries += 1
                score = e[5] if e[5] is not None else 0.0
                if score >= 0.9:
                    metric_high += 1
                elif score >= 0.5:
                    metric_mid += 1
                else:
                    metric_low += 1

    total_evidence = exact_entries + metric_entries
    total_categories = exact_entries + metric_high + metric_mid + metric_low

    if total_evidence == total_categories:
        print(
            f"\n  Plots 07.1 and 08 consistent: "
            f"{total_evidence} total, {exact_entries} exact, {metric_entries} metric"
        )
    else:
        print(
            f"\n  WARN: category sum {total_categories} != total evidence {total_evidence}"
        )


def ensure_nfcore_cache(cache_dir, quiet=False):
    cache_path = Path(cache_dir) / "nfcore_modules.txt"
    if cache_path.exists():
        return cache_path
    if not quiet:
        print("nf-core module list not cached — fetching from GitHub ...")
    try:
        nfcore_modules = fetch_nfcore_module_list(
            cache_path.parent / "api", ttl_seconds=3600
        )
        all_names = set(nfcore_modules)
        for name in nfcore_modules:
            if "/" in name:
                all_names.add(name.split("/")[0])
        cache_path.mkdir(parents=True, exist_ok=True)
        cache_path.write_text("\n".join(sorted(all_names)) + "\n")
        if not quiet:
            print(f"  Cached {len(all_names)} nf-core base names")
        return cache_path
    except Exception as e:
        print(f"  Warning: could not fetch nf-core module list ({e})")
        print(f"  Fallback: using inferred list from exact evidence entries")
