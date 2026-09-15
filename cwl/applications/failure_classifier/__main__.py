import argparse
import json
import os
import sys

from failure_classifier.classifier import classify


def main():
    parser = argparse.ArgumentParser(
        description="Classify nextflow pipeline failures by scanning logs"
    )
    parser.add_argument(
        "target", help="Pipeline output directory, or a parent dir with summary.json"
    )
    parser.add_argument("--error", help="Error string from summary.json (optional)")
    parser.add_argument(
        "--exit-code", type=int, help="Exit code from summary.json (optional)"
    )
    parser.add_argument("--log", help="Explicit path to nextflow_output.log (optional)")
    parser.add_argument(
        "--pipeline-name",
        help="Explicit pipeline name (default: basename of target dir)",
    )
    parser.add_argument("--summary", help="Path to summary.json for batch mode")
    args = parser.parse_args()

    summary_path = args.summary
    if not summary_path:
        candidate = os.path.join(args.target, "summary.json")
        if os.path.isfile(candidate):
            summary_path = candidate

    if summary_path:
        with open(summary_path) as f:
            summary = json.load(f)
        failures = summary.get("failures", [])
        if not failures:
            print(
                json.dumps({"error": "No failures in summary"}, indent=2),
                file=sys.stderr,
            )
            sys.exit(1)
        results = []
        for entry in failures:
            pipeline = entry.get("pipeline", "unknown")
            log_path = entry.get("output_log", "")
            error_str = entry.get("error", "")
            exit_code = entry.get("exit_code")

            if log_path and os.path.isfile(log_path):
                pipeline_dir = os.path.dirname(log_path)
                result = classify(
                    pipeline_dir,
                    error_str=error_str,
                    exit_code=exit_code,
                    log_path=log_path,
                    pipeline_name=pipeline,
                )
            elif error_str:
                result = classify(
                    args.target,
                    error_str=error_str,
                    exit_code=exit_code,
                    pipeline_name=pipeline,
                )
            else:
                result = {
                    "pipeline": pipeline,
                    "category": "unclassified",
                    "confidence": 0.0,
                    "label": "No log file or error string available",
                    "evidence": "",
                    "exit_code": exit_code,
                }
            result["pipeline"] = pipeline
            results.append(result)
        print(json.dumps(results, indent=2))
    else:
        result = classify(
            args.target,
            error_str=args.error,
            exit_code=args.exit_code,
            log_path=args.log,
            pipeline_name=args.pipeline_name,
        )
        print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
