import os
import sys

from .core import (
    connected_subgraphs,
    domain_clusters,
    fan_patterns,
    graph_quality_analysis,
    load_graphs,
    load_patterns,
    summarize_templates,
    tool_cooccurrence,
    tool_popularity,
    topology_summary,
    transition_patterns,
)
from .plots import plot_results
from .reports import (
    _print_full_report,
    _print_report,
    _write_analysis_report_md,
    _write_full_report_dir,
)


def analyze(input_dir, patterns_dag_path):
    patterns = load_patterns(patterns_dag_path)
    graphs = load_graphs(input_dir)
    tool_wfs = tool_popularity(graphs)
    cooccur = tool_cooccurrence(tool_wfs, min_pipelines=3)
    topo = topology_summary(graphs)
    transitions = transition_patterns(patterns)
    domains, pipeline_detail = domain_clusters(tool_wfs, graphs)
    divergence, convergence = fan_patterns(graphs)
    catalog, pipeline_sgs, pairwise = connected_subgraphs(graphs)
    graph_quality = graph_quality_analysis(graphs)
    return (
        graphs,
        tool_wfs,
        cooccur,
        topo,
        transitions,
        domains,
        pipeline_detail,
        divergence,
        convergence,
        catalog,
        pairwise,
        graph_quality,
    )


def main(args):
    (
        graphs,
        tool_wfs,
        cooccur,
        topo,
        transitions,
        domains,
        pipeline_detail,
        divergence,
        convergence,
        catalog,
        pairwise,
        graph_quality,
    ) = analyze(args.input_dir, args.patterns_dag)

    # Compute template clustering from catalog
    templates, non_samtools_catalog = summarize_templates(catalog)

    # Always print summary to stdout
    _print_report(
        graphs,
        tool_wfs,
        cooccur,
        topo,
        transitions,
        domains,
        pipeline_detail,
        divergence,
        convergence,
        catalog=catalog,
        pairwise=pairwise,
        graph_quality=graph_quality,
        templates=templates,
        non_samtools_catalog=non_samtools_catalog,
    )

    # Write summary file
    summary_path = args.output or "analysis_report_summary.txt"
    with open(summary_path, "w") as f:
        orig = sys.stdout
        sys.stdout = f
        _print_report(
            graphs,
            tool_wfs,
            cooccur,
            topo,
            transitions,
            domains,
            pipeline_detail,
            divergence,
            convergence,
            catalog=catalog,
            pairwise=pairwise,
            graph_quality=graph_quality,
            templates=templates,
            non_samtools_catalog=non_samtools_catalog,
        )
        sys.stdout = orig
    print(f"Wrote {summary_path}", file=sys.stderr)

    # Write full report as directory of numbered files
    summary_dir = os.path.dirname(summary_path) or "."
    full_dir = os.path.join(summary_dir, "analysis_report_full")
    _write_full_report_dir(
        full_dir,
        graphs,
        tool_wfs,
        cooccur,
        topo,
        transitions,
        domains,
        pipeline_detail=pipeline_detail,
        divergence=divergence,
        convergence=convergence,
        catalog=catalog,
        pairwise=pairwise,
        graph_quality=graph_quality,
        templates=templates,
        non_samtools_catalog=non_samtools_catalog,
    )
    print(f"Wrote full report to {full_dir}/", file=sys.stderr)

    if args.plot_dir:
        plot_results(
            graphs,
            tool_wfs,
            cooccur,
            topo,
            transitions,
            domains,
            divergence,
            convergence,
            args.plot_dir,
            catalog=catalog,
            pairwise=pairwise,
            graph_quality=graph_quality,
            templates=templates,
            pipeline_detail=pipeline_detail,
            non_samtools_catalog=non_samtools_catalog,
            cores=args.cores,
            font_path=args.font_path,
        )
        _write_analysis_report_md(
            graphs,
            tool_wfs,
            transitions,
            divergence,
            convergence,
            domains,
            pipeline_detail,
            topo,
            args.plot_dir,
        )
