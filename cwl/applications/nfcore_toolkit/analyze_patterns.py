#!/usr/bin/env python3
"""Analyze patterns across nf-core pipelines from DAG and API data."""

import argparse
import json
import os
import sys
from collections import defaultdict

TOOL_DOMAIN_MAP = {
    # microbiome
    "qiime2": "microbiome",
    "kraken2": "microbiome",
    "metaphlan": "microbiome",
    "humann": "microbiome",
    "bracken": "microbiome",
    "metabat2": "microbiome",
    "concoct": "microbiome",
    # single_cell
    "scanpy": "single_cell",
    "cellranger": "single_cell",
    "seurat": "single_cell",
    # epigenomics
    "macs2": "epigenomics",
    "deeptools": "epigenomics",
    "homer": "epigenomics",
    "chipseeker": "epigenomics",
    # genomics_variant
    "strelka": "genomics_variant",
    "manta": "genomics_variant",
    "mutect2": "genomics_variant",
    "freebayes": "genomics_variant",
    "gatk": "genomics_variant",
    "gatk4": "genomics_variant",
    "bcftools": "genomics_variant",
    "snpeff": "genomics_variant",
    "snpsift": "genomics_variant",
    "vep": "genomics_variant",
    "ensemblvep": "genomics_variant",
    "sentieon": "genomics_variant",
    # genomics_assembly
    "odgi": "genomics_assembly",
    "flye": "genomics_assembly",
    "shasta": "genomics_assembly",
    "spades": "genomics_assembly",
    "unicycler": "genomics_assembly",
    "quast": "genomics_assembly",
    "busco": "genomics_assembly",
    "abacas": "genomics_assembly",
    "bandage": "genomics_assembly",
    "canu": "genomics_assembly",
    "miniasm": "genomics_assembly",
    "raven": "genomics_assembly",
    "ravenassembly": "genomics_assembly",
    "mummer": "genomics_assembly",
    # phylogenetics
    "hmmer": "phylogenetics",
    "mafft": "phylogenetics",
    "fasttree": "phylogenetics",
    "raxml": "phylogenetics",
    "pangolin": "phylogenetics",
    "nextclade": "phylogenetics",
    "iqtree": "phylogenetics",
    "trimal": "phylogenetics",
    # immunology
    "presto": "immunology",
    "mixcr": "immunology",
    # rna_seq
    "salmon": "rna_seq",
    "star": "rna_seq",
    "kallisto": "rna_seq",
    "rsem": "rna_seq",
    "stringtie": "rna_seq",
    "featurecounts": "rna_seq",
    "htseq": "rna_seq",
    "hisat2": "rna_seq",
    # proteomics
    "maxquant": "proteomics",
    "msfragger": "proteomics",
    "openms": "proteomics",
}


def _tool_domain(tool):
    """Lookup domain for a tool; fallback to base name for dotted subtools (e.g. samtools.sort -> samtools)."""
    domain = TOOL_DOMAIN_MAP.get(tool)
    if domain:
        return domain
    if "." in tool:
        return TOOL_DOMAIN_MAP.get(tool.split(".")[0])
    return None


def load_graphs(input_dir):
    graphs = []
    for fname in sorted(os.listdir(input_dir)):
        if not fname.endswith(".graph.json"):
            continue
        with open(os.path.join(input_dir, fname)) as f:
            g = json.load(f)
        gr = g.get("graph", {})
        graphs.append(
            {
                "name": gr.get("name", "?"),
                "nodes": g.get("nodes", []),
                "links": g.get("links", []),
                "meta": gr,
            }
        )
    return graphs


def load_patterns(patterns_dag_path):
    with open(patterns_dag_path) as f:
        return json.load(f)


def tool_popularity(graphs):
    tool_wfs = defaultdict(set)
    for g in graphs:
        for n in g["nodes"]:
            app = n.get("app", "")
            if app:
                tool_wfs[app].add(g["name"])
    return tool_wfs


def tool_cooccurrence(tool_wfs, min_pipelines=2):
    top_tools = [t for t, ps in tool_wfs.items() if len(ps) >= min_pipelines]
    pairs = []
    for i, t1 in enumerate(top_tools):
        for t2 in top_tools[i + 1 :]:
            overlap = len(tool_wfs[t1] & tool_wfs[t2])
            if overlap >= 2:
                jaccard = overlap / len(tool_wfs[t1] | tool_wfs[t2])
                pairs.append(
                    (overlap, jaccard, t1, t2, len(tool_wfs[t1]), len(tool_wfs[t2]))
                )
    pairs.sort(key=lambda x: -x[0])
    return pairs


def topology_summary(graphs):
    topo = []
    for g in graphs:
        nnodes = len(g["nodes"])
        nedges = len(g["links"])
        ratio = nedges / nnodes if nnodes > 0 else 0
        tools = sorted({n.get("app", "") for n in g["nodes"] if n.get("app")})
        topo.append((g["name"], nnodes, nedges, ratio, tools))
    return topo


def transition_patterns(patterns):
    tc = patterns.get("transition_count", {})
    all_trans = []
    for src, trans in tc.items():
        if isinstance(trans, dict):
            for dst, v in trans.items():
                all_trans.append((v["count"], src, dst, v.get("workflows", [])))
    all_trans.sort(key=lambda x: -x[0])
    return all_trans


def domain_clusters(tool_wfs, graphs):
    domain_data = defaultdict(lambda: {"pipelines": [], "tools": defaultdict(list)})
    pipeline_detail = {}
    for g in graphs:
        pipeline_tools = {n.get("app", "") for n in g["nodes"] if n.get("app")}
        pipeline_domains = defaultdict(list)
        for tool in pipeline_tools:
            domain = _tool_domain(tool)
            if domain:
                pipeline_domains[domain].append(tool)
        all_domains = [(d, pipeline_domains[d]) for d in sorted(pipeline_domains)]
        if not pipeline_domains:
            domain_data["unclassified"]["pipelines"].append(
                (g["name"], [], 0.0, all_domains)
            )
            pipeline_detail[g["name"]] = all_domains
            continue
        best_domain = max(pipeline_domains, key=lambda d: (len(pipeline_domains[d]), d))
        best_tools = pipeline_domains[best_domain]
        total_matches = sum(len(v) for v in pipeline_domains.values())
        certainty = len(best_tools) / total_matches if total_matches > 0 else 0.0
        domain_data[best_domain]["pipelines"].append(
            (g["name"], best_tools, certainty, all_domains)
        )
        pipeline_detail[g["name"]] = all_domains
        for domain, tools in pipeline_domains.items():
            for t in tools:
                domain_data[domain]["tools"][t].append(g["name"])
    return dict(domain_data), dict(pipeline_detail)


def _find_self_loops(transitions):
    """Return self-loop transitions (src == dst) — potential toolkits with collapsed subtools."""
    return [(cnt, src) for cnt, src, dst, _ in transitions if src == dst]


def _build_chains(transitions):
    """Build 2-step tool chains (A->B->C) from transition data.

    Returns list of (count, a, b, c, sorted_pipelines) sorted descending by count.
    """
    trans_wf_map = {}
    for _, src, dst, wfs in transitions:
        trans_wf_map[(src, dst)] = set(wfs)
    chains = []
    for (a, b), wfs_ab in trans_wf_map.items():
        for (b2, c), wfs_bc in trans_wf_map.items():
            if b == b2:
                shared = wfs_ab & wfs_bc
                if len(shared) >= 2:
                    chains.append((len(shared), a, b, c, sorted(shared)))
    chains.sort(key=lambda x: -x[0])
    return chains


def fan_patterns(graphs):
    """Build divergence (fan-out) and convergence (fan-in) patterns from DAG links.

    For each tool, finds frequent sets of successors (divergence) and
    predecessors (convergence) across pipelines.

    Returns (divergence, convergence) where each is:
        dict[tool] = [(count, frozenset({neighbors}), [pipelines]), ...]
    """
    from collections import defaultdict

    div_agg = defaultdict(lambda: defaultdict(set))
    conv_agg = defaultdict(lambda: defaultdict(set))

    for g in graphs:
        pname = g["name"]
        node_app = {}
        for n in g.get("nodes", []):
            node_app[n.get("id", "")] = n.get("app", "")
        succ = defaultdict(set)
        pred = defaultdict(set)
        for link in g.get("links", []):
            src_id = link.get("source", "")
            dst_id = link.get("target", "")
            src_app = node_app.get(src_id, "")
            dst_app = node_app.get(dst_id, "")
            if src_app and dst_app and src_app != dst_app:
                succ[src_app].add(dst_app)
                pred[dst_app].add(src_app)
        for tool, successors in succ.items():
            if len(successors) >= 2:
                div_agg[tool][frozenset(successors)].add(pname)
        for tool, predecessors in pred.items():
            if len(predecessors) >= 2:
                conv_agg[tool][frozenset(predecessors)].add(pname)

    divergence = {}
    for tool, patterns in div_agg.items():
        items = [(len(ps), key, sorted(ps)) for key, ps in patterns.items()]
        items.sort(key=lambda x: -x[0])
        divergence[tool] = items

    convergence = {}
    for tool, patterns in conv_agg.items():
        items = [(len(ps), key, sorted(ps)) for key, ps in patterns.items()]
        items.sort(key=lambda x: -x[0])
        convergence[tool] = items

    return divergence, convergence


def _format_subgraph(labels, edges):
    """Render a subgraph as compact text.

    Groups edges by source node, e.g.:
        A → B → C                  (chain of 3)
        A → {B, C}                  (divergence)
        A → B, B → {C, D}          (branching)
    """
    out = {}
    for src, dst in edges:
        out.setdefault(src, []).append(dst)
    parts = []
    for src in sorted(out):
        targets = sorted(set(out[src]))
        if len(targets) == 1:
            parts.append(f"{src} → {targets[0]}")
        else:
            parts.append(f"{src} → {{{', '.join(targets)}}}")
    return "  ".join(parts)


def _enumerate_subgraphs(comp_nodes, comp_edges, max_size=6):
    """Enumerate all connected subgraphs (size 2 to max_size) within a component.

    Uses canonical ordering on node labels to avoid duplicates:
    each subgraph is only generated from its smallest-labeled start node.
    Returns set of (frozenset(labels), frozenset(edge_tuples)) keys.
    """
    adj = {}
    for src, dst in comp_edges:
        adj.setdefault(src, set()).add(dst)
        adj.setdefault(dst, set()).add(src)

    result = set()
    node_list = sorted(comp_nodes)

    for start in node_list:
        frontier = [(frozenset([start]), frozenset())]
        visited = set()

        while frontier:
            cur_nodes, cur_edges = frontier.pop()
            state = (cur_nodes, cur_edges)
            if state in visited:
                continue
            visited.add(state)

            if len(cur_nodes) >= 2:
                result.add((cur_nodes, cur_edges))

            if len(cur_nodes) >= max_size:
                continue

            boundary = set()
            for n in cur_nodes:
                for nb in adj.get(n, []):
                    if nb not in cur_nodes and nb > start:
                        boundary.add(nb)

            for nb in sorted(boundary):
                new_nodes = cur_nodes | {nb}
                new_edge_set = frozenset(
                    (s, t) for s, t in comp_edges if s in new_nodes and t in new_nodes
                )
                frontier.append((new_nodes, new_edge_set))

    return result


def connected_subgraphs(graphs, max_size=6):
    """Find all common connected subgraphs between every pair of pipelines.

    For each pair, computes the intersection of edge sets (same src→dst label),
    finds connected components within the intersection, then enumerates all
    connected subgraphs (size 2 to max_size) in each component.

    Returns:
        catalog: list of dicts sorted by (size desc, count desc)
        pipeline_subgraphs: dict[pipeline_name] = set of keys
        pairwise: list of (n_shared, a, b, [keys]) sorted by n_shared desc
    """
    from collections import defaultdict

    # Build per-pipeline edge sets
    pipeline_edges = {}
    for g in graphs:
        pname = g["name"]
        node_app = {}
        for n in g.get("nodes", []):
            node_app[n.get("id", "")] = n.get("app", "")
        edges = set()
        for link in g.get("links", []):
            src_id = link.get("source", "")
            dst_id = link.get("target", "")
            src_app = node_app.get(src_id, "")
            dst_app = node_app.get(dst_id, "")
            if src_app and dst_app and src_app != dst_app:
                edges.add((src_app, dst_app))
        if edges:
            pipeline_edges[pname] = frozenset(edges)

    pnames = list(pipeline_edges.keys())
    subgraph_pipelines = defaultdict(set)
    subgraph_pairs = defaultdict(set)

    for i in range(len(pnames)):
        for j in range(i + 1, len(pnames)):
            a, b = pnames[i], pnames[j]
            common = pipeline_edges[a] & pipeline_edges[b]
            if not common:
                continue

            # Build undirected adjacency from common edges
            adj = {}
            all_nodes = set()
            seen_pairs = set()
            for src, dst in common:
                pair = (src, dst)
                if pair in seen_pairs:
                    continue
                seen_pairs.add(pair)
                adj.setdefault(src, set()).add(dst)
                adj.setdefault(dst, set()).add(src)
                all_nodes.add(src)
                all_nodes.add(dst)

            # Find connected components
            visited = set()
            for node in all_nodes:
                if node in visited:
                    continue
                comp_nodes = set()
                queue = [node]
                while queue:
                    n = queue.pop(0)
                    if n in visited:
                        continue
                    visited.add(n)
                    comp_nodes.add(n)
                    for nb in adj.get(n, []):
                        if nb not in visited:
                            queue.append(nb)

                if len(comp_nodes) < 2:
                    continue

                # Collect directed edges within this component
                comp_edges = frozenset(
                    (s, t) for s, t in common if s in comp_nodes and t in comp_nodes
                )

                sub_max = min(max_size, len(comp_nodes))
                sg_keys = _enumerate_subgraphs(comp_nodes, comp_edges, sub_max)

                for key in sg_keys:
                    subgraph_pipelines[key].add(a)
                    subgraph_pipelines[key].add(b)
                    subgraph_pairs[key].add(frozenset({a, b}))

    # Build catalog
    catalog = []
    for key, pipelines in subgraph_pipelines.items():
        labels, edge_pairs = key
        catalog.append(
            {
                "key": key,
                "labels": labels,
                "edges": edge_pairs,
                "size": len(labels),
                "pipelines": sorted(pipelines),
                "count": len(pipelines),
            }
        )
    catalog.sort(key=lambda x: (-x["size"], -x["count"]))

    # Build per-pipeline index
    pipeline_sgs = defaultdict(set)
    for key, pipelines in subgraph_pipelines.items():
        for p in pipelines:
            pipeline_sgs[p].add(key)

    # Build pairwise shared
    pair_agg = defaultdict(set)
    for key, pairs in subgraph_pairs.items():
        for pair in pairs:
            a, b = tuple(pair)
            pair_agg[(a, b)].add(key)

    pairwise = [
        (len(keys), a, b, sorted(str(k) for k in keys))
        for (a, b), keys in pair_agg.items()
    ]
    pairwise.sort(key=lambda x: -x[0])

    return catalog, dict(pipeline_sgs), pairwise


def graph_quality_analysis(graphs):
    """Analyze graph quality: empty DAG failures + disconnected components.

    Returns:
        empty_by_category: dict[failure_category] = [(pipeline_name, meta_dict), ...]
        empty_external: list of (pipeline_name, meta_dict) with 0 nodes but no failure
        split_dags: list of (pipeline_name, n_components, n_nodes, n_edges)
        isolated_dags: list of (pipeline_name, n_nodes, n_edges) with 0 components (no edges)
    """
    empty_by_category = {}
    empty_external = []
    split_dags = []
    isolated_dags = []

    for g in graphs:
        meta = g.get("meta", {})
        pname = meta.get("name", g.get("name", "?"))
        nodes = g.get("nodes", [])
        links = g.get("links", [])
        n_nodes = len(nodes)
        n_links = len(links)

        if n_nodes == 0:
            fc = meta.get("failure_classification", {})
            if fc:
                cat = fc.get("category", "unknown")
                archived = meta.get("archived", False)
                lr = meta.get("latest_release", "") or ""
                if archived:
                    status = "archived"
                elif lr == "dev":
                    status = "unreleased"
                else:
                    status = "active"
                empty_by_category.setdefault(cat, []).append(
                    (
                        pname,
                        {"archived": archived, "status": status, "latest_release": lr},
                    )
                )
            else:
                empty_external.append((pname, {}))
            continue

        # Build undirected adjacency for tool nodes only
        node_app = {}
        for n in nodes:
            nid = n.get("id", "")
            app = n.get("app", "")
            if app:
                node_app[nid] = app

        adj = {}
        for link in links:
            src_id = link.get("source", "")
            dst_id = link.get("target", "")
            src_app = node_app.get(src_id, "")
            dst_app = node_app.get(dst_id, "")
            if src_app and dst_app and src_app != dst_app:
                adj.setdefault(src_app, set()).add(dst_app)
                adj.setdefault(dst_app, set()).add(src_app)

        all_tools = set(adj.keys())
        visited = set()
        components = 0
        for tool in all_tools:
            if tool in visited:
                continue
            components += 1
            queue = [tool]
            while queue:
                cur = queue.pop()
                if cur in visited:
                    continue
                visited.add(cur)
                for nb in adj.get(cur, set()):
                    if nb not in visited:
                        queue.append(nb)

        if components == 0 and n_nodes > 0:
            isolated_dags.append((pname, n_nodes, n_links))
        elif components >= 2:
            split_dags.append((pname, components, n_nodes, n_links))

    # Compute overall status breakdown for all pipelines
    status_counts = {"active": 0, "archived": 0, "unreleased": 0}
    status_success = {"active": 0, "archived": 0, "unreleased": 0}
    status_fail = {"active": 0, "archived": 0, "unreleased": 0}
    for g in graphs:
        meta = g.get("meta", {})
        archived = meta.get("archived", False)
        lr = meta.get("latest_release", "") or ""
        status = "archived" if archived else ("unreleased" if lr == "dev" else "active")
        status_counts[status] += 1
        if len(g.get("nodes", [])) > 0:
            status_success[status] += 1
        else:
            status_fail[status] += 1

    status_breakdown = {
        "counts": status_counts,
        "success": status_success,
        "fail": status_fail,
    }

    return (
        empty_by_category,
        empty_external,
        split_dags,
        isolated_dags,
        status_breakdown,
    )


def module_origin_summary(graphs):
    """Aggregate unique (app, origin) pairs per pipeline.

    Each distinct tool+origin combination is counted once per pipeline
    (e.g. two samtools.index nodes count as 1 for nf-core).
    Handles backward compat: nodes without language_metadata are 'unknown'.
    Returns (total_unique, {origin: count}, {pipeline_name: {origin: count}}).
    """
    from collections import defaultdict

    totals = defaultdict(int)
    pipeline_origins = {}
    for g in graphs:
        pipeline = g.get("name", "?")
        p_counts = defaultdict(int)
        seen = set()
        for n in g.get("nodes", []):
            meta = n.get("language_metadata", {}) or {}
            origin = meta.get("module_origin", "unknown")
            app = n.get("app", "")
            key = (app, origin)
            if key not in seen:
                seen.add(key)
                p_counts[origin] += 1
                totals[origin] += 1
        pipeline_origins[pipeline] = dict(p_counts)
    total_unique = sum(totals.values())
    return total_unique, dict(totals), pipeline_origins


def _print_report(
    graphs,
    tool_wfs,
    cooccur,
    topo,
    transitions,
    domains,
    pipeline_detail=None,
    divergence=None,
    convergence=None,
    catalog=None,
    pairwise=None,
    graph_quality=None,
):
    n_total = len(graphs)
    n_success = sum(1 for g in graphs if len(g["nodes"]) > 0)
    n_empty = n_total - n_success
    tools_sorted = sorted(tool_wfs.items(), key=lambda x: -len(x[1]))
    total_unique_tools = len(tool_wfs)
    singletons = [(t, list(ps)[0]) for t, ps in tool_wfs.items() if len(ps) == 1]

    print(f"Pipelines: {n_total} ({n_success} with DAG, {n_empty} empty)")
    print(
        f"Unique tools: {total_unique_tools} ({len(singletons)} singletons = {100 * len(singletons) // total_unique_tools}%)"
    )
    print()

    total_unique, mo_totals, _ = module_origin_summary(graphs)
    if total_unique > 0:
        print("=== Module origin ===")
        for origin in ["nf-core", "local", "heuristic", "unknown"]:
            cnt = mo_totals.get(origin, 0)
            if cnt:
                print(f"  {origin:10s} {cnt:4d} unique ({100 * cnt // total_unique}%)")
        print()

    if graph_quality:
        (
            empty_by_category,
            empty_external,
            split_dags,
            isolated_dags,
            status_breakdown,
        ) = graph_quality
        n_total = len(graphs)
        n_empty = sum(len(v) for v in empty_by_category.values()) + len(empty_external)
        print("=== Graph quality ===")
        print(f"  Empty DAGs: {n_empty}/{n_total} ({100 * n_empty // n_total}%)")
        for cat in [
            "preview_failed",
            "timeout",
            "config_parsing",
            "permissions",
            "unknown_config",
            "unclassified",
        ]:
            items = empty_by_category.get(cat, [])
            if items:
                tag = {
                    "active": "",
                    "archived": " (archived)",
                    "unreleased": " (unreleased)",
                }
                samples = ", ".join(
                    f"{p.split('/')[-1]}{tag.get(m.get('status', 'active'), '')}"
                    for p, m in items[:4]
                )
                if len(items) > 4:
                    samples += f", ... ({len(items)} total)"
                print(f"    {cat:20s} {len(items):2d}: {samples}")
        if empty_external:
            tag = {
                "active": "",
                "archived": " (archived)",
                "unreleased": " (unreleased)",
            }
            samples = ", ".join(
                f"{p.split('/')[-1]}{tag.get(m.get('status', 'active'), '')}"
                for p, m in empty_external[:4]
            )
            print(f"    {'external':20s} {len(empty_external):2d}: {samples}")
        print(
            "    Status: (unreleased) = latest_release=='dev', never had a stable release"
        )
        if split_dags:
            split_dags.sort(key=lambda x: -x[1])
            tops = ", ".join(
                f"{p.split('/')[-1]}({c})" for p, c, _, _ in split_dags[:5]
            )
            print(f"  Split DAGs (2+ components): {len(split_dags)}")
            print(f"    Most fragmented: {tops}")
        if isolated_dags:
            print(f"  Isolated DAGs (0 edges): {len(isolated_dags)}")
        print()

    if graph_quality:
        _, _, _, _, status_breakdown = graph_quality
        print("=== Pipeline status ===")
        total = sum(status_breakdown["counts"].values())
        for st in ["active", "archived", "unreleased"]:
            cnt = status_breakdown["counts"][st]
            if cnt:
                ok = status_breakdown["success"][st]
                fail = status_breakdown["fail"][st]
                pct = 100 * cnt // total
                ok_pct = 100 * ok // cnt if cnt else 0
                print(
                    f"  {st:12s} {cnt:3d} ({pct:2d}%) — {ok} DAG success ({ok_pct}%), {fail} empty"
                )
        print()

    print("=== Universal plumbing core (tools in >=20% of pipelines) ===")
    for t, ps in tools_sorted:
        if len(ps) < n_total * 0.2:
            break
        print(f"  {t:20s} {len(ps):3d} pipelines ({100 * len(ps) // n_total}%)")
    print()

    print("=== Top 20 by pipeline count ===")
    for t, ps in tools_sorted[:20]:
        print(f"  {t:20s} {len(ps):3d} pipelines")
    print()

    print("=== Highest Jaccard co-occurrence ===")
    print(
        "  Jaccard = overlap / union | overlap = pipelines using both | sizes = (pipelines using A, pipelines using B)"
    )
    print("  1.0 = always together, 0.0 = never together")
    for cnt, jac, t1, t2, n1, n2 in cooccur[:15]:
        print(
            f"  {t1:15s} + {t2:15s}  Jaccard={jac:.2f}  overlap={cnt:2d}  sizes=({n1},{n2})"
        )
    print()

    print("=== Top 20 most common transitions (DAG Markov model) ===")
    for cnt, src, dst, _wfs in transitions[:20]:
        print(f"  {src:20s} -> {dst:20s}  ({cnt:3d} edges)")
    print()

    chains = _build_chains(transitions)
    if chains:
        print("=== Top 15 2-step tool chains ===")
        for cnt, a, b, c, _ in chains[:15]:
            print(f"  {a:20s} -> {b:20s} -> {c:20s}  ({cnt:3d} pipelines)")
        print()

    if divergence:
        flat = sorted(
            [
                (cnt, tool, nset)
                for tool, items in divergence.items()
                for cnt, nset, _ in items
            ],
            key=lambda x: -x[0],
        )
        print("=== Top 10 divergence patterns (tool \u2192 {successors}) ===")
        for cnt, tool, nset in flat[:10]:
            print(f"  {tool:20s} \u2192 {format_set(nset):40s} ({cnt:3d} pipelines)")
        print()

    if convergence:
        flat = sorted(
            [
                (cnt, tool, nset)
                for tool, items in convergence.items()
                for cnt, nset, _ in items
            ],
            key=lambda x: -x[0],
        )
        print("=== Top 10 convergence patterns ({predecessors} \u2192 tool) ===")
        for cnt, tool, nset in flat[:10]:
            print(f"  {format_set(nset):40s} \u2192 {tool:20s} ({cnt:3d} pipelines)")
        print()

    self_loops = _find_self_loops(transitions)
    if self_loops:
        print("=== Potential toolkits (self-loops — collapsed subtools) ===")
        print(
            "  Self-loops suggest a tool with multiple subprocesses collapsing to the same name."
        )
        print(
            "  Subtool resolution is now module-path-based — add module map entries to recover identity."
        )
        print()
        for cnt, tool in self_loops:
            print(f"  {tool:20s} -> {tool:20s}  ({cnt:3d} edges)")
        print()

    print("=== Topology extremes ===")
    topo.sort(key=lambda x: -x[1])
    print("  Largest:")
    for p, n, e, r, _ in topo[:5]:
        print(f"    {p:40s} nodes={n:3d}  edges={e:3d}  ratio={r:.2f}")
    nonempty = [x for x in topo if x[1] > 0]
    nonempty.sort(key=lambda x: -x[3])
    print("  Highest edge/node ratio (non-empty DAGs):")
    for p, n, e, r, _ in nonempty[:5]:
        print(f"    {p:40s} nodes={n:3d}  edges={e:3d}  ratio={r:.2f}")
    nonempty.sort(key=lambda x: x[3])
    print("  Lowest edge/node ratio (chain-like):")
    for p, n, e, r, _ in nonempty[:5]:
        print(f"    {p:40s} nodes={n:3d}  edges={e:3d}  ratio={r:.2f}")
    print()

    print("=== Domain clusters ===")
    for dt, data in sorted(domains.items()):
        pipeline_names = [p[0] for p in data["pipelines"]]
        tool_summary = "; ".join(
            f"{t} in {len(ps)}" for t, ps in sorted(data["tools"].items())
        )
        certs_str = ", ".join(f"{p[0]}({p[2]:.2f})" for p in data["pipelines"])
        print(
            f"  {dt:20s} {len(pipeline_names):2d} pipelines: {', '.join(sorted(pipeline_names)[:5])}"
        )
        print(f"  {'':20s} found via: {tool_summary}")
        if all(len(p) >= 4 for p in data["pipelines"]):
            print(f"  {'':20s} certainty: {certs_str}")
    print()

    print("=== Pipeline-domain detail ===")
    detail = pipeline_detail or {}
    if detail:
        print(f"  {'Pipeline':35s} {'Domain':20s} {'Cert.':>6s}  Tools")
        print(f"  {'-' * 35} {'-' * 20} {'-' * 6}  {'-' * 30}")
        for pname in sorted(detail):
            entries = detail[pname]
            for i, (domain, tools) in enumerate(entries):
                cert = (
                    f"{len(tools) / sum(len(t) for _, t in entries):.2f}"
                    if len(entries) > 1
                    else "1.00"
                )
                tool_str = ", ".join(tools[:5])
                if i == 0:
                    print(f"  {pname:35s} {domain:20s} {cert:>6s}  {tool_str}")
                else:
                    print(f"  {'':35s} {domain:20s} {cert:>6s}  {tool_str}")
        print()

    if catalog:
        print(
            f"=== Top 15 most common connected subgraphs ({len(catalog)} unique motifs total) ==="
        )
        print(
            "  Each entry is a distinct (node_set, edge_set) combination. All counts are unique —"
        )
        print("  no duplicate subgraph is counted twice for the same pipeline.")
        for entry in catalog[:15]:
            text = _format_subgraph(entry["labels"], entry["edges"])
            print(f"  size={entry['size']}  {text}  ({entry['count']:3d} pipelines)")
        print()

    if pairwise:
        print("=== Top 15 pipeline pairs with most shared subgraphs ===")
        print(
            "  Count = distinct connected subgraphs (node_set, edge_set) shared within each pair."
        )
        print(
            "  A single large shared component produces many subset subgraphs, inflating counts."
        )
        print(
            "  E.g., atacseq/chipseq share a large component; 17k = all connected subsets, not 17k independent motifs."
        )
        for cnt, a, b, _keys in pairwise[:15]:
            print(f"  {a:35s} \u2194 {b:35s}  ({cnt:2d} shared)")
        print()

    print("=== Example singleton tools ===")
    for t, wf in singletons[:20]:
        print(f"  {t:20s} only in {wf}")


def _print_full_report(
    graphs,
    tool_wfs,
    cooccur,
    topo,
    transitions,
    domains,
    pipeline_detail=None,
    divergence=None,
    convergence=None,
    catalog=None,
    pairwise=None,
    graph_quality=None,
):
    """Print comprehensive report with ALL data (not truncated)."""
    n_total = len(graphs)
    n_success = sum(1 for g in graphs if len(g["nodes"]) > 0)
    n_empty = n_total - n_success
    tools_sorted = sorted(tool_wfs.items(), key=lambda x: -len(x[1]))
    total_unique_tools = len(tool_wfs)
    singletons = [(t, list(ps)[0]) for t, ps in tool_wfs.items() if len(ps) == 1]

    print(f"Pipelines: {n_total} ({n_success} with DAG, {n_empty} empty)")
    print(f"Unique tools: {total_unique_tools} ({len(singletons)} singletons)")
    print()

    total_unique, mo_totals, pipeline_origins = module_origin_summary(graphs)
    if total_unique > 0:
        print("=== Module origin ===")
        print(f"  {'Origin':10s} {'Unique':>6s} {'%':>4s}")
        print(f"  {'-' * 10} {'-' * 6} {'-' * 4}")
        for origin in ["nf-core", "local", "heuristic", "unknown"]:
            cnt = mo_totals.get(origin, 0)
            if cnt:
                print(f"  {origin:10s} {cnt:6d} {100 * cnt // total_unique:3d}%")
        print()
        print("  Per-pipeline detail:")
        for pname in sorted(pipeline_origins):
            counts = pipeline_origins[pname]
            parts = ", ".join(f"{k}={v}" for k, v in sorted(counts.items()))
            print(f"    {pname:35s} {parts}")
        print()

    if graph_quality:
        (
            empty_by_category,
            empty_external,
            split_dags,
            isolated_dags,
            status_breakdown,
        ) = graph_quality
        n_empty = sum(len(v) for v in empty_by_category.values()) + len(empty_external)
        print("=== Graph quality ===")
        print(f"  Empty DAGs: {n_empty}/{n_total} ({100 * n_empty // n_total}%)")
        for cat in [
            "preview_failed",
            "timeout",
            "config_parsing",
            "permissions",
            "unknown_config",
            "unclassified",
        ]:
            items = empty_by_category.get(cat, [])
            if items:
                for pname, meta in items:
                    tag = {
                        "active": "",
                        "archived": " (archived)",
                        "unreleased": " (unreleased)",
                    }
                    suffix = tag.get(meta.get("status", "active"), "")
                    print(f"    {cat:20s} {pname}{suffix}")
        if empty_external:
            for pname, _ in empty_external:
                print(f"    {'external':20s} {pname}")
        if split_dags:
            split_dags.sort(key=lambda x: -x[1])
            print(f"  Split DAGs (2+ components): {len(split_dags)}")
            print(f"  {'Pipeline':40s} {'Comp':>4s} {'Nodes':>5s} {'Edges':>5s}")
            print(f"  {'-' * 40} {'-' * 4} {'-' * 5} {'-' * 5}")
            for pname, comp, nn, ne in split_dags:
                print(f"  {pname:40s} {comp:4d} {nn:5d} {ne:5d}")
        if isolated_dags:
            print(f"  Isolated DAGs (0 edges): {len(isolated_dags)}")
            for pname, nn, ne in isolated_dags:
                print(f"    {pname:40s} nodes={nn} edges={ne}")
        print()

    if graph_quality:
        _, _, _, _, status_breakdown = graph_quality
        print("=== Pipeline status ===")
        total = sum(status_breakdown["counts"].values())
        for st in ["active", "archived", "unreleased"]:
            cnt = status_breakdown["counts"][st]
            if cnt:
                ok = status_breakdown["success"][st]
                fail = status_breakdown["fail"][st]
                pct = 100 * cnt // total
                ok_pct = 100 * ok // cnt if cnt else 0
                print(
                    f"  {st:12s} {cnt:3d} ({pct:2d}%) — {ok} DAG success ({ok_pct}%), {fail} empty"
                )
        print()

    print("=== All tools with pipeline counts ===")
    for t, ps in tools_sorted:
        pipelines = ", ".join(sorted(ps))
        print(f"  {t:25s} {len(ps):3d} pipelines: {pipelines}")
    print()

    print("=== All co-occurrences ===")
    print("  Jaccard = overlap / union | overlap = pipelines using both")
    for cnt, jac, t1, t2, n1, n2 in cooccur:
        print(
            f"  {t1:15s} + {t2:15s}  Jaccard={jac:.2f}  overlap={cnt:2d}  sizes=({n1},{n2})"
        )
    print()

    print("=== All transitions ===")
    for cnt, src, dst, wfs in transitions:
        pipelines = ", ".join(sorted(wfs))
        print(f"  {src:20s} -> {dst:20s}  ({cnt:3d} edges)  pipelines={pipelines}")
    print()

    chains = _build_chains(transitions)
    if chains:
        print("=== All 2-step tool chains ===")
        for cnt, a, b, c, pl in chains:
            pipelines = ", ".join(pl)
            print(f"  {a:20s} -> {b:20s} -> {c:20s}  ({cnt:3d} pipelines)  {pipelines}")
        print()

    if divergence:
        flat = sorted(
            [
                (cnt, tool, nset, pl)
                for tool, items in divergence.items()
                for cnt, nset, pl in items
            ],
            key=lambda x: -x[0],
        )
        print("=== All divergence patterns (tool \u2192 {successors}) ===")
        for cnt, tool, nset, pl in flat:
            pipelines = ", ".join(pl)
            print(
                f"  {tool:20s} \u2192 {format_set(nset):40s} ({cnt:3d} pipelines)  {pipelines}"
            )
        print()

    if convergence:
        flat = sorted(
            [
                (cnt, tool, nset, pl)
                for tool, items in convergence.items()
                for cnt, nset, pl in items
            ],
            key=lambda x: -x[0],
        )
        print("=== All convergence patterns ({predecessors} \u2192 tool) ===")
        for cnt, tool, nset, pl in flat:
            pipelines = ", ".join(pl)
            print(
                f"  {format_set(nset):40s} \u2192 {tool:20s} ({cnt:3d} pipelines)  {pipelines}"
            )
        print()

    self_loops = _find_self_loops(transitions)
    if self_loops:
        print("=== Potential toolkits (self-loops) ===")
        for cnt, tool in self_loops:
            print(f"  {tool:20s} -> {tool:20s}  ({cnt:3d} edges)")
        print()

    print("=== Topology (all pipelines) ===")
    print(f"  {'Pipeline':40s} {'Nodes':>5s} {'Edges':>5s} {'Ratio':>5s}  Tools")
    print(f"  {'-' * 40} {'-' * 5} {'-' * 5} {'-' * 5}  {'-' * 30}")
    topo_sorted = sorted(topo, key=lambda x: -x[1])
    for pname, nnodes, nedges, ratio, tools in topo_sorted:
        tool_str = ", ".join(sorted(tools)) if tools else "—"
        print(f"  {pname:40s} {nnodes:5d} {nedges:5d} {ratio:.2f}  {tool_str}")
    print()

    print("=== Domain clusters (all) ===")
    for dt, data in sorted(domains.items()):
        pipeline_names = [p[0] for p in data["pipelines"]]
        tool_summary = "; ".join(
            f"{t} in {len(ps)}" for t, ps in sorted(data["tools"].items())
        )
        certs_str = ", ".join(f"{p[0]}({p[2]:.2f})" for p in data["pipelines"])
        print(
            f"  {dt:20s} {len(pipeline_names):2d} pipelines: {', '.join(sorted(pipeline_names))}"
        )
        print(f"  {'':20s} found via: {tool_summary}")
        print(f"  {'':20s} certainty: {certs_str}")
    print()

    print("=== Pipeline-domain detail ===")
    detail = pipeline_detail or {}
    if detail:
        print(f"  {'Pipeline':35s} {'Domain':20s} {'Cert.':>6s}  Tools")
        print(f"  {'-' * 35} {'-' * 20} {'-' * 6}  {'-' * 30}")
        for pname in sorted(detail):
            entries = detail[pname]
            for i, (domain, tools) in enumerate(entries):
                cert = (
                    f"{len(tools) / sum(len(t) for _, t in entries):.2f}"
                    if len(entries) > 1
                    else "1.00"
                )
                tool_str = ", ".join(tools[:5])
                if i == 0:
                    print(f"  {pname:35s} {domain:20s} {cert:>6s}  {tool_str}")
                else:
                    print(f"  {'':35s} {domain:20s} {cert:>6s}  {tool_str}")
        print()

    print("=== All singleton tools ===")
    for t, wf in singletons:
        print(f"  {t:20s} only in {wf}")
    print()

    if catalog:
        print(
            f"=== All common connected subgraphs ({len(catalog)} unique motifs total) ==="
        )
        print(
            "  Each entry is a distinct (node_set, edge_set) combination. All counts are unique —"
        )
        print("  no duplicate subgraph is counted twice for the same pipeline.")
        for entry in catalog:
            text = _format_subgraph(entry["labels"], entry["edges"])
            print(f"  size={entry['size']}  {text}  ({entry['count']:3d} pipelines)")
        print()

    if pairwise:
        print("=== All pipeline pairs with shared subgraphs ===")
        print(
            "  Count = distinct connected subgraphs (node_set, edge_set) shared within each pair."
        )
        print(
            "  A single large shared component produces many subset subgraphs, inflating counts."
        )
        print(
            "  E.g., atacseq/chipseq share a large component; 17k = all connected subsets, not 17k independent motifs."
        )
        for cnt, a, b, _keys in pairwise:
            print(f"  {a:35s} \u2194 {b:35s}  ({cnt:2d} shared)")
        print()


def _init_mpl():
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import seaborn as sns

    sns.set_style("whitegrid")
    return plt


def _plot_tool_popularity(tool_wfs, plot_dir):
    import os

    plt = _init_mpl()
    tools_sorted = sorted(tool_wfs.items(), key=lambda x: -len(x[1]))
    total = len(tool_wfs)
    singletons = sum(1 for _, ps in tool_wfs.items() if len(ps) == 1)
    top30 = tools_sorted[:30]
    names = [t for t, _ in top30]
    counts = [len(ps) for _, ps in top30]
    fig, ax = plt.subplots(figsize=(10, 6))
    ax.barh(range(len(names)), counts, color="steelblue")
    ax.set_yticks(range(len(names)))
    ax.set_yticklabels(names)
    ax.set_xlabel("Pipelines")
    ax.set_title("Top 30 tools by pipeline count")
    ax.text(
        0.95,
        0.05,
        f"Total: {total} | Singletons: {singletons} ({100 * singletons // total}%)",
        transform=ax.transAxes,
        ha="right",
        va="bottom",
        fontsize=10,
        bbox=dict(boxstyle="round", facecolor="wheat", alpha=0.5),
    )
    ax.invert_yaxis()
    plt.tight_layout()
    fig.savefig(os.path.join(plot_dir, "tool_popularity.png"), dpi=150)
    plt.close(fig)


def _plot_edge_node_ratio(topo, plot_dir):
    import os

    plt = _init_mpl()
    nonempty = [(p, n, e, r) for p, n, e, r, _ in topo if n > 0]
    if not nonempty:
        return
    ratios = [r for _, _, _, r in nonempty]
    fig, ax = plt.subplots(figsize=(8, 5))
    ax.hist(ratios, bins=20, color="steelblue", edgecolor="white")
    ax.axvline(
        sum(ratios) / len(ratios),
        color="red",
        linestyle="--",
        label=f"mean={sum(ratios) / len(ratios):.2f}",
    )
    ax.axvline(
        sorted(ratios)[len(ratios) // 2],
        color="green",
        linestyle=":",
        label=f"median={sorted(ratios)[len(ratios) // 2]:.2f}",
    )
    ax.set_xlabel("Edge / node ratio")
    ax.set_ylabel("Pipelines")
    ax.set_title("DAG topology diversity")
    ax.legend()
    plt.tight_layout()
    fig.savefig(os.path.join(plot_dir, "edge_node_ratio.png"), dpi=150)
    plt.close(fig)


def _plot_domain_clusters(domains, plot_dir):
    import os

    plt = _init_mpl()
    dt_names = sorted(domains.keys())
    if not dt_names:
        return
    fig, ax = plt.subplots(figsize=(10, 6))
    import seaborn as sns

    colors = sns.color_palette("husl", len(dt_names))
    y_pos = range(len(dt_names))
    for i, dt in enumerate(dt_names):
        pipelines = domains[dt].get("pipelines", [])
        total = len(pipelines)
        certain = sum(1 for p in pipelines if p[2] >= 1.0)
        uncertain = total - certain
        if certain > 0:
            ax.barh(
                i, certain, color=colors[i], hatch="", label=dt if certain > 0 else ""
            )
        if uncertain > 0:
            ax.barh(i, uncertain, left=certain, color=colors[i], hatch="///", alpha=0.7)
        label = f"{total} pipeline{'s' if total != 1 else ''}"
        if uncertain > 0:
            label += f"\n({uncertain} uncertain)"
        ax.text(total + 0.3, i, label, va="center", fontsize=9)

    ax.set_yticks(list(y_pos))
    ax.set_yticklabels(dt_names)
    ax.set_xlabel("Pipelines")
    ax.set_title("Domain clusters  (solid = certain, hatched = mixed-domain)")
    from matplotlib.patches import Patch

    legend_elements = [
        Patch(facecolor="gray", alpha=0.5, label="certain (single-domain)"),
        Patch(
            facecolor="gray", alpha=0.5, hatch="///", label="uncertain (multi-domain)"
        ),
    ]
    ax.legend(handles=legend_elements, loc="lower right", fontsize=8)
    plt.tight_layout()
    fig.savefig(os.path.join(plot_dir, "domain_clusters.png"), dpi=150)
    plt.close(fig)


def _plot_domain_overlap_matrix(graphs, plot_dir):
    import os
    from collections import defaultdict

    plt = _init_mpl()
    import seaborn as sns

    pipeline_domain_counts = defaultdict(lambda: defaultdict(int))
    for g in graphs:
        pipeline_tools = {n.get("app", "") for n in g["nodes"] if n.get("app")}
        for tool in pipeline_tools:
            domain = _tool_domain(tool)
            if domain:
                pipeline_domain_counts[g["name"]][domain] += 1
    if not pipeline_domain_counts:
        return
    all_domains = sorted(
        {d for counts in pipeline_domain_counts.values() for d in counts}
    )
    n = len(all_domains)
    if n < 2:
        return
    import numpy as np

    overlap = np.zeros((n, n), dtype=int)
    for counts in pipeline_domain_counts.values():
        doms = [d for d in all_domains if counts.get(d, 0) > 0]
        for d1 in doms:
            for d2 in doms:
                i, j = all_domains.index(d1), all_domains.index(d2)
                overlap[i][j] += 1
    fig, ax = plt.subplots(figsize=(8, 7))
    sns.heatmap(
        overlap,
        xticklabels=all_domains,
        yticklabels=all_domains,
        annot=True,
        fmt="d",
        cmap="YlOrRd",
        ax=ax,
        square=True,
    )
    ax.set_title("Domain \u00d7 Domain co-occurrence (pipelines sharing both)")
    plt.setp(ax.get_xticklabels(), rotation=30, ha="right", fontsize=9)
    plt.setp(ax.get_yticklabels(), fontsize=9)
    plt.tight_layout()
    fig.savefig(os.path.join(plot_dir, "domain_overlap_matrix.png"), dpi=150)
    plt.close(fig)


def _plot_domain_tool_heatmap(tool_wfs, domains, plot_dir):
    import os

    plt = _init_mpl()
    import seaborn as sns

    domain_names = sorted(domains.keys())
    if not domain_names:
        return
    domain_pipelines = {}
    for dt in domain_names:
        domain_pipelines[dt] = {p[0] for p in domains[dt].get("pipelines", [])}
    tools_sorted = sorted(tool_wfs.items(), key=lambda x: -len(x[1]))
    top_tools = tools_sorted[:25]
    tool_names = [t for t, _ in top_tools]
    n_tools = len(tool_names)
    n_domains = len(domain_names)
    import numpy as np

    raw_mat = np.zeros((n_domains, n_tools), dtype=int)
    for j, dt in enumerate(domain_names):
        for i, (_tool, pipelines) in enumerate(top_tools):
            raw_mat[j, i] = len(set(pipelines) & domain_pipelines[dt])
    fig, ax = plt.subplots(figsize=(14, 5))
    sns.heatmap(
        raw_mat,
        annot=True,
        fmt="d",
        xticklabels=tool_names,
        yticklabels=domain_names,
        cmap="YlOrRd",
        ax=ax,
        cbar_kws={"label": "Pipeline count"},
    )
    ax.set_xticklabels(tool_names, rotation=45, ha="right", fontsize=8)
    ax.set_title("Tool usage by domain (raw pipeline count)")
    plt.tight_layout()
    fig.savefig(os.path.join(plot_dir, "domain_tool_heatmap.png"), dpi=150)
    plt.close(fig)


def _plot_cooccurrence_heatmap(tool_wfs, cooccur, plot_dir):
    import os

    plt = _init_mpl()
    import seaborn as sns

    tools_in_10 = [t for t, ps in tool_wfs.items() if len(ps) >= 10]
    if len(tools_in_10) < 3:
        return
    n = len(tools_in_10)
    jmat = [[0.0] * n for _ in range(n)]
    idx = {t: i for i, t in enumerate(tools_in_10)}
    for _, jac, t1, t2, _, _ in cooccur:
        if t1 in idx and t2 in idx:
            i, j = idx[t1], idx[t2]
            jmat[i][j] = jac
            jmat[j][i] = jac
    fig, ax = plt.subplots(figsize=(12, 10))
    sns.heatmap(
        jmat,
        xticklabels=tools_in_10,
        yticklabels=tools_in_10,
        annot=False,
        cmap="YlOrRd",
        square=True,
        ax=ax,
        vmin=0,
        vmax=1,
    )
    ax.set_title("Tool co-occurrence (Jaccard index)")
    plt.setp(ax.get_xticklabels(), rotation=45, ha="right", fontsize=8)
    plt.setp(ax.get_yticklabels(), fontsize=8)
    plt.tight_layout()
    fig.savefig(os.path.join(plot_dir, "cooccurrence_heatmap.png"), dpi=150)
    plt.close(fig)


def _plot_failure_categories(graphs, plot_dir):
    import os
    from collections import defaultdict

    plt = _init_mpl()
    import seaborn as sns

    success_count = sum(1 for g in graphs if len(g["nodes"]) > 0)
    fail_counts = defaultdict(int)
    for g in graphs:
        fc = g["meta"].get("failure_classification", {})
        cat = fc.get("category", "")
        if cat:
            fail_counts[cat] += 1
    if not fail_counts:
        return
    cats = ["success"] + sorted(fail_counts.keys())
    vals = [success_count] + [fail_counts[c] for c in sorted(fail_counts.keys())]
    colors = ["mediumseagreen"] + [
        sns.color_palette("Set2")[i % len(sns.color_palette("Set2"))]
        for i in range(len(cats) - 1)
    ]
    fig, ax = plt.subplots(figsize=(10, 5))
    bars = ax.bar(cats, vals, color=colors)
    for bar, v in zip(bars, vals, strict=True):
        ax.text(
            bar.get_x() + bar.get_width() / 2,
            bar.get_height() + 0.5,
            str(v),
            ha="center",
            fontsize=10,
        )
    ax.set_ylabel("Pipelines")
    ax.set_title("Pipeline outcomes by category")
    plt.setp(ax.get_xticklabels(), rotation=30, ha="right")
    plt.tight_layout()
    fig.savefig(os.path.join(plot_dir, "failure_categories.png"), dpi=150)
    plt.close(fig)


def _plot_transition_network(transitions, plot_dir):
    import os

    plt = _init_mpl()
    if not transitions:
        return
    try:
        import networkx as nx
    except ImportError:
        return
    G = nx.DiGraph()
    top_trans = transitions[:20]
    max_count = top_trans[0][0] if top_trans else 1
    for cnt, src, dst, _ in top_trans:
        G.add_edge(src, dst, weight=cnt)
    components = list(nx.weakly_connected_components(G))
    pos = {}
    offset_x = 0
    for component in components:
        subgraph = G.subgraph(component)
        sub_pos = nx.spring_layout(subgraph, k=3.0, seed=42, center=(offset_x, 0))
        pos.update(sub_pos)
        offset_x += 4.0
    fig, ax = plt.subplots(figsize=(16, 12))
    weights = [G[u][v]["weight"] for u, v in G.edges()]
    nx.draw_networkx_nodes(
        G, pos, ax=ax, node_color="steelblue", node_size=800, alpha=0.9
    )
    nx.draw_networkx_labels(G, pos, ax=ax, font_size=9)
    nx.draw_networkx_edges(
        G,
        pos,
        ax=ax,
        width=[2 * w / max_count for w in weights],
        alpha=0.6,
        edge_color="gray",
        arrows=True,
        arrowsize=15,
        connectionstyle="arc3,rad=0.1",
    )
    ax.set_title("Transition network (top 20 edges)")
    ax.axis("off")
    plt.tight_layout()
    fig.savefig(os.path.join(plot_dir, "transition_network.png"), dpi=150)
    plt.close(fig)


def _plot_sankey(transitions, plot_dir):
    import os

    if not transitions:
        return
    try:
        import plotly.graph_objects as go
    except ImportError:
        print("  plotly not available, skipping sankey diagram", file=sys.stderr)
        return

    top = transitions[:30]
    sources = []
    targets = []
    values = []
    all_nodes = []
    node_set = set()
    for cnt, src, dst, _ in top:
        if src not in node_set:
            node_set.add(src)
            all_nodes.append(src)
        if dst not in node_set:
            node_set.add(dst)
            all_nodes.append(dst)
        sources.append(all_nodes.index(src))
        targets.append(all_nodes.index(dst))
        values.append(cnt)

    node_map = {n: i for i, n in enumerate(all_nodes)}
    fig = go.Figure(
        data=[
            go.Sankey(
                arrangement="perpendicular",
                node=dict(
                    pad=40,
                    thickness=20,
                    line=dict(color="black", width=0.5),
                    label=all_nodes,
                ),
                link=dict(
                    source=[node_map[t[1]] for t in top],
                    target=[node_map[t[2]] for t in top],
                    value=[t[0] for t in top],
                ),
            )
        ]
    )
    fig.update_layout(title_text="Transition Sankey diagram", font_size=10)
    try:
        fig.write_image(os.path.join(plot_dir, "sankey.png"), width=1200, height=800)
    except Exception as e:
        print(f"  sankey PNG export failed: {e}", file=sys.stderr)
    try:
        fig.write_html(os.path.join(plot_dir, "sankey.html"))
    except Exception:
        pass


def _plot_transitions_frequency(transitions, tool_wfs, plot_dir):
    import os

    plt = _init_mpl()
    import seaborn as sns

    if not transitions:
        return
    top20 = transitions[:20]
    labels = []
    counts = []
    for cnt, src, dst, wfs in top20:
        overlap = len(set(wfs))
        union = len(tool_wfs.get(src, set()) | tool_wfs.get(dst, set()))
        jac = overlap / union if union > 0 else 0
        labels.append(f"{src} \u2192 {dst}  J={jac:.2f}")
        counts.append(cnt)
    fig, ax = plt.subplots(figsize=(11, 7))
    colors = sns.color_palette("viridis", len(labels))
    bars = ax.barh(range(len(labels)), counts, color=colors)
    ax.set_yticks(range(len(labels)))
    ax.set_yticklabels(labels, fontsize=8)
    for bar, v in zip(bars, counts, strict=True):
        ax.text(
            bar.get_width() + 0.3,
            bar.get_y() + bar.get_height() / 2,
            str(v),
            va="center",
            fontsize=9,
        )
    ax.set_xlabel("Edge count")
    ax.set_title("Top 20 transitions with Jaccard similarity")
    ax.invert_yaxis()
    plt.tight_layout()
    fig.savefig(os.path.join(plot_dir, "transitions_frequency.png"), dpi=150)
    plt.close(fig)


def _plot_tool_chains(transitions, plot_dir):
    import os

    plt = _init_mpl()
    import seaborn as sns

    if not transitions:
        return
    chains = _build_chains(transitions)
    if not chains:
        return
    top_chains = chains[:15]
    labels = [f"{a} \u2192 {b} \u2192 {c}" for _, a, b, c, _ in top_chains]
    counts = [cnt for cnt, _, _, _, _ in top_chains]
    fig, ax = plt.subplots(figsize=(10, 7))
    colors = sns.color_palette("mako", len(labels))
    bars = ax.barh(range(len(labels)), counts, color=colors)
    ax.set_yticks(range(len(labels)))
    ax.set_yticklabels(labels)
    for bar, v in zip(bars, counts, strict=True):
        ax.text(
            bar.get_width() + 0.3,
            bar.get_y() + bar.get_height() / 2,
            str(v),
            va="center",
            fontsize=9,
        )
    ax.set_xlabel("Pipelines with chain")
    ax.set_title("Most common 2-step tool chains")
    ax.invert_yaxis()
    plt.tight_layout()
    fig.savefig(os.path.join(plot_dir, "tool_chains.png"), dpi=150)
    plt.close(fig)


def _plot_fan_pattern(patterns, title, xlabel, filename, plot_dir):
    """Horizontal bar chart for divergence or convergence patterns."""
    import os

    plt = _init_mpl()
    import seaborn as sns

    flat = []
    for tool, items in patterns.items():
        for cnt, nset, _ in items:
            flat.append((cnt, tool, nset))
    flat.sort(key=lambda x: -x[0])
    if not flat:
        return
    top = flat[:15]
    labels = [
        (
            f"{t} \u2192 {format_set(s)}"
            if "\u2192" not in title
            else f"{format_set(s)} \u2192 {t}"
        )
        for cnt, t, s in top
    ]
    # Actually determine whether this is divergence or convergence by title
    if "convergence" in title.lower():
        labels = [f"{format_set(s)} \u2192 {t}" for cnt, t, s in top]
    else:
        labels = [f"{t} \u2192 {format_set(s)}" for cnt, t, s in top]
    counts = [cnt for cnt, _, _ in top]
    fig, ax = plt.subplots(figsize=(10, 7))
    colors = sns.color_palette("mako", len(labels))
    bars = ax.barh(range(len(labels)), counts, color=colors)
    ax.set_yticks(range(len(labels)))
    ax.set_yticklabels(labels, fontsize=8)
    for bar, v in zip(bars, counts, strict=True):
        ax.text(
            bar.get_width() + 0.3,
            bar.get_y() + bar.get_height() / 2,
            str(v),
            va="center",
            fontsize=9,
        )
    ax.set_xlabel(xlabel)
    ax.set_title(title)
    ax.invert_yaxis()
    plt.tight_layout()
    fig.savefig(os.path.join(plot_dir, filename), dpi=150)
    plt.close(fig)


def format_set(s):
    """Format a frozenset as {a, b, c} for display."""
    if not s:
        return "{}"
    items = sorted(s)
    if len(items) == 1:
        return items[0]
    return "{" + ", ".join(items[:4]) + ("..." if len(items) > 4 else "") + "}"


def _plot_divergence_patterns(divergence, plot_dir):
    _plot_fan_pattern(
        divergence,
        "Most common divergence patterns (tool \u2192 {successors})",
        "Pipelines with pattern",
        "divergence_patterns.png",
        plot_dir,
    )


def _plot_convergence_patterns(convergence, plot_dir):
    _plot_fan_pattern(
        convergence,
        "Most common convergence patterns ({predecessors} \u2192 tool)",
        "Pipelines with pattern",
        "convergence_patterns.png",
        plot_dir,
    )


def _plot_top_connected_subgraphs(catalog, plot_dir):
    import os

    plt = _init_mpl()
    top15 = catalog[:15]
    labels = [_format_subgraph(e["labels"], e["edges"]) for e in top15]
    counts = [e["count"] for e in top15]
    colors = [plt.cm.Blues(0.3 + 0.7 * (1 - i / len(top15))) for i in range(len(top15))]
    fig, ax = plt.subplots(figsize=(10, 7))
    bars = ax.barh(range(len(labels)), counts, color=colors)
    ax.set_yticks(range(len(labels)))
    ax.set_yticklabels(labels, fontsize=7)
    for bar, v in zip(bars, counts, strict=True):
        ax.text(
            bar.get_width() + 0.2,
            bar.get_y() + bar.get_height() / 2,
            str(v),
            va="center",
            fontsize=8,
        )
    ax.set_xlabel("Pipelines sharing subgraph")
    ax.set_title("Most common connected subgraphs (all sizes)", fontsize=12)
    ax.invert_yaxis()
    plt.tight_layout()
    fig.savefig(
        os.path.join(plot_dir, "top_connected_subgraphs.png"),
        dpi=150,
        bbox_inches="tight",
    )
    plt.close(fig)


def _plot_top_size2_subgraphs(catalog, plot_dir):
    import os

    plt = _init_mpl()
    size2 = sorted(
        [e for e in catalog if e["size"] == 2],
        key=lambda x: -x["count"],
    )[:15]
    labels = [_format_subgraph(e["labels"], e["edges"]) for e in size2]
    counts = [e["count"] for e in size2]
    colors = [
        plt.cm.Greens(0.3 + 0.7 * (1 - i / len(size2))) for i in range(len(size2))
    ]
    fig, ax = plt.subplots(figsize=(10, 7))
    bars = ax.barh(range(len(labels)), counts, color=colors)
    ax.set_yticks(range(len(labels)))
    ax.set_yticklabels(labels, fontsize=8)
    for bar, v in zip(bars, counts, strict=True):
        ax.text(
            bar.get_width() + 0.2,
            bar.get_y() + bar.get_height() / 2,
            str(v),
            va="center",
            fontsize=8,
        )
    ax.set_xlabel("Pipelines sharing subgraph")
    ax.set_title("Most common size-2 subgraphs", fontsize=12)
    ax.invert_yaxis()
    plt.tight_layout()
    fig.savefig(
        os.path.join(plot_dir, "top_size2_subgraphs.png"), dpi=150, bbox_inches="tight"
    )
    plt.close(fig)


def _plot_top_pipeline_pairs(pairwise, plot_dir):
    import os

    plt = _init_mpl()
    top15 = pairwise[:15]
    labels = [f"{a.split('/')[-1]} \u2194 {b.split('/')[-1]}" for cnt, a, b, _ in top15]
    counts = [cnt for cnt, _, _, _ in top15]
    colors = [
        plt.cm.Oranges(0.3 + 0.7 * (1 - i / len(top15))) for i in range(len(top15))
    ]
    fig, ax = plt.subplots(figsize=(10, 7))
    bars = ax.barh(range(len(labels)), counts, color=colors)
    ax.set_yticks(range(len(labels)))
    ax.set_yticklabels(labels, fontsize=8)
    for bar, v in zip(bars, counts, strict=True):
        ax.text(
            bar.get_width() + 0.5,
            bar.get_y() + bar.get_height() / 2,
            str(v),
            va="center",
            fontsize=8,
        )
    ax.set_xlabel("Unique shared subgraphs")
    ax.set_title("Pipeline pairs with most shared subgraphs", fontsize=12)
    ax.invert_yaxis()
    plt.tight_layout()
    fig.savefig(
        os.path.join(plot_dir, "top_pipeline_pairs.png"), dpi=150, bbox_inches="tight"
    )
    plt.close(fig)


def _plot_subgraph_topology(catalog, plot_dir):
    import os

    plt = _init_mpl()
    top12 = catalog[:12]
    ncols = 4
    nrows = (len(top12) + ncols - 1) // ncols
    fig, axes = plt.subplots(nrows, ncols, figsize=(5 * ncols, 4 * nrows))
    axes = axes.flatten() if hasattr(axes, "flatten") else [axes]

    for i, entry in enumerate(top12):
        ax = axes[i]
        import networkx as nx

        G = nx.DiGraph()
        for src, dst in entry["edges"]:
            G.add_edge(src, dst)
        pos = nx.spring_layout(G, k=1.5, seed=42)
        nx.draw_networkx_nodes(G, pos, ax=ax, node_color="lightblue", node_size=500)
        nx.draw_networkx_labels(G, pos, ax=ax, font_size=7)
        nx.draw_networkx_edges(
            G,
            pos,
            ax=ax,
            edge_color="gray",
            arrows=True,
            arrowsize=12,
            arrowstyle="-|>",
            connectionstyle="arc3,rad=0.1",
        )
        ax.set_title(f"n={entry['count']}", fontsize=10)
        ax.axis("off")

    for j in range(len(top12), len(axes)):
        axes[j].axis("off")

    fig.suptitle("Topology of most common connected subgraphs", fontsize=14, y=1.02)
    plt.tight_layout()
    fig.savefig(
        os.path.join(plot_dir, "subgraph_topology.png"), dpi=150, bbox_inches="tight"
    )
    plt.close(fig)


def _plot_graph_quality(graph_quality, plot_dir):
    import os

    plt = _init_mpl()
    empty_by_category, empty_external, split_dags, isolated_dags, _status_br = (
        graph_quality
    )

    # Collect categories with counts
    cat_order = [
        "preview_failed",
        "timeout",
        "config_parsing",
        "permissions",
        "unknown_config",
        "unclassified",
    ]
    cat_labels = {
        "preview_failed": "Preview failed\n(no DAG produced)",
        "timeout": "Timeout\n(DAG too slow)",
        "config_parsing": "Config parsing\n(NF 26.x regression)",
        "permissions": "Permissions\n(work dir access)",
        "unknown_config": "Unknown config\n(attribute error)",
        "unclassified": "Unclassified\n(no match)",
    }
    cat_colors = {
        "preview_failed": "#e74c3c",
        "timeout": "#f39c12",
        "config_parsing": "#9b59b6",
        "permissions": "#e67e22",
        "unknown_config": "#95a5a6",
        "unclassified": "#7f8c8d",
    }

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 6))

    # Left panel: empty DAG failure categories (stacked horizontal)
    cats = []
    counts = []
    colors = []
    for cat in cat_order:
        items = empty_by_category.get(cat, [])
        if items:
            active = sum(1 for _, m in items if m.get("status") == "active")
            archived = sum(1 for _, m in items if m.get("status") == "archived")
            unreleased = sum(1 for _, m in items if m.get("status") == "unreleased")
            if active:
                cats.append(cat_labels.get(cat, cat))
                counts.append(active)
                colors.append(cat_colors.get(cat, "#3498db"))
            if archived:
                cats.append(cat_labels.get(cat, cat) + "\n(archived)")
                counts.append(archived)
                colors.append("#bdc3c7")
            if unreleased:
                cats.append(cat_labels.get(cat, cat) + "\n(unreleased)")
                counts.append(unreleased)
                colors.append("#d4a574")
    if empty_external:
        cats.append("External\n(structural only)")
        counts.append(len(empty_external))
        colors.append("#2ecc71")

    if counts:
        bars = ax1.barh(range(len(cats)), counts, color=colors)
        ax1.set_yticks(range(len(cats)))
        ax1.set_yticklabels(cats, fontsize=8)
        for bar, v in zip(bars, counts, strict=True):
            ax1.text(
                bar.get_width() + 0.2,
                bar.get_y() + bar.get_height() / 2,
                str(v),
                va="center",
                fontsize=9,
            )
        ax1.set_xlabel("Pipelines")
        ax1.set_title("Empty DAGs by failure category", fontsize=12)
        ax1.invert_yaxis()

    # Right panel: component count histogram for split DAGs
    if split_dags:
        comp_vals = [c for _, c, _, _ in split_dags]
        unique_comps = sorted(set(comp_vals))
        comp_hist = {c: comp_vals.count(c) for c in unique_comps}
        comp_cats = [f"{c} components" for c in unique_comps]
        comp_counts_list = [comp_hist[c] for c in unique_comps]
        colors2 = [
            plt.cm.Reds(0.3 + 0.7 * (1 - i / len(comp_cats)))
            for i in range(len(comp_cats))
        ]
        bars2 = ax2.barh(range(len(comp_cats)), comp_counts_list, color=colors2)
        ax2.set_yticks(range(len(comp_cats)))
        ax2.set_yticklabels(comp_cats, fontsize=9)
        for bar, v in zip(bars2, comp_counts_list, strict=True):
            ax2.text(
                bar.get_width() + 0.2,
                bar.get_y() + bar.get_height() / 2,
                str(v),
                va="center",
                fontsize=10,
            )
        ax2.set_xlabel("Pipelines")
        ax2.set_title("Split DAGs by component count", fontsize=12)
        ax2.invert_yaxis()
    else:
        ax2.text(
            0.5,
            0.5,
            "No split DAGs detected",
            ha="center",
            va="center",
            transform=ax2.transAxes,
            fontsize=12,
        )
        ax2.set_title("Split DAGs by component count", fontsize=12)

    plt.tight_layout()
    fig.savefig(
        os.path.join(plot_dir, "graph_quality.png"), dpi=150, bbox_inches="tight"
    )
    plt.close(fig)


def _plot_pipeline_status(status_breakdown, plot_dir):
    import os

    plt = _init_mpl()

    counts = status_breakdown["counts"]
    success = status_breakdown["success"]
    fail = status_breakdown["fail"]

    labels = []
    total_vals = []
    ok_vals = []
    fail_vals = []
    bar_colors = []
    for st in ["active", "archived", "unreleased"]:
        if counts.get(st, 0):
            labels.append(st.capitalize())
            total_vals.append(counts[st])
            ok_vals.append(success.get(st, 0))
            fail_vals.append(fail.get(st, 0))
            bar_colors.append(
                {"active": "#2ecc71", "archived": "#bdc3c7", "unreleased": "#d4a574"}[
                    st
                ]
            )

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(10, 4))

    # Left: total counts
    if total_vals:
        x = range(len(labels))
        ax1.barh(x, total_vals, color=bar_colors, edgecolor="white")
        ax1.set_yticks(list(x))
        ax1.set_yticklabels(labels, fontsize=10)
        for i, v in enumerate(total_vals):
            ax1.text(v + 0.3, i, str(v), va="center", fontsize=9)
        ax1.set_xlabel("Pipelines")
        ax1.set_title("Pipeline count by status", fontsize=11)
        ax1.invert_yaxis()
        ax1.margins(y=0.3)

    # Right: success vs failure grouped
    if ok_vals or fail_vals:
        x = range(len(labels))
        w = 0.35
        for i, (lb, ok, fl) in enumerate(zip(labels, ok_vals, fail_vals, strict=True)):
            ax2.bar(
                i - w / 2,
                ok,
                w,
                label="DAG success" if i == 0 else "",
                color="#2ecc71",
                edgecolor="white",
            )
            ax2.bar(
                i + w / 2,
                fl,
                w,
                label="Empty DAG" if i == 0 else "",
                color="#e74c3c",
                edgecolor="white",
            )
            ax2.text(i - w / 2, ok + 0.3, str(ok), ha="center", va="bottom", fontsize=8)
            if fl:
                ax2.text(
                    i + w / 2, fl + 0.3, str(fl), ha="center", va="bottom", fontsize=8
                )
        ax2.set_xticks(list(x))
        ax2.set_xticklabels(labels, fontsize=10)
        ax2.set_ylabel("Pipelines")
        ax2.set_title("DAG success vs failure by status", fontsize=11)
        ax2.legend(fontsize=8)
        ax2.margins(y=0.2)

    plt.tight_layout()
    fig.savefig(
        os.path.join(plot_dir, "pipeline_status.png"), dpi=150, bbox_inches="tight"
    )
    plt.close(fig)


def _plot_singleton_scatter(tool_wfs, topo, domains, plot_dir):
    import os
    from collections import defaultdict

    plt = _init_mpl()
    import seaborn as sns

    singleton_per_pipeline = defaultdict(int)
    for _tool, pipelines in tool_wfs.items():
        if len(pipelines) == 1:
            singleton_per_pipeline[next(iter(pipelines))] += 1
    pipeline_domain_map = {}
    for domain, data in domains.items():
        for pname, _, _, _ in data["pipelines"]:
            pipeline_domain_map.setdefault(pname, domain)
    scatter_data = []
    for pname, _, _, _, tools in topo:
        n_unique_tools = len(tools)
        scount = singleton_per_pipeline.get(pname, 0)
        pdomain = pipeline_domain_map.get(pname, "unknown")
        scatter_data.append((pname, n_unique_tools, scount, pdomain))
    if not scatter_data:
        return
    fig, ax = plt.subplots(figsize=(10, 7))
    dset = sorted(set(d for _, _, _, d in scatter_data))
    cmap = dict(zip(dset, sns.color_palette("husl", len(dset)), strict=True))
    for _pname, n_tools, scount, pdomain in scatter_data:
        ax.scatter(
            n_tools,
            scount,
            color=cmap[pdomain],
            s=80,
            alpha=0.7,
            edgecolors="black",
            linewidth=0.5,
            label=pdomain,
        )
    ax.set_xlabel("Unique tools in pipeline")
    ax.set_ylabel("Singleton tools (unique to this pipeline)")
    ax.set_title("Unique tools vs singleton count")
    handles = [
        plt.Line2D(
            [0], [0], marker="o", color="w", markerfacecolor=cmap[d], markersize=8
        )
        for d in dset
    ]
    ax.legend(handles, dset, title="Domain", loc="upper right")
    plt.tight_layout()
    fig.savefig(os.path.join(plot_dir, "singleton_scatter.png"), dpi=150)
    plt.close(fig)


def _plot_module_origin(graphs, plot_dir):
    import os

    plt = _init_mpl()
    import numpy as np

    _, mo_totals, pipeline_origins = module_origin_summary(graphs)
    if not pipeline_origins:
        return

    pipelines = sorted(pipeline_origins.keys())
    names = [p.split("/")[-1] for p in pipelines]
    origins = ["nf-core", "local", "heuristic", "unknown"]
    colors = {
        "nf-core": "#2ecc71",
        "local": "#3498db",
        "heuristic": "#e67e22",
        "unknown": "#95a5a6",
    }
    bottom = np.zeros(len(pipelines))
    fig, ax = plt.subplots(figsize=(max(12, len(pipelines) * 0.2), 7))
    for origin in origins:
        vals = np.array([pipeline_origins[p].get(origin, 0) for p in pipelines])
        if vals.sum() > 0:
            ax.bar(
                range(len(pipelines)),
                vals,
                bottom=bottom,
                color=colors[origin],
                label=origin,
                edgecolor="white",
                linewidth=0.3,
            )
            bottom += vals
    ax.set_xticks(range(len(pipelines)))
    ax.set_xticklabels(names, rotation=90, fontsize=6)
    ax.set_ylabel("Unique tools")
    ax.set_title("Module origin per pipeline")
    ax.legend(title="Origin", loc="upper right")
    total = sum(mo_totals.values())
    summary = "  ".join(
        f"{k}={v} ({100 * v // total}%)" for k, v in sorted(mo_totals.items())
    )
    ax.text(
        0.02,
        0.98,
        summary,
        transform=ax.transAxes,
        ha="left",
        va="top",
        fontsize=8,
        bbox=dict(boxstyle="round", facecolor="white", alpha=0.7),
    )
    plt.tight_layout()
    fig.savefig(os.path.join(plot_dir, "module_origin.png"), dpi=150)
    plt.close(fig)


def _plot_module_origin_norm(graphs, plot_dir):
    import os

    plt = _init_mpl()
    import numpy as np

    _, _, pipeline_origins = module_origin_summary(graphs)
    if not pipeline_origins:
        return

    pipelines = sorted(pipeline_origins.keys())
    names = [p.split("/")[-1] for p in pipelines]
    origins = ["nf-core", "local", "heuristic", "unknown"]
    colors = {
        "nf-core": "#2ecc71",
        "local": "#3498db",
        "heuristic": "#e67e22",
        "unknown": "#95a5a6",
    }
    bottom = np.zeros(len(pipelines))
    fig, ax = plt.subplots(figsize=(max(12, len(pipelines) * 0.2), 7))
    for origin in origins:
        vals = np.array([pipeline_origins[p].get(origin, 0) for p in pipelines])
        totals = np.array([sum(pipeline_origins[p].values()) for p in pipelines])
        pcts = np.where(totals > 0, vals / totals * 100, 0)
        if pcts.sum() > 0:
            ax.bar(
                range(len(pipelines)),
                pcts,
                bottom=bottom,
                color=colors[origin],
                label=origin,
                edgecolor="white",
                linewidth=0.3,
            )
            bottom += pcts
    ax.set_xticks(range(len(pipelines)))
    ax.set_xticklabels(names, rotation=90, fontsize=6)
    ax.set_ylabel("% of pipeline tools")
    ax.set_title("Module origin per pipeline (normalized)")
    ax.legend(title="Origin", loc="upper right")
    ax.set_ylim(0, 100)
    plt.tight_layout()
    fig.savefig(os.path.join(plot_dir, "module_origin_norm.png"), dpi=150)
    plt.close(fig)


def _plot_module_origin_aggregate(graphs, plot_dir):
    import os

    plt = _init_mpl()
    import numpy as np

    _, mo_totals, pipeline_origins = module_origin_summary(graphs)
    if not pipeline_origins:
        return

    origins = ["nf-core", "local", "heuristic", "unknown"]
    colors = {
        "nf-core": "#2ecc71",
        "local": "#3498db",
        "heuristic": "#e67e22",
        "unknown": "#95a5a6",
    }

    # Aggregate absolute counts across all pipelines
    abs_vals = np.array([mo_totals.get(o, 0) for o in origins])
    pct_vals = abs_vals / abs_vals.sum() * 100 if abs_vals.sum() > 0 else abs_vals

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(10, 5))

    # Left: absolute stacked bar
    bottom_abs = 0
    for i, origin in enumerate(origins):
        v = abs_vals[i]
        if v > 0:
            ax1.bar(
                0,
                v,
                bottom=bottom_abs,
                color=colors[origin],
                label=origin,
                edgecolor="white",
                linewidth=0.5,
            )
            ax1.text(
                0,
                bottom_abs + v / 2,
                str(int(v)),
                ha="center",
                va="center",
                fontsize=10,
                fontweight="bold",
            )
            bottom_abs += v
    ax1.set_xticks([])
    ax1.set_ylabel("Unique tools")
    ax1.set_title("Aggregate (absolute)")
    ax1.legend(title="Origin", loc="upper right")

    # Right: normalized stacked bar
    bottom_pct = 0
    for i, origin in enumerate(origins):
        v = pct_vals[i]
        if v > 0:
            ax2.bar(
                0,
                v,
                bottom=bottom_pct,
                color=colors[origin],
                label=origin,
                edgecolor="white",
                linewidth=0.5,
            )
            ax2.text(
                0,
                bottom_pct + v / 2,
                f"{v:.0f}%",
                ha="center",
                va="center",
                fontsize=10,
                fontweight="bold",
            )
            bottom_pct += v
    ax2.set_xticks([])
    ax2.set_ylabel("% of tools")
    ax2.set_title("Aggregate (normalized)")
    ax2.set_ylim(0, 100)

    plt.tight_layout()
    fig.savefig(os.path.join(plot_dir, "module_origin_aggregate.png"), dpi=150)
    plt.close(fig)


def _write_transition_trace(transitions, tool_wfs, plot_dir):
    import json
    import os

    if not transitions:
        return
    trans_data = []
    for cnt, src, dst, wfs in transitions:
        trans_data.append(
            {
                "source": src,
                "target": dst,
                "count": cnt,
                "pipelines": sorted(wfs),
            }
        )
    chains = _build_chains(transitions)
    chains_dicts = [
        {"a": a, "b": b, "c": c, "count": cnt, "pipelines": pl}
        for cnt, a, b, c, pl in chains
    ]
    trace = {
        "transitions": trans_data,
        "chains": chains_dicts,
    }
    path = os.path.join(plot_dir, "transition_trace.json")
    with open(path, "w") as f:
        json.dump(trace, f, indent=2)
    print(f"  Wrote {path}", file=sys.stderr)


def _write_analysis_report_md(
    graphs,
    tool_wfs,
    transitions,
    divergence,
    convergence,
    domains,
    pipeline_detail,
    topo,
    plot_dir,
):
    """Write analysis_report.md with dynamic data from the current run."""
    import os

    n_total = len(graphs)
    n_success = sum(1 for g in graphs if len(g["nodes"]) > 0)
    n_empty = n_total - n_success
    tools_sorted = sorted(tool_wfs.items(), key=lambda x: -len(x[1]))
    total_unique_tools = len(tool_wfs)
    singletons = [(t, list(ps)[0]) for t, ps in tool_wfs.items() if len(ps) == 1]
    chains = _build_chains(transitions)
    self_loops = _find_self_loops(transitions)

    lines = []
    _w = lines.append
    _w("# nf-core Pipeline Pattern Analysis Report\n")
    _w(
        f"**Dataset**: {n_total} nf-core pipelines ({n_success} with DAG, {n_empty} empty)\n"
    )
    _w(
        f"**Unique tools**: {total_unique_tools} ({len(singletons)} singletons = {100 * len(singletons) // total_unique_tools}%)\n"
    )
    _w("")

    _w("## Universal Plumbing Core\n")
    _w("Tools appearing in ≥20% of pipelines:\n")
    _w("")
    _w("| Tool | Pipelines | % |")
    _w("|------|-----------|---|")
    for t, ps in tools_sorted:
        if len(ps) < n_total * 0.2:
            break
        _w(f"| {t} | {len(ps)} | {100 * len(ps) // n_total}% |")
    _w("")

    _w("## Top Transitions\n")
    _w("```")
    for cnt, src, dst, _ in transitions[:15]:
        _w(f"{src:20s} -> {dst:20s} ({cnt:3d} edges)")
    _w("```\n")

    if chains:
        _w("## 2-Step Tool Chains\n")
        _w("```")
        for cnt, a, b, c, _ in chains[:15]:
            _w(f"{a:20s} -> {b:20s} -> {c:20s} ({cnt:3d} pipelines)")
        _w("```\n")

    if divergence:
        _w("## Divergence Patterns (Fan-Out)\n")
        _w("A tool with multiple successors in the **same** pipeline:\n")
        _w("")
        _w("| Tool | Successors | Pipelines |")
        _w("|------|------------|-----------|")
        flat = sorted(
            [
                (cnt, tool, nset)
                for tool, items in divergence.items()
                for cnt, nset, _ in items
            ],
            key=lambda x: -x[0],
        )
        for cnt, tool, nset in flat[:10]:
            s = ", ".join(sorted(nset))
            _w(f"| {tool} | {{{s}}} | {cnt} |")
        _w("")

    if convergence:
        _w("## Convergence Patterns (Fan-In)\n")
        _w("A tool with multiple predecessors in the **same** pipeline:\n")
        _w("")
        _w("| Predecessors | Tool | Pipelines |")
        _w("|-------------|------|-----------|")
        flat = sorted(
            [
                (cnt, tool, nset)
                for tool, items in convergence.items()
                for cnt, nset, _ in items
            ],
            key=lambda x: -x[0],
        )
        for cnt, tool, nset in flat[:10]:
            s = ", ".join(sorted(nset))
            _w(f"| {{{s}}} | {tool} | {cnt} |")
        _w("")

    _w("## Consistency Note\n")
    _w(
        "The three views (chains, divergence, convergence) capture different structural facts:\n"
    )
    _w("")
    _w("| View | What it captures |")
    _w("|------|-----------------|")
    _w("| **Chain** | One path of length 2 exists |")
    _w("| **Divergence** | All successors appear **together** in the same pipeline |")
    _w(
        "| **Convergence** | All predecessors appear **together** in the same pipeline |"
    )
    _w("")
    _w(
        "Divergence and convergence counts are naturally lower because they require full neighbor sets to co-occur.\n"
    )

    if self_loops:
        _w("## Self-Loops (Potential Toolkits)\n")
        _w("Tools with self-loop edges suggesting collapsed subprocesses:\n")
        _w("")
        _w("| Tool | Self-loops |")
        _w("|------|-----------|")
        for cnt, tool in self_loops[:15]:
            _w(f"| {tool} | {cnt} |")
        _w("")

    _w("## Topology Extremes\n")
    _w("")
    _w("| Pipeline | Nodes | Edges | Ratio |")
    _w("|----------|-------|-------|-------|")
    topo_sorted = sorted(topo, key=lambda x: -x[1])
    for p, nn, ne, r, _ in topo_sorted[:3]:
        _w(f"| **Largest**: {p} | {nn} | {ne} | {r:.2f} |")
    nonempty = [x for x in topo if x[1] > 0]
    if nonempty:
        nonempty.sort(key=lambda x: -x[3])
        for p, nn, ne, r, _ in nonempty[:1]:
            _w(f"| **Highest ratio**: {p} | {nn} | {ne} | {r:.2f} |")
    _w("")

    _w("## Domain Clusters\n")
    _w("")
    _w("| Domain | Pipelines |")
    _w("|--------|-----------|")
    dt_sorted = sorted(domains.items(), key=lambda x: -len(x[1]["pipelines"]))
    for dt, data in dt_sorted:
        _w(f"| {dt} | {len(data['pipelines'])} |")
    _w("")

    path = os.path.join(plot_dir, "analysis_report.md")
    with open(path, "w") as f:
        f.write("\n".join(lines))
    print(f"  Wrote {path}", file=sys.stderr)


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
    cores=1,
):
    import os
    import time

    os.makedirs(plot_dir, exist_ok=True)
    os.makedirs(os.path.join(plot_dir, "transitions"), exist_ok=True)
    os.makedirs(os.path.join(plot_dir, "domains"), exist_ok=True)
    os.makedirs(os.path.join(plot_dir, "subgraphs"), exist_ok=True)

    # Suppress InheritableWarning spam from multiprocessing
    import warnings

    warnings.filterwarnings("ignore", category=UserWarning, module="multiprocessing")

    import os.path as _osp

    dom_dir = _osp.join(plot_dir, "domains")
    tra_dir = _osp.join(plot_dir, "transitions")
    sub_dir = _osp.join(plot_dir, "subgraphs")

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
            "module_origin.png",
            _plot_module_origin,
            (graphs, plot_dir),
        ),
        (
            "module_origin_norm.png",
            _plot_module_origin_norm,
            (graphs, plot_dir),
        ),
        (
            "module_origin_aggregate.png",
            _plot_module_origin_aggregate,
            (graphs, plot_dir),
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
                (catalog, sub_dir),
            ),
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
        )
        sys.stdout = orig
    print(f"Wrote {summary_path}", file=sys.stderr)

    # Write full report alongside summary
    summary_dir = os.path.dirname(summary_path) or "."
    full_path = os.path.join(summary_dir, "analysis_report_full.txt")
    with open(full_path, "w") as f:
        orig = sys.stdout
        sys.stdout = f
        _print_full_report(
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
        )
        sys.stdout = orig
    print(f"Wrote {full_path}", file=sys.stderr)

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
            cores=args.cores,
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


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Analyze cross-pipeline patterns")
    parser.add_argument(
        "--input-dir", required=True, help="Directory with graph.json files"
    )
    parser.add_argument(
        "--patterns-dag",
        required=True,
        help="patterns_dag.json from pattern_aggregator",
    )
    parser.add_argument(
        "--output",
        default=None,
        help="Write summary report to file (default: analysis_report_summary.txt)",
    )
    parser.add_argument(
        "--plot-dir",
        default=None,
        help="Generate plots in this directory (requires matplotlib + seaborn)",
    )
    parser.add_argument(
        "--cores",
        type=int,
        default=1,
        help="Number of parallel worker processes for plot generation (default: 1)",
    )
    main(parser.parse_args())
