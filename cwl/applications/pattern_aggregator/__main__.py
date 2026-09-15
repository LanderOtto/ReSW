import argparse
import json
import sys

from pattern_aggregator.aggregator import build_from_api, build_patterns
from pattern_aggregator.query import query_app


def cmd_build(args):
    if args.from_api:
        patterns = build_from_api(args.input_file)
    else:
        patterns = build_patterns(args.input_file)
    with open(args.output, "w") as f:
        json.dump(patterns, f, indent=2)
    print(
        f"Wrote {args.output}  ({patterns['total_workflows']} workflows, "
        f"{len(patterns['wf_count'])} apps, "
        f"{sum(len(v) for v in patterns['transition_count'].values())} transitions)"
    )


def cmd_query(args):
    with open(args.patterns) as f:
        patterns = json.load(f)
    result = query_app(patterns, args.current, top=args.top)
    print(result)


def cmd_validate(args):
    from pattern_aggregator.validate import validate_patterns

    with open(args.api) as f:
        api = json.load(f)
    with open(args.dag) as f:
        dag = json.load(f)
    result = validate_patterns(api, dag)
    report_path = args.output
    with open(report_path, "w") as f:
        json.dump(result, f, indent=2)
    s = result["summary"]
    print(
        f"Wrote {report_path}  "
        f"(api={s['total_api_apps']}, dag={s['total_dag_apps']}, "
        f"api_only={s['api_only_count']}, dag_only={s['dag_only_count']}, "
        f"mismatch={s['count_mismatch_count']})",
        file=sys.stderr,
    )


def main():
    parser = argparse.ArgumentParser(
        description="Build and query a Markov-1 transition model from workflow graphs"
    )
    sub = parser.add_subparsers(dest="command", required=True)

    build_p = sub.add_parser(
        "build", help="Build patterns.json from graph manifest or API listing"
    )
    build_p.add_argument(
        "input_file", help="Path to manifest.json or pipelines.json (see --from-api)"
    )
    build_p.add_argument(
        "--from-api", action="store_true", help="Input is pipelines.json (API metadata)"
    )
    build_p.add_argument(
        "--output", default="patterns.json", help="Output path (default: patterns.json)"
    )
    build_p.set_defaults(func=cmd_build)

    query_p = sub.add_parser("query", help="Query patterns for next-step suggestions")
    query_p.add_argument("--patterns", required=True, help="Path to patterns.json")
    query_p.add_argument("--current", required=True, help="Current application name")
    query_p.add_argument(
        "--top", type=int, default=5, help="Number of suggestions (default: 5)"
    )
    query_p.set_defaults(func=cmd_query)

    validate_p = sub.add_parser(
        "validate",
        help="Compare API-derived and DAG-derived patterns and report discrepancies",
    )
    validate_p.add_argument("--api", required=True, help="API-derived patterns.json")
    validate_p.add_argument("--dag", required=True, help="DAG-derived patterns.json")
    validate_p.add_argument(
        "--output",
        default="validation.json",
        help="Validation report output (default: validation.json)",
    )
    validate_p.set_defaults(func=cmd_validate)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
