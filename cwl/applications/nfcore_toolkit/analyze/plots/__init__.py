import sys

from .basic import (
    _plot_cooccurrence_heatmap,
    _plot_edge_node_ratio,
    _plot_failure_categories,
    _plot_singleton_scatter,
    _plot_singletons_per_pipeline,
    _plot_tool_popularity,
)
from .common import _init_mpl, format_set
from .domains import (
    _plot_domain_clusters,
    _plot_domain_overlap_matrix,
    _plot_domain_tool_heatmap,
    _plot_pipeline_domain_detail,
)
from .module_origin import (
    _plot_module_origin,
    _plot_module_origin_aggregate,
    _plot_module_origin_norm,
    _plot_origin_set_distribution,
    _plot_self_loop_origin,
    _plot_tool_origin_mixed,
)
from .quality import _plot_graph_quality, _plot_pipeline_status
from .subgraphs import (
    _plot_colored_subgraph_topology,
    _plot_exact_convergence_distribution,
    _plot_exact_convergence_top,
    _plot_larger_subgraph_topology,
    _plot_non_only_samtools_subgraphs,
    _plot_subgraph_topology,
    _plot_top_connected_subgraphs,
    _plot_top_pipeline_pairs,
    _plot_top_size2_subgraphs,
)
from .templates import (
    _plot_template_cross_pair,
    _plot_template_diversity,
    _plot_template_topology,
    _plot_top_templates,
)
from .transitions import (
    _plot_convergence_patterns,
    _plot_divergence_patterns,
    _plot_sankey,
    _plot_self_loops,
    _plot_tool_chains,
    _plot_transition_network,
    _plot_transitions_frequency,
    _write_transition_trace,
)


def plot_results(
    graphs,
    tool_wfs,
    cooccur,
    topo,
    transitions,
    domains,
    divergence,
    convergence,
    plot_dir,
    catalog=None,
    pairwise=None,
    graph_quality=None,
    templates=None,
    pipeline_detail=None,
    non_samtools_catalog=None,
    cores=1,
    font_path=None,
):
    import os
    import time

    os.makedirs(plot_dir, exist_ok=True)
    os.makedirs(os.path.join(plot_dir, "transitions"), exist_ok=True)
    os.makedirs(os.path.join(plot_dir, "domains"), exist_ok=True)
    os.makedirs(os.path.join(plot_dir, "subgraphs"), exist_ok=True)
    os.makedirs(os.path.join(plot_dir, "templates"), exist_ok=True)
    os.makedirs(os.path.join(plot_dir, "module_origin"), exist_ok=True)

    # Suppress InheritableWarning spam from multiprocessing
    import warnings

    warnings.filterwarnings("ignore", category=UserWarning, module="multiprocessing")

    import os.path as _osp

    dom_dir = _osp.join(plot_dir, "domains")
    tra_dir = _osp.join(plot_dir, "transitions")
    sub_dir = _osp.join(plot_dir, "subgraphs")
    tem_dir = _osp.join(plot_dir, "templates")

    tasks = [
        ("tool_popularity.png", _plot_tool_popularity, (tool_wfs, plot_dir)),
        ("edge_node_ratio.png", _plot_edge_node_ratio, (topo, plot_dir)),
        ("domains/domain_clusters.png", _plot_domain_clusters, (domains, dom_dir)),
        (
            "domains/domain_overlap_matrix.png",
            _plot_domain_overlap_matrix,
            (graphs, dom_dir),
        ),
        (
            "cooccurrence_heatmap.png",
            _plot_cooccurrence_heatmap,
            (tool_wfs, cooccur, plot_dir),
        ),
        (
            "domains/domain_tool_heatmap.png",
            _plot_domain_tool_heatmap,
            (tool_wfs, domains, dom_dir),
        ),
        ("failure_categories.png", _plot_failure_categories, (graphs, plot_dir)),
        (
            "transitions/transition_network.png",
            _plot_transition_network,
            (transitions, tra_dir),
        ),
        (
            "transitions/transitions_frequency.png",
            _plot_transitions_frequency,
            (transitions, tool_wfs, tra_dir),
        ),
        (
            "transitions/tool_chains.png",
            _plot_tool_chains,
            (transitions, tra_dir),
        ),
        ("transitions/sankey.png", _plot_sankey, (transitions, tra_dir)),
        (
            "transitions/transition_trace.json",
            _write_transition_trace,
            (transitions, tool_wfs, tra_dir),
        ),
        (
            "singleton_scatter.png",
            _plot_singleton_scatter,
            (tool_wfs, topo, domains, plot_dir),
        ),
        (
            "singletons_per_pipeline.png",
            _plot_singletons_per_pipeline,
            (tool_wfs, plot_dir),
        ),
        (
            "transitions/self_loops.png",
            _plot_self_loops,
            (transitions, tra_dir),
        ),
        (
            "module_origin/pipeline_origin.png",
            _plot_module_origin,
            (graphs, plot_dir),
        ),
        (
            "module_origin/pipeline_origin_norm.png",
            _plot_module_origin_norm,
            (graphs, plot_dir),
        ),
        (
            "module_origin/origin_aggregate.png",
            _plot_module_origin_aggregate,
            (graphs, plot_dir),
        ),
        (
            "module_origin/tool_origin_mixed.png",
            _plot_tool_origin_mixed,
            (graphs, plot_dir),
        ),
        (
            "module_origin/tool_origin_sets.png",
            _plot_origin_set_distribution,
            (graphs, plot_dir),
        ),
        (
            "module_origin/tool_self_loop_origin.png",
            _plot_self_loop_origin,
            (transitions, graphs, plot_dir),
        ),
        (
            "transitions/divergence_patterns.png",
            _plot_divergence_patterns,
            (divergence, tra_dir),
        ),
        (
            "transitions/convergence_patterns.png",
            _plot_convergence_patterns,
            (convergence, tra_dir),
        ),
    ]

    if catalog is not None and pairwise is not None:
        tasks.append(
            (
                "subgraphs/top_connected_subgraphs.png",
                _plot_top_connected_subgraphs,
                (catalog, sub_dir),
            ),
        )
        tasks.append(
            (
                "subgraphs/top_size2_subgraphs.png",
                _plot_top_size2_subgraphs,
                (catalog, sub_dir),
            ),
        )
        tasks.append(
            (
                "subgraphs/top_pipeline_pairs.png",
                _plot_top_pipeline_pairs,
                (pairwise, sub_dir),
            ),
        )
        tasks.append(
            (
                "subgraphs/subgraph_topology.png",
                _plot_subgraph_topology,
                (catalog, sub_dir, font_path),
            ),
        )
        tasks.append(
            (
                "subgraphs/larger_subgraph_topology.png",
                _plot_larger_subgraph_topology,
                (catalog, sub_dir, font_path),
            ),
        )
        tasks.append(
            (
                "subgraphs/colored_subgraph_topology.png",
                _plot_colored_subgraph_topology,
                (catalog, sub_dir, font_path),
            ),
        )

    if templates is not None:
        tasks.append(
            (
                "templates/template_diversity.png",
                _plot_template_diversity,
                (templates, tem_dir),
            ),
        )
        tasks.append(
            (
                "templates/top_templates.png",
                _plot_top_templates,
                (templates, tem_dir),
            ),
        )
        tasks.append(
            (
                "templates/template_topology.png",
                _plot_template_topology,
                (templates, tem_dir),
            ),
        )
        if catalog is not None:
            tasks.append(
                (
                    "templates/template_cross_pair.png",
                    _plot_template_cross_pair,
                    (templates, catalog, tem_dir),
                ),
            )

    if pipeline_detail is not None:
        tasks.append(
            (
                "domains/pipeline_domain_heatmap.png",
                _plot_pipeline_domain_detail,
                (pipeline_detail, dom_dir),
            )
        )

    if non_samtools_catalog is not None:
        tasks.append(
            (
                "subgraphs/non_only_samtools_subgraphs.png",
                _plot_non_only_samtools_subgraphs,
                (non_samtools_catalog, sub_dir),
            )
        )

    if catalog is not None:
        tasks.append(
            (
                "subgraphs/exact_convergence_top.png",
                _plot_exact_convergence_top,
                (catalog, sub_dir),
            )
        )
        tasks.append(
            (
                "subgraphs/exact_convergence_distribution.png",
                _plot_exact_convergence_distribution,
                (catalog, sub_dir),
            )
        )

    if graph_quality is not None:
        *_, status_breakdown = graph_quality
        tasks.append(
            (
                "pipeline_status.png",
                _plot_pipeline_status,
                (status_breakdown, plot_dir),
            ),
        )
        tasks.append(
            ("graph_quality.png", _plot_graph_quality, (graph_quality, plot_dir)),
        )

    times = {}

    if cores > 1 and len(tasks) > 1:
        import multiprocessing
        from concurrent.futures import ProcessPoolExecutor, as_completed

        ctx = multiprocessing.get_context("spawn")
        with ProcessPoolExecutor(max_workers=cores, mp_context=ctx) as pool:
            fut_map = {}
            for name, fn, args in tasks:
                fut = pool.submit(fn, *args)
                fut_map[fut] = name
            for fut in as_completed(fut_map):
                name = fut_map[fut]
                t0 = time.perf_counter()
                fut.result()
                times[name] = time.perf_counter() - t0
    else:
        for name, fn, args in tasks:
            t0 = time.perf_counter()
            fn(*args)
            times[name] = time.perf_counter() - t0

    total = sum(times.values())
    for name, t in sorted(times.items(), key=lambda x: -x[1]):
        print(f"  {name}: {t:.2f}s", file=sys.stderr)
    print(
        f"  Total: {total:.2f}s across {len(tasks)} plots (cores={cores})",
        file=sys.stderr,
    )
    print(f"  Plots saved to {plot_dir}/", file=sys.stderr)
