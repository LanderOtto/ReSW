import argparse

from .analyze import main as analyze_main
from .constants import DEFAULT_CACHE_DIR
from .plotter import main as plot_main


def main():
    parser = argparse.ArgumentParser(description="")
    sub = parser.add_subparsers(dest="command", required=True)

    analize_parser = sub.add_parser(
        "analize",
        help="Nextflow pipeline analysis: catalog, cross-reference, module usage",
    )

    analize_parser.add_argument(
        "--limit",
        type=int,
        default=0,
        help="Repos to analyze for module usage (0 = stats only)",
    )
    analize_parser.add_argument(
        "--json", default="nextflow_analysis.json", help="Output JSON path"
    )
    analize_parser.add_argument(
        "--cache-dir",
        default=DEFAULT_CACHE_DIR,
        help="Directory for API caches and cloned repos",
    )
    analize_parser.add_argument(
        "--cache-ttl",
        type=int,
        default=60,
        help="API cache TTL in minutes (default: 60)",
    )
    analize_parser.add_argument(
        "--no-cache", action="store_true", help="Force fresh API calls"
    )
    analize_parser.add_argument(
        "--weights",
        metavar="JSON",
        default=None,
        help="Path to a JSON file with MRS mixture weights "
        "(e.g. workdir/metric_calibration/best.json). "
        "Uses the provisional default weights when omitted.",
    )
    analize_parser.set_defaults(func=analyze_main)

    plot_parser = sub.add_parser(
        "plot",
        help="Community snapshot ('pre-analysis') plots from a full "
        "nextflow_analysis.json",
    )
    plot_parser.add_argument("json_path", nargs="?", default="nextflow_analysis.json")
    plot_parser.add_argument("output_dir", nargs="?", default="plots")
    # plot_parser.add_argument("--nfcore-modules", default=None,#DEFAULT_MODULES_TXT,
    #                     help="nf-core module list cache (counts for the inventory plot)")
    plot_parser.add_argument(
        "--cache-dir",
        default=DEFAULT_CACHE_DIR,
        help="Directory for API caches and cloned repos",
    )
    plot_parser.add_argument(
        "--font-path", default=None, help="Font path for the images"
    )
    plot_parser.set_defaults(func=plot_main)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
