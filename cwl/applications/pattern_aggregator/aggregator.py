import json


def _topological_sort(nodes, links):
    app_by_id = {}
    for n in nodes:
        nid = n.get("id")
        app = n.get("app")
        if nid and app is not None:
            app_by_id[nid] = app

    incoming = {}
    for link in links:
        s, d = link.get("source"), link.get("target")
        if s and d:
            incoming.setdefault(d, []).append(s)

    in_deg = {}
    for nid in app_by_id:
        in_deg[nid] = len(incoming.get(nid, []))

    out_map = {}
    for link in links:
        s, d = link.get("source"), link.get("target")
        if s and d:
            out_map.setdefault(s, []).append(d)

    queue = [nid for nid, d in in_deg.items() if d == 0]
    order = []
    while queue:
        nid = queue.pop(0)
        order.append(nid)
        for nxt in out_map.get(nid, []):
            if nxt in in_deg:
                in_deg[nxt] -= 1
                if in_deg[nxt] == 0:
                    queue.append(nxt)
    return order


def _tag_node_positions(nodes, links):
    topo = _topological_sort(nodes, links)
    n = len(topo)
    positions = {}
    for i, nid in enumerate(topo):
        ratio = i / (n - 1) if n > 1 else 0.5
        if ratio < 1 / 3:
            positions[nid] = "EARLY"
        elif ratio < 2 / 3:
            positions[nid] = "MID"
        else:
            positions[nid] = "LATE"
    return positions


def build_patterns_from_graphs(graphs):
    wf_count = {}
    transition_count = {}
    bigram_count = {}
    position_stats = {}
    by_position = {}
    positional_depth = {}
    total_workflows = len(graphs)

    for graph in graphs:
        wf_id = graph.get("graph", {}).get("id")
        if not wf_id:
            wf_id = "unknown"

        nodes = graph.get("nodes", [])
        links = graph.get("links", [])
        app_by_id = {}
        seen_apps = set()

        for node in nodes:
            nid = node.get("id")
            app = node.get("app")
            if app is None or nid is None:
                continue
            app_by_id[nid] = app
            if app not in seen_apps:
                seen_apps.add(app)
                entry = wf_count.setdefault(app, {"count": 0, "workflows": []})
                if wf_id not in entry["workflows"]:
                    entry["count"] += 1
                    entry["workflows"].append(wf_id)

        node_positions = _tag_node_positions(nodes, links)

        for node in nodes:
            nid = node.get("id")
            app = node.get("app")
            if app is None or nid is None:
                continue
            tag = node_positions.get(nid, "MID")
            stats = position_stats.setdefault(app, {"EARLY": 0, "MID": 0, "LATE": 0})
            stats[tag] += 1

        incoming = {}
        for link in links:
            src = link.get("source")
            dst = link.get("target")
            incoming.setdefault(dst, []).append(src)

        for link in links:
            src = link.get("source")
            dst = link.get("target")
            src_app = app_by_id.get(src)
            dst_app = app_by_id.get(dst)
            if src_app is None or dst_app is None:
                continue

            src_pos = node_positions.get(src, "EARLY")
            pos_entry = (
                by_position.setdefault(src_pos, {})
                .setdefault(src_app, {})
                .setdefault(dst_app, {"count": 0, "workflows": []})
            )
            pos_entry["count"] += 1
            if wf_id not in pos_entry["workflows"]:
                pos_entry["workflows"].append(wf_id)

            node_order = _topological_sort(nodes, links)
            n = len(node_order)
            src_idx = node_order.index(src) if src in node_order else -1
            depth_ratio = src_idx / (n - 1) if n > 1 and src_idx >= 0 else 0.5
            pd_entry = positional_depth.setdefault(str(src_app), {}).setdefault(
                str(dst_app), []
            )
            pd_entry.append(depth_ratio)

            dst_entry = transition_count.setdefault(src_app, {}).setdefault(
                dst_app, {"count": 0, "workflows": []}
            )
            dst_entry["count"] += 1
            if wf_id not in dst_entry["workflows"]:
                dst_entry["workflows"].append(wf_id)

            for pred_id in incoming.get(src, []):
                pred_app = app_by_id.get(pred_id)
                if pred_app is None:
                    continue
                bg_entry = (
                    bigram_count.setdefault(pred_app, {})
                    .setdefault(src_app, {})
                    .setdefault(dst_app, {"count": 0, "workflows": []})
                )
                bg_entry["count"] += 1
                if wf_id not in bg_entry["workflows"]:
                    bg_entry["workflows"].append(wf_id)

    return {
        "total_workflows": total_workflows,
        "wf_count": dict(sorted(wf_count.items())),
        "transition_count": {
            src: dict(sorted(dst.items()))
            for src, dst in sorted(transition_count.items())
        },
        "bigram_count": {
            pred: {src: dict(sorted(dst.items())) for src, dst in sorted(inner.items())}
            for pred, inner in sorted(bigram_count.items())
        },
        "position_stats": dict(sorted(position_stats.items())),
        "positional_depth": {
            src: dict(sorted(dst.items()))
            for src, dst in sorted(positional_depth.items())
        },
        "by_position": {
            pos: {src: dict(sorted(dst.items())) for src, dst in sorted(table.items())}
            for pos, table in sorted(by_position.items())
        },
    }


def build_patterns(manifest_path):
    with open(manifest_path) as f:
        manifest = json.load(f)
    graphs = manifest.get("graphs", [])
    return build_patterns_from_graphs(graphs)


def build_from_api(pipelines_path):
    with open(pipelines_path) as f:
        pipelines = json.load(f)
    graphs = []
    for pipeline in pipelines:
        full_name = pipeline.get("full_name", "")
        if not full_name:
            continue
        tools = pipeline.get("tools", [])
        nodes = [{"id": f"tool_{i}", "app": tool} for i, tool in enumerate(tools)]
        graphs.append(
            {
                "graph": {"id": full_name},
                "nodes": nodes,
                "links": [],
            }
        )
    return build_patterns_from_graphs(graphs)
