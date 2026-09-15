import sys
from collections import defaultdict

from .core import (
    _build_chains,
    _find_self_loops,
    _format_subgraph,
    _is_samtools_only,
    catalog_pipeline_distribution,
    cross_pair_convergence,
    exact_subgraph_convergence,
    format_set,
    module_origin_summary,
    pair_dominance,
    self_loop_origin_analysis,
    template_full_summary,
    tool_origin_mixed,
)


def _make_toc(*titles):
    """Return (lines, title_to_id) with auto-assigned [S01]..[SXX] IDs."""
    ids = {}
    lines = ["[Contents]"]
    for i, title in enumerate(titles, 1):
        sid = f"S{i:02d}"
        ids[title] = sid
        lines.append(f"  {i}. [{sid}] {title}")
    lines.append("---")
    lines.append("")
    return lines, ids


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
    templates=None,
    non_samtools_catalog=None,
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

    print("  (see analysis_report_full/10_origins.txt for module origin analysis)")
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
    print("  (see analysis_report_full/01_meta.txt)")
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
    print("  (see analysis_report_full/01_meta.txt)")
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
    print("  (see analysis_report_full/02_tools.txt)")
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
    print("  (see analysis_report_full/03_cooccurrence.txt)")
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

    slo = self_loop_origin_analysis(transitions, graphs)
    if slo:
        print("=== Potential toolkits (self-loops — collapsed subtools) ===")
        print(
            "  Self-loops suggest a tool with multiple subprocesses collapsing to the same name."
        )
        print()
        print(f"  {'Tool':20s} {'Edges':>6s} {'Origin(s)':20s} {'Status':20s}")
        print(f"  {'-' * 20} {'-' * 6} {'-' * 20} {'-' * 20}")
        for e in slo:
            origin_str = "+".join(sorted(e["origins"].keys()))
            tag = "KNOWN_SUBTOOLS" if e["known_subtool"] else "candidate"
            print(
                f"  {e['tool']:20s} {e['self_loop_count']:6d} {origin_str:20s} {tag:20s}"
            )
        print()
    print("  (see analysis_report_full/04_transitions.txt)")
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
    print("  (see analysis_report_full/05_topology.txt)")
    print()

    if catalog:
        print(f"=== Catalog subgraphs (top 15, {len(catalog)} total entries) ===")
        print(
            "  Each entry is a distinct (node_set, edge_set) combination. All counts are unique —"
        )
        print("  no duplicate subgraph is counted twice for the same pipeline.")
        print()
        for entry in catalog[:15]:
            text = _format_subgraph(entry["labels"], entry["edges"])
            print(f"  size={entry['size']}  {text}  ({entry['count']:3d} pipelines)")
        print()

    if non_samtools_catalog:
        print("=== Non-only-samtools subgraph highlights ===")
        print("  Subgraphs that include at least one tool outside the samtools family:")
        for entry in non_samtools_catalog[:10]:
            text = _format_subgraph(entry["labels"], entry["edges"])
            non_st = [
                l
                for l in entry["labels"]
                if not (l.startswith("samtools.") or l == "samtools")
            ]
            print(
                f"  size={entry['size']}  {text}  "
                f"({entry['count']:3d} pipelines, non-samtools: {', '.join(non_st)})"
            )
        print()
    print("  (see analysis_report_full/07_catalog.txt)")
    print()

    if catalog:
        exact = exact_subgraph_convergence(catalog, min_pipelines=3)
        print(
            f"=== Exact subgraph convergence (same labels, same edges, >=3 pipelines) ==="
        )
        print(
            f"  {len(exact)} entries shared by >=3 pipelines ({100*len(exact)//len(catalog)}% of catalog)."
        )
        if exact:
            print("  Top entries by pipeline count:")
            for e in exact[:10]:
                text = _format_subgraph(e["labels"], e["edges"])
                print(
                    f"    {text} — {len(e['pipelines'])} pipelines ({e['n_pairs']} pairs)"
                )
        print()

    if templates:
        n_templates = len(templates)
        n_samtools = sum(1 for t in templates if t["all_samtools"])
        summary = (
            template_full_summary(catalog, templates, pairwise) if pairwise else None
        )
        total_variants = sum(t["n_variants"] for t in templates[:5])
        print(
            f"=== Template families ({n_templates} families, {n_samtools} all-samtools) ==="
        )
        print(
            "  Each template groups catalog entries by label_set (ignoring edge differences)."
        )
        print(
            f"  Top 5 templates account for {total_variants}/{len(catalog)} entries "
            f"({100 * total_variants // len(catalog)}% of catalog)."
        )
        if summary:
            print(
                f"  Cross-pair convergence: {summary['n_cross_pair']} templates ({100*summary['n_cross_pair']//n_templates}%) span >1 pipeline pair."
            )
            print(
                f"  Multi-variant templates: {summary['n_multi_variant']} ({100*summary['n_multi_variant']//n_templates}%) — 100% cross-pair."
            )
            print(
                f"  Triple convergence (>=3 variants, >=3 pairs): {summary['n_triple_convergence']} templates."
            )
        print("  Top template families by pipeline coverage:")
        for t in templates[:5]:
            tag = "all-samtools" if t["all_samtools"] else "mixed"
            print(
                f"    size={t['size']}  {', '.join(t['node_set'][:4])}{'...' if len(t['node_set']) > 4 else ''}  "
                f"{t['n_variants']} variants, up to {t['total_pipelines']} pipelines, {tag}"
            )
        print()
    print("  (see analysis_report_full/08_templates.txt)")
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
        if templates:
            dom = pair_dominance(pairwise)
            summary = template_full_summary(catalog, templates, pairwise)
            n_samtools = sum(1 for t in templates if t["all_samtools"])
            print(
                f"  Of {len(catalog)} motifs, {n_samtools} template families are all-samtools "
                f"combinatorial variants — see 08_templates.txt."
            )
            print(
                f"  {summary['n_pairs_with_shared']} pairs share at least 1 entry. "
                f"Top pair: {summary['top_pair_name']} ({summary['top_pair_pct']:.1f}%). "
                f"Top 15: {summary['top_15_cumul_pct']:.1f}% cumulative."
            )
            if dom:
                print("  Pair dominance (cumulative %):")
                for i, d in enumerate(dom[:5]):
                    an = (
                        d["a"].split("/")[-1].replace("nf-core.", "")
                        if "/" in d["a"]
                        else d["a"]
                    )
                    bn = (
                        d["b"].split("/")[-1].replace("nf-core.", "")
                        if "/" in d["b"]
                        else d["b"]
                    )
                    print(
                        f"    {i+1}. {an:25s} ↔ {bn:25s}  {d['count']:5d} ({d['pct']:.1f}%, cumul {d['cum_pct']:.1f}%)"
                    )
        for cnt, a, b, _keys in pairwise[:15]:
            print(f"  {a:35s} \u2194 {b:35s}  ({cnt:2d} shared)")
        print()
    print("  (see analysis_report_full/09_pairs.txt)")
    print()

    print("=== Example singleton tools ===")
    for t, wf in singletons[:20]:
        print(f"  {t:20s} only in {wf}")
    print()
    print("  (see analysis_report_full/06_singletons.txt)")


def _full_meta(graphs, tool_wfs, graph_quality):
    """Generator yielding lines for meta section: header, graph quality, pipeline status."""
    n_total = len(graphs)
    n_success = sum(1 for g in graphs if len(g["nodes"]) > 0)
    n_empty = n_total - n_success
    tools_sorted = sorted(tool_wfs.items(), key=lambda x: -len(x[1]))
    total_unique_tools = len(tool_wfs)
    singletons = [(t, list(ps)[0]) for t, ps in tool_wfs.items() if len(ps) == 1]

    toc_lines, sec = _make_toc("Graph quality", "Pipeline status")
    yield from toc_lines

    yield f"Pipelines: {n_total} ({n_success} with DAG, {n_empty} empty)"
    yield f"Unique tools: {total_unique_tools} ({len(singletons)} singletons)"
    yield ""
    yield "  See 10_origins.txt for module origin analysis."
    yield ""

    if graph_quality:
        (
            empty_by_category,
            empty_external,
            split_dags,
            isolated_dags,
            status_breakdown,
        ) = graph_quality
        n_empty = sum(len(v) for v in empty_by_category.values()) + len(empty_external)
        yield f"[{sec['Graph quality']}] === Graph quality ==="
        yield f"  Empty DAGs: {n_empty}/{n_total} ({100 * n_empty // n_total}%)"
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
                    yield f"    {cat:20s} {pname}{suffix}"
        if empty_external:
            for pname, _ in empty_external:
                yield f"    {'external':20s} {pname}"
        if split_dags:
            split_dags.sort(key=lambda x: -x[1])
            yield f"  Split DAGs (2+ components): {len(split_dags)}"
            yield f"  {'Pipeline':40s} {'Comp':>4s} {'Nodes':>5s} {'Edges':>5s}"
            yield f"  {'-' * 40} {'-' * 4} {'-' * 5} {'-' * 5}"
            for pname, comp, nn, ne in split_dags:
                yield f"  {pname:40s} {comp:4d} {nn:5d} {ne:5d}"
        if isolated_dags:
            yield f"  Isolated DAGs (0 edges): {len(isolated_dags)}"
            for pname, nn, ne in isolated_dags:
                yield f"    {pname:40s} nodes={nn} edges={ne}"
        yield ""

    if graph_quality:
        _, _, _, _, status_breakdown = graph_quality
        yield f"[{sec['Pipeline status']}] === Pipeline status ==="
        total = sum(status_breakdown["counts"].values())
        for st in ["active", "archived", "unreleased"]:
            cnt = status_breakdown["counts"][st]
            if cnt:
                ok = status_breakdown["success"][st]
                fail = status_breakdown["fail"][st]
                pct = 100 * cnt // total
                ok_pct = 100 * ok // cnt if cnt else 0
                yield f"  {st:12s} {cnt:3d} ({pct:2d}%) — {ok} DAG success ({ok_pct}%), {fail} empty"
        yield ""


def _full_tools(tool_wfs):
    """Generator: all tools with pipeline counts."""
    tools_sorted = sorted(tool_wfs.items(), key=lambda x: -len(x[1]))
    toc_lines, sec = _make_toc("All tools with pipeline counts")
    yield from toc_lines
    yield f"[{sec['All tools with pipeline counts']}] === All tools with pipeline counts ==="
    for t, ps in tools_sorted:
        pipelines = ", ".join(sorted(ps))
        yield f"  {t:25s} {len(ps):3d} pipelines: {pipelines}"
    yield ""
    yield "  See 10_origins.txt for module origin provenance analysis."
    yield ""


def _full_singletons(tool_wfs):
    """Generator: all singleton tools."""
    singletons = [(t, list(ps)[0]) for t, ps in tool_wfs.items() if len(ps) == 1]
    toc_lines, sec = _make_toc("All singleton tools")
    yield from toc_lines
    yield f"[{sec['All singleton tools']}] === All singleton tools ==="
    for t, wf in singletons:
        yield f"  {t:20s} only in {wf}"
    yield ""


def _full_cooccurrence(cooccur):
    """Generator: all co-occurrences."""
    toc_lines, sec = _make_toc("All co-occurrences")
    yield from toc_lines
    yield f"[{sec['All co-occurrences']}] === All co-occurrences ==="
    yield "  Jaccard = overlap / union | overlap = pipelines using both"
    for cnt, jac, t1, t2, n1, n2 in cooccur:
        yield f"  {t1:15s} + {t2:15s}  Jaccard={jac:.2f}  overlap={cnt:2d}  sizes=({n1},{n2})"
    yield ""


def _full_transitions(transitions, divergence, convergence, graphs=None):
    """Generator: all transitions, chains, divergence, convergence, self-loops."""
    _arrow = "\u2192"
    toc_lines, sec = _make_toc(
        "All transitions",
        "All 2-step tool chains",
        f"All divergence patterns (tool {_arrow} {{successors}})",
        f"All convergence patterns ({{predecessors}} {_arrow} tool)",
        "Potential toolkits (self-loops)",
    )
    yield from toc_lines
    yield f"[{sec['All transitions']}] === All transitions ==="
    for cnt, src, dst, wfs in transitions:
        pipelines = ", ".join(sorted(wfs))
        yield f"  {src:20s} -> {dst:20s}  ({cnt:3d} edges)  pipelines={pipelines}"
    yield ""

    chains = _build_chains(transitions)
    if chains:
        yield f"[{sec['All 2-step tool chains']}] === All 2-step tool chains ==="
        for cnt, a, b, c, pl in chains:
            pipelines = ", ".join(pl)
            yield f"  {a:20s} -> {b:20s} -> {c:20s}  ({cnt:3d} pipelines)  {pipelines}"
        yield ""

    if divergence:
        flat = sorted(
            [
                (cnt, tool, nset, pl)
                for tool, items in divergence.items()
                for cnt, nset, pl in items
            ],
            key=lambda x: -x[0],
        )
        _atitle = f"All divergence patterns (tool {_arrow} {{successors}})"
        yield f"[{sec[_atitle]}] === All divergence patterns (tool {_arrow} {{successors}}) ==="
        for cnt, tool, nset, pl in flat:
            pipelines = ", ".join(pl)
            yield f"  {tool:20s} \u2192 {format_set(nset):40s} ({cnt:3d} pipelines)  {pipelines}"
        yield ""

    if convergence:
        flat = sorted(
            [
                (cnt, tool, nset, pl)
                for tool, items in convergence.items()
                for cnt, nset, pl in items
            ],
            key=lambda x: -x[0],
        )
        _ctitle = f"All convergence patterns ({{predecessors}} {_arrow} tool)"
        yield f"[{sec[_ctitle]}] === All convergence patterns ({{predecessors}} {_arrow} tool) ==="
        for cnt, tool, nset, pl in flat:
            pipelines = ", ".join(pl)
            yield f"  {format_set(nset):40s} \u2192 {tool:20s} ({cnt:3d} pipelines)  {pipelines}"
        yield ""

    self_loops = _find_self_loops(transitions)
    if self_loops:
        yield f"[{sec['Potential toolkits (self-loops)']}] === Potential toolkits (self-loops) ==="
        if graphs:
            slo = self_loop_origin_analysis(transitions, graphs)
            yield f"  {'Tool':20s} {'Edges':>6s} {'Origin(s)':20s} {'Status':20s}"
            yield f"  {'-' * 20} {'-' * 6} {'-' * 20} {'-' * 20}"
            for e in slo:
                origin_str = "+".join(sorted(e["origins"].keys()))
                tag = "KNOWN_SUBTOOLS" if e["known_subtool"] else "candidate"
                yield f"  {e['tool']:20s} {e['self_loop_count']:6d} {origin_str:20s} {tag:20s}"
        else:
            for cnt, tool in self_loops:
                yield f"  {tool:20s} -> {tool:20s}  ({cnt:3d} edges)"
        yield ""


def _full_topology(topo, domains, pipeline_detail):
    """Generator: topology, domain clusters, pipeline-domain detail."""
    toc_lines, sec = _make_toc(
        "Topology (all pipelines)", "Domain clusters (all)", "Pipeline-domain detail"
    )
    yield from toc_lines
    yield f"[{sec['Topology (all pipelines)']}] === Topology (all pipelines) ==="
    yield f"  {'Pipeline':40s} {'Nodes':>5s} {'Edges':>5s} {'Ratio':>5s}  Tools"
    yield f"  {'-' * 40} {'-' * 5} {'-' * 5} {'-' * 5}  {'-' * 30}"
    topo_sorted = sorted(topo, key=lambda x: -x[1])
    for pname, nnodes, nedges, ratio, tools in topo_sorted:
        tool_str = ", ".join(sorted(tools)) if tools else "\u2014"
        yield f"  {pname:40s} {nnodes:5d} {nedges:5d} {ratio:.2f}  {tool_str}"
    yield ""

    yield f"[{sec['Domain clusters (all)']}] === Domain clusters (all) ==="
    for dt, data in sorted(domains.items()):
        pipeline_names = [p[0] for p in data["pipelines"]]
        tool_summary = "; ".join(
            f"{t} in {len(ps)}" for t, ps in sorted(data["tools"].items())
        )
        certs_str = ", ".join(f"{p[0]}({p[2]:.2f})" for p in data["pipelines"])
        yield f"  {dt:20s} {len(pipeline_names):2d} pipelines: {', '.join(sorted(pipeline_names))}"
        yield f"  {'':20s} found via: {tool_summary}"
        yield f"  {'':20s} certainty: {certs_str}"
    yield ""

    yield f"[{sec['Pipeline-domain detail']}] === Pipeline-domain detail ==="
    detail = pipeline_detail or {}
    if detail:
        yield f"  {'Pipeline':35s} {'Domain':20s} {'Cert.':>6s}  Tools"
        yield f"  {'-' * 35} {'-' * 20} {'-' * 6}  {'-' * 30}"
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
                    yield f"  {pname:35s} {domain:20s} {cert:>6s}  {tool_str}"
                else:
                    yield f"  {'':35s} {domain:20s} {cert:>6s}  {tool_str}"
    yield ""


def _full_catalog(catalog, non_samtools_catalog):
    """Generator: all catalog entries, exact subgraph convergence, non-samtools filter."""
    n_catalog = len(catalog)
    toc_lines, sec = _make_toc(
        "All common connected subgraphs",
        "Exact subgraph convergence",
        "Non-only-samtools subgraphs",
    )
    yield from toc_lines
    yield f"[{sec['All common connected subgraphs']}] === All common connected subgraphs ({n_catalog} entries) ==="
    yield "  Each entry is a distinct (node_set, edge_set) combination — the catalog."
    yield "  All counts are unique: no duplicate subgraph is counted twice for the same pipeline."
    yield ""
    for entry in catalog:
        text = _format_subgraph(entry["labels"], entry["edges"])
        yield f"  size={entry['size']}  {text}  ({entry['count']:3d} pipelines)"
    yield ""

    # Exact subgraph convergence section
    exact = exact_subgraph_convergence(catalog, min_pipelines=3)
    yield f"[{sec['Exact subgraph convergence']}] === Exact subgraph convergence (same labels, same edges, >=3 pipelines) ==="
    yield f"  {len(exact)} entries shared by >=3 pipelines ({100*len(exact)//n_catalog}% of catalog)."
    yield ""
    if exact:
        yield f"  {'Count':>5s} {'Pairs':>5s} {'Size':>4s}  Subgraph"
        yield f"  {'-' * 5} {'-' * 5} {'-' * 4}  {'-' * 50}"
        for e in exact[:20]:
            text = _format_subgraph(e["labels"], e["edges"])
            yield f"  {len(e['pipelines']):5d} {e['n_pairs']:5d} {e['size']:4d}  {text}"
        yield ""
        yield "  Full listing (grouped by pipeline count):"
        by_count = {}
        for e in exact:
            by_count.setdefault(len(e["pipelines"]), []).append(e)
        for nc in sorted(by_count, reverse=True):
            entries = by_count[nc]
            yield f"    Pipeline count = {nc} ({len(entries)} entries):"
            for e in entries:
                text = _format_subgraph(e["labels"], e["edges"])
                yield f"      size={e['size']}  {text}  (pipelines: {', '.join(e['pipelines'])})"
            yield ""

    if non_samtools_catalog:
        yield f"[{sec['Non-only-samtools subgraphs']}] === Non-only-samtools subgraphs ==="
        yield "  Subgraphs that include at least one tool outside the samtools family:"
        for entry in non_samtools_catalog:
            text = _format_subgraph(entry["labels"], entry["edges"])
            non_st = [
                l
                for l in entry["labels"]
                if not (l.startswith("samtools.") or l == "samtools")
            ]
            yield f"  size={entry['size']}  {text}  ({entry['count']:3d} pipelines, non-samtools: {', '.join(non_st)})"
        yield ""


def _full_templates(templates, catalog, pairwise):
    """Generator: template families, cross-pair convergence analysis."""
    n_templates = len(templates)
    n_samtools = sum(1 for t in templates if t["all_samtools"])
    toc_lines, sec = _make_toc(
        "Template families (extended node sets)",
        "Template families (grouped by node set)",
        "Cross-pair convergence analysis",
    )
    yield from toc_lines
    yield f"[{sec['Template families (extended node sets)']}] === Template families (extended node sets) ({n_templates} families, {n_samtools} all-samtools, {n_templates - n_samtools} with non-samtools tools) ==="
    yield "  Each template groups catalog entries by label_set (ignoring edge differences)."
    yield ""
    ndigits = len(str(n_templates))
    yield f"  {'ID':>{ndigits+1}s}  Node set"
    yield f"  {'-' * (ndigits+1)}  {'-' * 50}"
    for i, t in enumerate(templates, 1):
        tid = f"T{i:0{ndigits}d}"
        yield f"  {tid:>{ndigits+1}s}  {', '.join(t['node_set'])}"
    yield ""
    yield f"[{sec['Template families (grouped by node set)']}] === Template families (grouped by node set) ==="
    yield f"  {'ID':>{ndigits+1}s} {'Sz':>3s} {'Vars':>5s} {'Pipes':>6s} {'Max':>4s}  Type"
    yield f"  {'-' * (ndigits+1)} {'-' * 3} {'-' * 5} {'-' * 6} {'-' * 4}  {'-' * 15}"
    for i, t in enumerate(templates, 1):
        tid = f"T{i:0{ndigits}d}"
        tag = "all-samtools" if t["all_samtools"] else "mixed"
        yield f"  {tid:>{ndigits+1}s} {t['size']:3d} {t['n_variants']:5d} {t['total_pipelines']:6d} {t['max_count']:4d}  {tag}"
    yield ""

    # Cross-pair convergence section
    if pairwise:
        cross = cross_pair_convergence(catalog, templates)
        n_cross = sum(1 for r in cross if r["is_cross_pair"])
        n_multi = sum(1 for r in cross if r["multi_variant"])
        n_triple = sum(1 for r in cross if r["n_variants"] >= 3 and r["n_pairs"] >= 3)
        yield f"[{sec['Cross-pair convergence analysis']}] === Cross-pair convergence analysis ==="
        yield f"  Templates spanning >1 pipeline pair: {n_cross} ({100*n_cross//n_templates}%)"
        yield f"  Multi-variant templates: {n_multi} — 100% cross-pair"
        yield f"  Triple-convergence templates (>=3 variants, >=3 pairs): {n_triple}"
        yield ""
        yield "  Top 20 cross-pair templates (by pipeline pair span):"
        yield f"  {'Size':>4s} {'Variants':>8s} {'Pairs':>6s} {'Pipelines':>9s}  Tool set"
        yield f"  {'-' * 4} {'-' * 8} {'-' * 6} {'-' * 9}  {'-' * 40}"
        for r in cross[:20]:
            ns = ", ".join(r["node_set"][:4])
            if len(r["node_set"]) > 4:
                ns += "..."
            yield f"  {r['size']:4d} {r['n_variants']:8d} {r['n_pairs']:6d} {r['total_pipelines']:9d}  {ns}"
        yield ""
        yield "  Pair contribution distribution (top 15):"
        dom = pair_dominance(pairwise)
        cumul = 0
        for i, d in enumerate(dom[:15]):
            an = (
                d["a"].split("/")[-1].replace("nf-core.", "")
                if "/" in d["a"]
                else d["a"]
            )
            bn = (
                d["b"].split("/")[-1].replace("nf-core.", "")
                if "/" in d["b"]
                else d["b"]
            )
            yield f"    {i+1:2d}. {an:25s} \u2194 {bn:25s}  {d['count']:5d} ({d['pct']:.1f}%, cumul {d['cum_pct']:.1f}%)"
        yield ""


def _full_pairs(pairwise, catalog, templates):
    """Generator: all pipeline pairs with shared subgraphs and dominance analysis."""
    toc_lines, sec = _make_toc(
        "All pipeline pairs with shared subgraphs", "Pair dominance analysis"
    )
    yield from toc_lines
    yield f"[{sec['All pipeline pairs with shared subgraphs']}] === All pipeline pairs with shared subgraphs ==="
    yield "  Count = distinct connected subgraphs (node_set, edge_set) shared within each pair."
    yield "  A single large shared component produces many subset subgraphs, inflating counts."
    yield "  E.g., atacseq/chipseq share a large component; 17k = all connected subsets, not 17k independent motifs."
    if templates:
        n_samtools = sum(1 for t in templates if t["all_samtools"])
        yield f"  Of {len(catalog)} motifs, {n_samtools} template families are all-samtools combinatorial variants \u2014 see 08_templates.txt."
    for cnt, a, b, _keys in pairwise:
        yield f"  {a:35s} \u2194 {b:35s}  ({cnt:2d} shared)"
    yield ""

    # Pair dominance section
    dom = pair_dominance(pairwise)
    yield f"[{sec['Pair dominance analysis']}] === Pair dominance analysis ==="
    yield f"  Total pairs with shared entries: {len(dom)}"
    yield f"  Total shared entries across all pairs: {sum(d['count'] for d in dom)}"
    yield ""
    yield "  Cumulative contribution of top pairs:"
    yield f"  {'Rank':>4s} {'Pipeline A':30s} {'Pipeline B':30s} {'Count':>6s} {'%':>6s} {'Cumul%':>7s}"
    yield f"  {'-' * 4} {'-' * 30} {'-' * 30} {'-' * 6} {'-' * 6} {'-' * 7}"
    for i, d in enumerate(dom):
        an = d["a"].split("/")[-1].replace("nf-core.", "") if "/" in d["a"] else d["a"]
        bn = d["b"].split("/")[-1].replace("nf-core.", "") if "/" in d["b"] else d["b"]
        yield f"  {i+1:4d} {an:30s} {bn:30s} {d['count']:6d} {d['pct']:5.1f}% {d['cum_pct']:6.1f}%"
    yield ""


def _full_origins(graphs, transitions=None):
    """Generator: aggregate origin, mixed tools, pair co-occurrence, per-pipeline detail, self-loop origins."""
    total_unique, mo_totals, pipeline_origins = module_origin_summary(graphs)
    mixed = tool_origin_mixed(graphs)

    toc_titles = [
        "Aggregate module origin",
        "Mixed-origin tools",
        "Origin-set distribution",
        "Per-pipeline origin detail",
    ]
    if transitions:
        toc_titles.append("Self-loop origin analysis")
    toc_lines, sec = _make_toc(*toc_titles)
    yield from toc_lines

    yield f"[{sec['Aggregate module origin']}] === Aggregate module origin ==="
    if total_unique > 0:
        yield f"  {'Origin':10s} {'Unique':>6s} {'%':>4s}"
        yield f"  {'-' * 10} {'-' * 6} {'-' * 4}"
        for origin in ["nf-core", "local", "heuristic", "unknown"]:
            cnt = mo_totals.get(origin, 0)
            if cnt:
                yield f"  {origin:10s} {cnt:6d} {100 * cnt // total_unique:3d}%"
    yield ""

    yield f"[{sec['Mixed-origin tools']}] === Mixed-origin tools ==="
    s = mixed["summary"]
    yield f"  Total tools: {s['total_tools']}"
    yield f"  Pure-origin tools (single origin): {s['pure_tools']}"
    yield f"  Mixed-origin tools (>=2 origins): {s['mixed_tools']} ({s['pct_mixed']:.1f}%)"
    yield ""

    tools_data = mixed["tools"]
    if tools_data:
        yield f"  {'Tool':25s} {'Origins':30s} Pipeline distribution"
        yield f"  {'-' * 25} {'-' * 30} {'-' * 40}"
        for app in sorted(tools_data):
            origins = tools_data[app]
            origin_str = ", ".join(sorted(origins.keys()))
            parts = [f"{o}={len(ps)}" for o, ps in sorted(origins.items())]
            yield f"  {app:25s} {origin_str:30s} {' | '.join(parts)}"
    else:
        yield "  No tools with mixed origins found."
    yield ""

    yield f"[{sec['Origin-set distribution']}] === Origin-set distribution ==="
    yield "  All origin combinations across all tools (including zero counts)."
    yield ""
    all_subsets = mixed["all_subsets"]
    current_size = None
    for key, cnt in all_subsets:
        size = len(key.split("+"))
        if size != current_size:
            if current_size is not None:
                yield ""
            current_size = size
            yield f"  -- {size} origin(s) --"
        yield f"    {key:45s} {cnt:4d} tools"

    yield f"[{sec['Per-pipeline origin detail']}] === Per-pipeline origin detail ==="
    for pname in sorted(pipeline_origins):
        counts = pipeline_origins[pname]
        parts = ", ".join(f"{k}={v}" for k, v in sorted(counts.items()))
        yield f"  {pname:35s} {parts}"
    yield ""

    if transitions:
        slo = self_loop_origin_analysis(transitions, graphs)
        if slo:
            yield f"[{sec['Self-loop origin analysis']}] === Self-loop origin analysis ==="
            yield "  Cross-reference of self-loop tools (potential toolkits) with module origin."
            yield ""
            yield f"  {'Tool':20s} {'Edges':>6s} {'Origin(s)':20s} {'Pipes':>6s} {'Status':20s}"
            yield f"  {'-' * 20} {'-' * 6} {'-' * 20} {'-' * 6} {'-' * 20}"
            for e in slo:
                origin_str = "+".join(sorted(e["origins"].keys()))
                tag = "KNOWN_SUBTOOLS" if e["known_subtool"] else "candidate"
                yield f"  {e['tool']:20s} {e['self_loop_count']:6d} {origin_str:20s} {e['pipeline_count']:6d} {tag:20s}"
            yield ""


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
    templates=None,
    non_samtools_catalog=None,
):
    """Print comprehensive report with ALL data (not truncated)."""
    for line in _full_meta(graphs, tool_wfs, graph_quality):
        print(line)
    for line in _full_tools(tool_wfs):
        print(line)
    for line in _full_cooccurrence(cooccur):
        print(line)
    for line in _full_transitions(transitions, divergence, convergence, graphs):
        print(line)
    for line in _full_topology(topo, domains, pipeline_detail):
        print(line)
    for line in _full_singletons(tool_wfs):
        print(line)
    if catalog is not None:
        for line in _full_catalog(catalog, non_samtools_catalog):
            print(line)
    if templates is not None:
        for line in _full_templates(templates, catalog, pairwise):
            print(line)
    if pairwise is not None:
        for line in _full_pairs(pairwise, catalog, templates):
            print(line)
    for line in _full_origins(graphs, transitions):
        print(line)


def _write_full_report_dir(
    report_dir,
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
    templates=None,
    non_samtools_catalog=None,
):
    """Write the full report as a directory of numbered files, one per section."""
    import os

    os.makedirs(report_dir, exist_ok=True)
    sections = [
        ("01_meta.txt", _full_meta(graphs, tool_wfs, graph_quality)),
        ("02_tools.txt", _full_tools(tool_wfs)),
        ("03_cooccurrence.txt", _full_cooccurrence(cooccur)),
        (
            "04_transitions.txt",
            _full_transitions(transitions, divergence, convergence, graphs),
        ),
        ("05_topology.txt", _full_topology(topo, domains, pipeline_detail)),
        ("06_singletons.txt", _full_singletons(tool_wfs)),
        (
            "07_catalog.txt",
            (
                _full_catalog(catalog, non_samtools_catalog)
                if catalog is not None
                else iter([])
            ),
        ),
        (
            "08_templates.txt",
            (
                _full_templates(templates, catalog, pairwise)
                if templates is not None
                else iter([])
            ),
        ),
        (
            "09_pairs.txt",
            (
                _full_pairs(pairwise, catalog, templates)
                if pairwise is not None
                else iter([])
            ),
        ),
        ("10_origins.txt", _full_origins(graphs, transitions)),
    ]
    for fname, gen in sections:
        path = os.path.join(report_dir, fname)
        with open(path, "w") as f:
            for line in gen:
                f.write(line + "\n")
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
