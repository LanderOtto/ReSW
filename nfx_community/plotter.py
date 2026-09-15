import json

import matplotlib

matplotlib.use("Agg")

# from nextflow_preanalysis import PRE_PLOTS, DEFAULT_MODULES_TXT  # noqa: E402

# from nfx_community.plot import generate_all, ensure_nfcore_cache

from .plot import ensure_nfcore_cache, generate_all


def main(args):

    if args.font_path:
        import matplotlib.pyplot as plt
        from matplotlib import font_manager

        font_manager.fontManager.addfont(args.font_path)
        prop = font_manager.FontProperties(fname=args.font_path)
        plt.rcParams["font.family"] = prop.get_name()

    with open(args.json_path) as f:
        data = json.load(f)
    if data["module_analysis"]["analyzed"] == 0:
        raise Exception("Execute nfx analysis with --limit flag")

    nfcore_modules = ensure_nfcore_cache(args.cache_dir)

    # import json
    # with open(args.json_path) as f:
    #     data = json.load(f)

    # ma = data.get("module_analysis") or {}
    # repos = ma.get("repos") or []
    # if not repos:
    #     print(f"WARN: '{args.json_path}' has no module_analysis.repos "
    #           f"(it looks like a --limit 0 stats-only run).")
    #     print("      Re-run with a positive limit, e.g.")
    #     print("      python3 run_nfx_analysis.py --limit 508")
    #     return 1

    # out = Path(args.output_dir, "pre-analysis")
    # out.mkdir(parents=True, exist_ok=True)
    # print(f"Generating pre-analysis snapshots -> {out}/ "
    #       f"({len(repos):,} pipelines)")

    # options = {"nfcore_modules": args.nfcore_modules}
    # for name, func in PRE_PLOTS:
    #     print(f"  Plotting {name} ...")
    #     try:
    #         func(data, out, name, options)
    #     except Exception as e:
    #         print(f"    FAILED {name}: {e}")

    # # Console summary
    # from collections import Counter
    # orgs = Counter(r["full_name"].split("/")[0] for r in repos)
    # tc = [r.get("total_process_count", 0) for r in repos
    #       if r.get("total_process_count", 0) > 0]

    # module_list = ""
    # if Path(args.nfcore_modules).is_file():
    #     names = [l.strip() for l in open(args.nfcore_modules) if l.strip()]
    #     module_list = (f", {len(names):,} nf-core modules/submodules / "
    #                    f"{len({n.split('/')[0] for n in names}):,} "
    #                    f"top-level tool folders")
    # print(f"\n  Snapshot: {len(orgs)} community orgs, {len(repos):,} "
    #       f"pipelines, avg {len(repos)/len(orgs):.2f}/org, "
    #       f"{len(tc)} pipelines with processes "
    #       f"(median {sorted(tc)[len(tc)//2] if tc else 0}){module_list}")

    generate_all(
        json_path=args.json_path,
        output_dir=args.output_dir,
        font_path=args.font_path,
        nfcore_modules=nfcore_modules,
    )
