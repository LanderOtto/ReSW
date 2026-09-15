import json

from nfcore_toolkit.common import STATUS_KEYS


def collect_results(manifest_path):
    with open(manifest_path) as f:
        manifest = json.load(f)
    graphs = manifest.get("graphs", [])
    failures = []
    successes = []

    for data in graphs:
        meta = data.get("graph", data)
        pipeline = meta.get("id") or meta.get("pipeline", "unknown")
        failure_classification = meta.get("failure_classification")

        if failure_classification:
            exit_code = failure_classification.get("exit_code", -1)
            entry = {
                "pipeline": pipeline,
                "exit_code": exit_code,
                "error": failure_classification.get("label", "unknown error"),
                "failure_classification": failure_classification,
            }
            for key in STATUS_KEYS:
                if key in meta:
                    entry[key] = meta[key]
            failures.append(entry)
        else:
            exit_code = meta.get("exit_code", 0)
            if exit_code != 0 or (meta.get("error") and not meta.get("steps")):
                entry = {
                    "pipeline": pipeline,
                    "exit_code": exit_code,
                    "error": meta.get("error", "unknown error"),
                }
                for key in STATUS_KEYS:
                    if key in meta:
                        entry[key] = meta[key]
                failures.append(entry)
            else:
                successes.append(
                    {
                        "pipeline": pipeline,
                        "exit_code": exit_code,
                    }
                )

    # Aggregate failure classifications by category
    failure_categories = {}
    for entry in failures:
        fc = entry.get("failure_classification", {})
        cat = fc.get("category", "unclassified")
        failure_categories.setdefault(cat, {"count": 0, "pipelines": []})
        failure_categories[cat]["count"] += 1
        failure_categories[cat]["pipelines"].append(entry["pipeline"])

    return {
        "total": len(graphs),
        "success": len(successes),
        "failed": len(failures),
        "failures": failures,
        "failure_categories": failure_categories,
    }
