"""Analyze patterns across nf-core pipelines from DAG and API data."""

import argparse
import json
import os
import sys
from collections import Counter, defaultdict


def format_set(s):
    """Format a frozenset as {a, b, c} for display."""
    if not s:
        return "{}"
    items = sorted(s)
    if len(items) == 1:
        return items[0]
    return "{" + ", ".join(items[:4]) + ("..." if len(items) > 4 else "") + "}"


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
    all_trans.sort(key=lambda x: (-x[0], x[1], x[2]))
    return all_trans


def domain_clusters(tool_wfs, graphs):
    domain_data = defaultdict(lambda: {"pipelines": [], "tools": defaultdict(list)})
    pipeline_detail = {}
    for g in graphs:
        pipeline_tools = {n.get("app", "") for n in g["nodes"] if n.get("app")}
        pipeline_domains = defaultdict(list)
        for tool in sorted(pipeline_tools):
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
        for domain in sorted(pipeline_domains):
            tools = pipeline_domains[domain]
            for t in sorted(tools):
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
    for tool in sorted(div_agg):
        patterns = div_agg[tool]
        items = [(len(ps), key, sorted(ps)) for key, ps in patterns.items()]
        items.sort(key=lambda x: (-x[0], sorted(x[1])))
        divergence[tool] = items

    convergence = {}
    for tool in sorted(conv_agg):
        patterns = conv_agg[tool]
        items = [(len(ps), key, sorted(ps)) for key, ps in patterns.items()]
        items.sort(key=lambda x: (-x[0], sorted(x[1])))
        convergence[tool] = items

    return divergence, convergence


def _template_key(entry):
    """Group key: frozenset of sorted node labels (ignores edge structure)."""
    return frozenset(sorted(entry["labels"]))


def _is_samtools_only(labels):
    """True if every label is a samtools subcommand."""
    return all(l.startswith("samtools.") or l == "samtools" for l in labels)


def summarize_templates(catalog):
    """Group catalog entries by node-label set (template).

    Each template groups all edge variants of the same tool set.
    Returns (templates, non_samtools_catalog).

    templates: list of dicts sorted by (size desc, total_pipelines desc)
        node_set, size, n_variants, total_pipelines, max_count,
        all_samtools, non_samtools_tools, representative
    non_samtools_catalog: filtered entries with at least one non-samtools tool
    """
    from collections import defaultdict

    groups = defaultdict(list)
    for entry in catalog:
        groups[_template_key(entry)].append(entry)

    templates = []
    for key, entries in groups.items():
        pipelines_union = set()
        for e in entries:
            pipelines_union.update(e["pipelines"])
        rep = max(entries, key=lambda e: (e["count"], len(e["edges"])))
        non_samtools = {
            l for l in key if not (l.startswith("samtools.") or l == "samtools")
        }
        templates.append(
            {
                "node_set": sorted(key),
                "size": len(key),
                "n_variants": len(entries),
                "total_pipelines": len(pipelines_union),
                "max_count": rep["count"],
                "all_samtools": len(non_samtools) == 0,
                "non_samtools_tools": sorted(non_samtools),
                "representative": rep,
            }
        )

    templates.sort(key=lambda t: (-t["size"], -t["total_pipelines"], -t["n_variants"]))

    non_samtools_catalog = [e for e in catalog if not _is_samtools_only(e["labels"])]

    return templates, non_samtools_catalog


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
    for key in sorted(subgraph_pipelines):
        pipelines = subgraph_pipelines[key]
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
    catalog.sort(
        key=lambda x: (-x["size"], -x["count"], sorted(x["labels"]), sorted(x["edges"]))
    )

    # Build per-pipeline index
    pipeline_sgs = defaultdict(set)
    for key in sorted(subgraph_pipelines):
        pipelines = subgraph_pipelines[key]
        for p in pipelines:
            pipeline_sgs[p].add(key)

    # Build pairwise shared
    pair_agg = defaultdict(set)
    for key in sorted(subgraph_pairs):
        pairs = subgraph_pairs[key]
        for pair in pairs:
            a, b = sorted(pair)
            pair_agg[(a, b)].add(key)

    pairwise = [
        (len(keys), a, b, sorted(str(k) for k in keys))
        for (a, b), keys in sorted(pair_agg.items())
    ]
    pairwise.sort(key=lambda x: (-x[0], x[1], x[2]))

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


def catalog_pipeline_distribution(catalog):
    """Return Counter: how many catalog entries are shared by N pipelines each.

    Example: {2: 37288, 3: 3148, 4: 856, ...}
    means 37288 entries shared by exactly 2 pipelines, 3148 by 3, etc.
    """
    return Counter(len(e["pipelines"]) for e in catalog)


def pair_dominance(pairwise):
    """Analyze which pipeline pairs contribute the most shared entries.

    Returns list of dicts sorted by count desc, with cumulative percentage:
        [{"count": 17521, "a": "atacseq", "b": "chipseq", "cum_pct": 25.4}, ...]
    """
    total = sum(cnt for cnt, a, b, _ in pairwise if cnt > 0)
    result = []
    cumul = 0
    for cnt, a, b, _ in sorted(pairwise, key=lambda x: -x[0]):
        if cnt == 0:
            continue
        cumul += cnt
        result.append(
            {
                "count": cnt,
                "a": a,
                "b": b,
                "cum_pct": 100.0 * cumul / total,
                "pct": 100.0 * cnt / total,
            }
        )
    return result


def cross_pair_convergence(catalog, templates):
    """For each template, compute how many unique pipeline pairs its entries span.

    A template whose entries span >1 pipeline pair represents cross-pair
    convergence: the same tool set appears in multiple independent comparisons.

    Returns list of dicts:
        {"node_set": [...], "size": N, "n_variants": N, "n_pairs": N,
         "total_pipelines": N, "is_cross_pair": bool, "multi_variant": bool}
    """
    from collections import defaultdict

    # Build label_set -> entries index
    label_entries = defaultdict(list)
    for e in catalog:
        label_entries[frozenset(e["labels"])].append(e)

    results = []
    for t in templates:
        key = frozenset(t["node_set"])
        entries = label_entries.get(key, [])
        all_pairs = set()
        for e in entries:
            pl = sorted(e["pipelines"])
            for i in range(len(pl)):
                for j in range(i + 1, len(pl)):
                    all_pairs.add((pl[i], pl[j]))
        results.append(
            {
                "node_set": t["node_set"],
                "size": t["size"],
                "n_variants": t["n_variants"],
                "n_pairs": len(all_pairs),
                "total_pipelines": t["total_pipelines"],
                "is_cross_pair": len(all_pairs) > 1,
                "multi_variant": t["n_variants"] > 1,
            }
        )
    results.sort(key=lambda x: (-x["size"], -x["n_pairs"], -x["n_variants"]))
    return results


def template_full_summary(catalog, templates, pairwise):
    """Return a dict with all key template/catalog/pair statistics.

    Keys:
        n_catalog, n_templates, collapse_pct, collapse_count
        n_all_samtools, n_multi_variant, n_cross_pair
        n_single_variant, n_single_pair
        n_pairs_with_shared, total_pair_entries
        top_pair_name, top_pair_pct
        n_triple_convergence (>=3 variants AND >=3 pairs)
        multi_variant_all_cross_pair (bool)
    """
    n_catalog = len(catalog)
    n_templates = len(templates)
    collapse_count = n_catalog - n_templates
    collapse_pct = 100.0 * collapse_count / n_catalog if n_catalog else 0
    n_all_samtools = sum(1 for t in templates if t["all_samtools"])
    n_multi_variant = sum(1 for t in templates if t["n_variants"] > 1)
    n_single_variant = n_templates - n_multi_variant

    cross = cross_pair_convergence(catalog, templates)
    n_cross_pair = sum(1 for r in cross if r["is_cross_pair"])
    n_single_pair = n_templates - n_cross_pair
    n_triple = sum(1 for r in cross if r["n_variants"] >= 3 and r["n_pairs"] >= 3)

    multi_variant_cross = sum(
        1 for r in cross if r["multi_variant"] and r["is_cross_pair"]
    )
    multi_variant_single = sum(
        1 for r in cross if r["multi_variant"] and not r["is_cross_pair"]
    )

    dom = pair_dominance(pairwise)
    total_pair = sum(d["count"] for d in dom)
    n_pairs = len(dom)
    top = dom[0] if dom else None

    return {
        "n_catalog": n_catalog,
        "n_templates": n_templates,
        "collapse_count": collapse_count,
        "collapse_pct": collapse_pct,
        "n_all_samtools": n_all_samtools,
        "n_multi_variant": n_multi_variant,
        "n_single_variant": n_single_variant,
        "n_cross_pair": n_cross_pair,
        "n_single_pair": n_single_pair,
        "n_triple_convergence": n_triple,
        "multi_variant_all_cross_pair": (multi_variant_single == 0),
        "multi_variant_cross_pair": multi_variant_cross,
        "multi_variant_single_pair": multi_variant_single,
        "n_pairs_with_shared": n_pairs,
        "total_pair_entries": total_pair,
        "top_pair_name": f"{top['a']} ↔ {top['b']}" if top else None,
        "top_pair_pct": top["pct"] if top else 0,
        "top_15_cumul_pct": (
            dom[14]["cum_pct"] if len(dom) > 14 else (dom[-1]["cum_pct"] if dom else 0)
        ),
    }


def tool_origin_mixed(graphs):
    """Identify tools appearing in multiple origin categories across pipelines.

    Builds {app: {origin: [pipeline_names]}} and filters to tools with >=2 origins.
    Returns {
        "tools": {app: {origin: [pipeline_names]}, ...},
        "summary": {"total_tools": N, "mixed_tools": M, "pure_tools": P, "pct_mixed": X.X},
        "by_origin_pair": {"nf-core+local": N, ...}
    }
    """
    from collections import Counter, defaultdict
    from itertools import combinations

    app_origins = defaultdict(lambda: defaultdict(set))
    all_apps = set()
    for g in graphs:
        pipeline = g.get("name", "?")
        for n in g.get("nodes", []):
            meta = n.get("language_metadata", {}) or {}
            origin = meta.get("module_origin", "unknown")
            app = n.get("app", "")
            if app:
                all_apps.add(app)
                app_origins[app][origin].add(pipeline)

    mixed = {}
    by_origin_pair = Counter()
    origin_sets = Counter()
    for app, origins in app_origins.items():
        origin_set_key = "+".join(sorted(origins.keys()))
        origin_sets[origin_set_key] += 1
        if len(origins) >= 2:
            mixed[app] = {o: sorted(ps) for o, ps in origins.items()}
            origin_list = sorted(origins.keys())
            for i in range(len(origin_list)):
                for j in range(i + 1, len(origin_list)):
                    by_origin_pair[f"{origin_list[i]}+{origin_list[j]}"] += 1

    # Build all possible origin subsets for complete reporting
    all_origins = ["nf-core", "local", "heuristic", "unknown"]
    all_subsets = []
    for r in range(1, len(all_origins) + 1):
        for combo in combinations(sorted(all_origins), r):
            key = "+".join(combo)
            all_subsets.append((key, origin_sets.get(key, 0)))
    all_subsets.sort(key=lambda x: (-len(x[0].split("+")), -x[1], x[0]))

    n_total = len(all_apps)
    n_mixed = len(mixed)
    n_pure = n_total - n_mixed
    pct_mixed = 100.0 * n_mixed / n_total if n_total else 0

    return {
        "tools": dict(mixed),
        "summary": {
            "total_tools": n_total,
            "mixed_tools": n_mixed,
            "pure_tools": n_pure,
            "pct_mixed": pct_mixed,
        },
        "by_origin_pair": dict(by_origin_pair),
        "origin_sets": dict(origin_sets),
        "all_subsets": all_subsets,
    }


def self_loop_origin_analysis(transitions, graphs):
    """Cross-reference self-loop tools with module origin.

    For each self-loop detected in transitions, looks up the tool's module_origin
    across all graph nodes. The known_subtool flag is retired — module path is
    the authoritative source for subtool resolution.

    Returns list of dicts sorted by self-loop count descending:
      {"tool": str, "self_loop_count": int, "known_subtool": bool,
       "origins": {origin: [pipeline_names]}, "origin_mixed": bool,
       "pipeline_count": int}
    """
    from collections import defaultdict

    self_loops = _find_self_loops(transitions)
    if not self_loops:
        return []

    self_loop_tools = {tool for _, tool in self_loops}
    loop_counts = {tool: cnt for cnt, tool in self_loops}

    tool_origins = defaultdict(lambda: defaultdict(set))
    for g in graphs:
        pipeline = g.get("name", "?")
        for n in g.get("nodes", []):
            app = n.get("app", "")
            if app in self_loop_tools:
                meta = n.get("language_metadata", {}) or {}
                origin = meta.get("module_origin", "unknown")
                tool_origins[app][origin].add(pipeline)

    results = []
    for tool in sorted(self_loop_tools, key=lambda t: -loop_counts.get(t, 0)):
        origins = tool_origins.get(tool, {})
        origin_dict = {o: sorted(ps) for o, ps in origins.items()}
        all_pipelines = set()
        for ps in origins.values():
            all_pipelines.update(ps)
        results.append(
            {
                "tool": tool,
                "self_loop_count": loop_counts.get(tool, 0),
                "known_subtool": False,
                "origins": origin_dict,
                "origin_mixed": len(origins) >= 2,
                "pipeline_count": len(all_pipelines),
            }
        )

    return results


def exact_subgraph_convergence(catalog, min_pipelines=3):
    """Filter catalog entries shared by >= min_pipelines pipelines.

    These are exact (label_set, edge_set) matches that appear identically
    across multiple pipeline comparisons — the strongest evidence of
    convergent subgraph evolution.

    Returns list of entries (original dicts) sorted by (count desc, size desc),
    with an added "n_pairs" key (number of unique pipeline pairs).
    """
    filtered = [e for e in catalog if len(e["pipelines"]) >= min_pipelines]
    filtered.sort(key=lambda e: (-len(e["pipelines"]), -e["size"]))
    for e in filtered:
        pl = e["pipelines"]
        e["n_pairs"] = len(pl) * (len(pl) - 1) // 2
    return filtered
