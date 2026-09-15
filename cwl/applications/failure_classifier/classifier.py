from failure_classifier.loader import load_pipeline_dir
from failure_classifier.matchers import MATCHERS


def classify(
    pipeline_dir,
    error_str=None,
    exit_code=None,
    log_path=None,
    debug_log_path=None,
    pipeline_name=None,
):
    ctx = load_pipeline_dir(
        pipeline_dir, error_str, exit_code, log_path, debug_log_path, pipeline_name
    )
    for _name, fn in MATCHERS:
        result = fn(ctx)
        if result is not None:
            return {
                "pipeline": ctx["pipeline"],
                "category": result.category,
                "confidence": result.confidence,
                "label": result.label,
                "evidence": result.evidence[:300],
                "exit_code": ctx["exit_code"],
            }
    return {
        "pipeline": ctx["pipeline"],
        "category": "unclassified",
        "confidence": 0.0,
        "label": "No matching pattern found",
        "evidence": "",
        "exit_code": ctx["exit_code"],
    }
