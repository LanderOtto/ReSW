import json
import shutil
import subprocess
import sys
import time
from collections import Counter
from concurrent.futures import (
    FIRST_COMPLETED,
    ProcessPoolExecutor,
    ThreadPoolExecutor,
    as_completed,
    wait,
)
from pathlib import Path

from .analysis import (
    analyze_via_api,
    analyze_via_clone,
    classify_module_style,
    classify_module_subtype,
    detect_reimplementations,
)
from .api import (
    build_catalog_index,
    fetch_catalog,
    fetch_nfcore_module_list,
    fetch_nfcore_subworkflow_list,
    fetch_repo_info,
    fetch_repos,
)
from .constants import EXCLUDED_ORGS, GITHUB_TOKEN, SEARCH_QUERY, SIZE_THRESHOLD_KB
from .nfcore_tools import (
    count_nfcore_module_tools,
    count_script_interpreters,
    ensure_nfcore_module_files,
    scan_nf_files_for_nfcore_tools,
)
from .printing import print_gap_row, print_header, print_skip_summary, progress_bar

TIMEOUT_PER_REPO = 300  # 5 minutes max per repo


def _mrs_catalog(
    module_repos,
    clone_base,
    nfcore_modules,
    nfcore_base_names,
    nfcore_subworkflows,
    weights_config,
):
    print(f"\n  Repos from the catalog")

    module_results = []
    cloned_count = 0

    total = len(module_repos)
    # with ThreadPoolExecutor(max_workers=8) as exec:
    with ProcessPoolExecutor(max_workers=8) as exec:
        futs = {
            exec.submit(
                process_one_repo,
                r,
                clone_base,
                nfcore_modules,
                nfcore_base_names,
                nfcore_subworkflows,
                weights_config,
            ): r
            for r in module_repos
        }
        skip_errors = {}
        pending = set(futs.keys())
        deadline = time.time() + TIMEOUT_PER_REPO
        while pending and time.time() < deadline:
            done, pending = wait(pending, timeout=30, return_when=FIRST_COMPLETED)
            for fut in done:
                repo = futs[fut]
                try:
                    res = fut.result(timeout=0)
                    module_results.append(res)
                    if res["cloned"]:
                        cloned_count += 1
                except Exception as err:
                    err_key = str(err).split("\n")[0].strip()
                    skip_errors.setdefault(err_key, []).append(repo["full_name"])
                    module_results.append(
                        {
                            "full_name": repo["full_name"],
                            "size_mb": round(repo["size_kb"] / 1024, 1),
                            "cloned": False,
                            "in_catalog": False,
                            "pushed_at": repo.get("pushed_at", ""),
                            "nfcore_tool_exact": [],
                            "nfcore_tool_evidence": [],
                            "nfcore_subworkflow_exact": [],
                            "nfcore_subworkflow_custom": [],
                            "total_process_count": 0,
                            "module_style": "unknown",
                            "module_subtype": "unknown",
                            "skip_counter": {},
                            "parse_fail_count": 0,
                            "script_interpreters": {},
                        }
                    )
                i = len(module_results)
                progress_bar(i, total, "  Analyzing repos ")

            if pending:
                remaining = int(deadline - time.time())
                names = [futs[f]["full_name"] for f in list(pending)[:3]]
                # print(f"\n  Waiting on {len(pending)} repos"
                #       f" (timeout in {remaining}s): {', '.join(names)}{'...' if len(pending) > 3 else ''}")

        # Force-timeout any remaining stuck repos
        for fut in pending:
            repo = futs[fut]
            skip_errors.setdefault("TIMEOUT", []).append(repo["full_name"])
            module_results.append(
                {
                    "full_name": repo["full_name"],
                    "size_mb": round(repo["size_kb"] / 1024, 1),
                    "cloned": False,
                    "in_catalog": False,
                    "pushed_at": repo.get("pushed_at", ""),
                    "nfcore_tool_exact": [],
                    "nfcore_tool_evidence": [],
                    "nfcore_subworkflow_exact": [],
                    "nfcore_subworkflow_custom": [],
                    "total_process_count": 0,
                    "module_style": "unknown",
                    "module_subtype": "unknown",
                    "skip_counter": {},
                    "parse_fail_count": 0,
                    "script_interpreters": {},
                }
            )
        i = len(module_results)
        progress_bar(i, total, "  Analyzing repos ")
    return module_results


def verify_catalog_entries(catalog_full_names, gh_found):
    missing = sorted(catalog_full_names - gh_found)
    if not missing:
        return {}
    verified = {}
    with ThreadPoolExecutor(max_workers=3) as exec:
        futs = {exec.submit(fetch_repo_info, fn): fn for fn in missing}
        for i, fut in enumerate(as_completed(futs), 1):
            fn = futs[fut]
            info = fut.result()
            if info is not None:
                verified[fn] = {
                    "exists": True,
                    "language": info.get("language") or "none",
                    "archived": info.get("archived", False),
                    "pushed_at": info.get("pushed_at", ""),
                }
            else:
                verified[fn] = {"exists": False}
            progress_bar(i, len(missing), "  Verifying catalog entries ")
    return verified


# Provisional default MRS mixture weights — must match scoring.compute_mrs.
_DEFAULT_MRS_WEIGHTS = [0.30, 0.14, 0.14, 0.14, 0.14, 0.14]


def process_one_repo(
    r,
    clone_base,
    nfcore_modules,
    nfcore_base_names,
    nfcore_subworkflows=None,
    config=None,
):
    fn = r["full_name"]
    res = {
        "full_name": fn,
        "size_mb": round(r["size_kb"] / 1024, 1),
        "cloned": False,
        "pushed_at": r.get("pushed_at", ""),
        "in_catalog": False,
    }
    cd = clone_base / fn.replace("/", "__")
    if cd.is_dir():
        res["cloned"] = True
        mod_info = analyze_via_clone(cd)
        try:
            r2 = subprocess.run(
                ["git", "log", "-1", "--format=%aI"],
                capture_output=True,
                text=True,
                timeout=30,
                cwd=str(cd),
            )
            if r2.returncode == 0:
                res["last_commit"] = r2.stdout.strip()
        except Exception:
            pass
    elif 0 < r["size_kb"] < SIZE_THRESHOLD_KB:
        try:
            subprocess.run(
                [
                    "git",
                    "clone",
                    "--depth",
                    "1",
                    f"https://github.com/{fn}.git",
                    str(cd),
                ],
                capture_output=True,
                text=True,
                timeout=120,
                check=True,
            )
            res["cloned"] = True
            mod_info = analyze_via_clone(cd)
        except Exception:
            mod_info = analyze_via_api(fn)
        if res["cloned"]:
            try:
                r2 = subprocess.run(
                    ["git", "log", "-1", "--format=%aI"],
                    capture_output=True,
                    text=True,
                    timeout=30,
                    cwd=str(cd),
                )
                if r2.returncode == 0:
                    res["last_commit"] = r2.stdout.strip()
            except Exception:
                pass
    else:
        mod_info = analyze_via_api(fn)
    res.update(mod_info)
    res["uses_nfcore"] = res["has_modules_json"] or res["has_nfcore_dir"]
    res["has_local"] = res["has_local_dir"]

    res["module_style"] = classify_module_style(res)
    res["module_subtype"] = classify_module_subtype(res, fn, clone_base)

    if "last_commit" not in res and res.get("pushed_at"):
        res["last_commit"] = res["pushed_at"]

    reimp = detect_reimplementations(res, nfcore_modules, nfcore_subworkflows)
    res["reimplemented_modules"] = sorted(reimp)
    res["reimplemented_count"] = len(reimp)

    if res.get("module_subtype") == "local_only":
        res["module_subtype"] = "local_reimpl" if reimp else "local_custom"
    elif res.get("module_subtype") == "custom_only":
        res["module_subtype"] = "custom_reimpl" if reimp else "custom_nocore"

    if res.get("cloned"):
        result = scan_nf_files_for_nfcore_tools(
            cd, nfcore_modules, nfcore_base_names, nfcore_subworkflows, config=config
        )
        (
            exact,
            evidence,
            infra_only_entries,
            exact_sw,
            custom_sw,
            total_process_count,
            skip_counter,
            parse_fail_count,
            script_interpreters,
        ) = result
        res["nfcore_tool_exact"] = exact
        res["nfcore_tool_derivatives"] = []
        res["nfcore_tool_evidence"] = evidence
        res["nfcore_tool_infra_only"] = infra_only_entries
        res["nfcore_subworkflow_exact"] = exact_sw
        res["nfcore_subworkflow_custom"] = custom_sw
        res["total_process_count"] = total_process_count
        res["skip_counter"] = skip_counter
        res["parse_fail_count"] = parse_fail_count
        res["script_interpreters"] = script_interpreters
    else:
        res["nfcore_tool_exact"] = []
        res["nfcore_tool_derivatives"] = []
        res["nfcore_tool_evidence"] = []
        res["nfcore_tool_infra_only"] = []
        res["total_process_count"] = 0
        res["nfcore_subworkflow_exact"] = []
        res["nfcore_subworkflow_custom"] = []
        res["script_interpreters"] = {}

    return res


def _load_mrs_weights(path):
    """Load and validate an MRS mixture weight vector from a JSON file.

    Accepts either the calibration output (`best_config.config.weights`) or a
    plain `{"weights": [...]}`. Returns ``{"weights": [...]}`` ready to pass
    into ``scan_nf_files_for_nfcore_tools(config=...)``. Raises ``SystemExit``
    on any malformed input (hard error).
    """
    import math

    p = Path(path)
    if not p.is_file():
        sys.exit(f"--weights: file not found: {p}")
    try:
        data = json.loads(p.read_text())
    except (json.JSONDecodeError, UnicodeDecodeError) as e:
        sys.exit(f"--weights: invalid JSON in {p}: {e}")

    weights = data.get("weights") if isinstance(data, dict) else None
    if weights is None:
        best = (data or {}).get("best_config", {}).get("config", {})
        weights = best.get("weights")
    if not isinstance(weights, list) or not weights:
        sys.exit(
            f"--weights: no weight vector found in {p} "
            "(expected 'weights' or 'best_config.config.weights')"
        )

    n_default = len(_DEFAULT_MRS_WEIGHTS)
    if len(weights) != n_default:
        sys.exit(f"--weights: expected {n_default} weights, got {len(weights)}")
    for i, v in enumerate(weights):
        if not isinstance(v, (int, float)) or isinstance(v, bool):
            sys.exit(f"--weights: weight {i} is not a number: {v!r}")
        if not 0.0 <= float(v) <= 1.0:
            sys.exit(f"--weights: weight {i} = {v} out of range [0, 1]")
    total = sum(float(v) for v in weights)
    if abs(total - 1.0) > 1e-6:
        sys.exit(f"--weights: weights sum to {total}, expected 1.0")

    return {"weights": [float(v) for v in weights]}


def main(args):
    weights_config = _load_mrs_weights(args.weights) if args.weights else None
    if weights_config:
        print(
            f"MRS weights: {weights_config['weights']} "
            f"(from --weights {args.weights})"
        )

    if not GITHUB_TOKEN:
        print(
            "Warning: GITHUB_TOKEN not set — rate limits will be very restrictive.",
            file=sys.stderr,
        )

    cache_root = Path(args.cache_dir)
    api_cache = cache_root / "api"
    clone_base = cache_root / "clones"

    api_cache.mkdir(parents=True, exist_ok=True)
    ttl = args.cache_ttl * 60
    force = args.no_cache

    # ---------------------------------------------------------------
    # 1. Catalog
    # ---------------------------------------------------------------
    print("\nFetching nf-co.re catalog ...")
    catalog_workflows = fetch_catalog()
    catalog_full_names, catalog_org_counts = build_catalog_index(catalog_workflows)
    catalog_data = []
    for wf in catalog_workflows:
        fn = wf["full_name"]
        catalog_data.append(
            {
                "full_name": fn,
                "owner": fn.split("/")[0],
                "name": fn.split("/")[1],
                "size_kb": wf.get("size_kb", 0),
                "url": f"https://github.com/{fn}",
                "pushed_at": wf.get("pushed_at", ""),
                "in_catalog": True,
            }
        )
    total_catalog = len(catalog_workflows)
    total_catalog_orgs = len(catalog_org_counts)
    sorted_catalog_orgs = sorted(catalog_org_counts.items(), key=lambda x: -x[1])

    cat_group = {"nf-core": 0, "seqeralabs": 0, "nextflow-io": 0, "other": 0}
    for org, cnt in sorted_catalog_orgs:
        if org in EXCLUDED_ORGS:
            cat_group[org] = cnt
        else:
            cat_group["other"] += cnt
    other_cat_orgs_n = sum(1 for o in catalog_org_counts if o not in EXCLUDED_ORGS)

    print(f"  Catalog pipelines: {total_catalog}")
    print(f"  Organizations:     {total_catalog_orgs}")

    # ---------------------------------------------------------------
    # 1b. nf-core module & subworkflow lists
    # ---------------------------------------------------------------
    print("\nFetching nf-core/modules tree ...")
    nfcore_modules = fetch_nfcore_module_list(api_cache, ttl, force)
    print(f"  Found {len(nfcore_modules)} nf-core module names")

    nfcore_cache = cache_root / "nfcore_modules.txt"
    all_names = set(nfcore_modules)
    for name in nfcore_modules:
        if "/" in name:
            all_names.add(name.split("/")[0])
    nfcore_cache.write_text("\n".join(sorted(all_names)) + "\n")

    nfcore_subworkflows = fetch_nfcore_subworkflow_list(api_cache, ttl, force)
    print(f"  Found {len(nfcore_subworkflows)} nf-core subworkflow names\n")

    nfcore_base_names = sorted({m.split("/")[0] for m in nfcore_modules})

    # ---------------------------------------------------------------
    # 2. GitHub repos
    # ---------------------------------------------------------------
    print("Fetching GitHub repos ...")
    t0 = time.time()
    all_repos = fetch_repos(catalog_full_names, api_cache, ttl, force)
    gh_found = {r["full_name"] for r in all_repos}
    print(
        f"  Found {len(all_repos)} org-owned repos "
        f"(search: {SEARCH_QUERY}) in {time.time() - t0:.1f}s"
    )

    not_in_search = catalog_full_names - gh_found
    if not_in_search:
        print(
            f"\n  Catalog entries not in search results ({len(not_in_search)})"
            " — checking directly ..."
        )
        verified = verify_catalog_entries(catalog_full_names, gh_found)
        for fn, info in verified.items():
            if info["exists"]:
                print(
                    f"    {fn}: exists (lang={info['language']},"
                    f" archived={info['archived']})"
                )
                all_repos.append(
                    {
                        "full_name": fn,
                        "owner": fn.split("/")[0],
                        "name": fn.split("/")[1],
                        "size_kb": 0,
                        "url": f"https://github.com/{fn}",
                        "pushed_at": info.get("pushed_at", ""),
                        "in_catalog": True,
                    }
                )
            else:
                print(f"    {fn}: NOT FOUND on GitHub")

    # ---------------------------------------------------------------
    # 3. Catalog summary
    # ---------------------------------------------------------------
    print_header("1. nf-co.re Catalog Summary")
    print(f"  Total pipelines in catalog:   {total_catalog}")
    print(f"  Total organizations:          {total_catalog_orgs}\n")
    print(f"  {'Organization':<28} {'Pipelines':>10}")
    print(f"  {'-' * 28} {'-' * 10}")
    for org, cnt in sorted_catalog_orgs:
        print(f"  {org:<28} {cnt:>10}")
    print("\n  By group:")
    for group in ["nf-core", "seqeralabs", "nextflow-io", "other"]:
        if group == "other":
            print(
                f"    {group:<28} {other_cat_orgs_n:>3} orgs,"
                f" {cat_group['other']:>4} pipelines"
            )
        else:
            print(
                f"    {group:<28}"
                f" {'1' if cat_group[group] > 0 else '0':>3} org,"
                f" {cat_group[group]:>4} pipelines"
            )

    # ---------------------------------------------------------------
    # 4. Gap analysis
    # ---------------------------------------------------------------
    print_header("2. Cross-Reference: GitHub \u2194 Catalog")
    print(f"  ('{SEARCH_QUERY.replace('+', ' ')}' on GitHub)")
    print(
        f"  {'Organization':<28} {'GitHub':>6}  {'In catalog':>11}"
        f"  {'Not in catalog':>14}"
    )
    print(f"  {'-' * 28} {'-' * 6}  {'-' * 11}  {'-' * 14}")

    for org in sorted(EXCLUDED_ORGS):
        org_repos = [r for r in all_repos if r["owner"] == org]
        if org_repos:
            print_gap_row(org, org_repos)

    other_cat = [
        r for r in all_repos if r["owner"] not in EXCLUDED_ORGS and r["in_catalog"]
    ]
    other_cat_orgs_set = set(r["owner"] for r in other_cat)
    if other_cat:
        print_gap_row(f"Other catalog ({len(other_cat_orgs_set)} orgs)", other_cat)

    other_miss = [
        r for r in all_repos if r["owner"] not in EXCLUDED_ORGS and not r["in_catalog"]
    ]
    other_miss_orgs = set(r["owner"] for r in other_miss)
    if other_miss:
        print_gap_row(f"Other uncatalogued ({len(other_miss_orgs)} orgs)", other_miss)

    mrs_catalog_results = _mrs_catalog(
        catalog_data,
        clone_base,
        nfcore_modules,
        nfcore_base_names,
        nfcore_subworkflows,
        weights_config,
    )

    # ---------------------------------------------------------------
    # 5. Module analysis
    # ---------------------------------------------------------------
    comm_interp = {}
    nfcore_interp = {}
    module_tools = {}
    if args.limit <= 0:
        print("\n  Skipping module analysis (pass --limit N to enable).")
        module_results = []
    else:
        clone_base.mkdir(parents=True, exist_ok=True)
        module_repos = [
            r
            for r in all_repos
            if r["owner"] not in EXCLUDED_ORGS and not r["in_catalog"]
        ]
        print(
            f"\n  Repos eligible for module analysis: {len(module_repos)}"
            f"\n  (excluded orgs + catalog repos filtered out)"
            f"\n  Analyzing {min(len(module_repos), args.limit)} repos"
            f" (--limit={args.limit})"
        )

        module_repos = module_repos[: args.limit]
        module_results = []
        cloned_count = 0

        total = len(module_repos)
        # with ThreadPoolExecutor(max_workers=8) as exec:
        with ProcessPoolExecutor(max_workers=8) as exec:
            futs = {
                exec.submit(
                    process_one_repo,
                    r,
                    clone_base,
                    nfcore_modules,
                    nfcore_base_names,
                    nfcore_subworkflows,
                    weights_config,
                ): r
                for r in module_repos
            }
            skip_errors = {}
            pending = set(futs.keys())
            deadline = time.time() + TIMEOUT_PER_REPO
            while pending and time.time() < deadline:
                done, pending = wait(pending, timeout=30, return_when=FIRST_COMPLETED)
                for fut in done:
                    repo = futs[fut]
                    try:
                        res = fut.result(timeout=0)
                        module_results.append(res)
                        if res["cloned"]:
                            cloned_count += 1
                    except Exception as err:
                        err_key = str(err).split("\n")[0].strip()
                        skip_errors.setdefault(err_key, []).append(repo["full_name"])
                        module_results.append(
                            {
                                "full_name": repo["full_name"],
                                "size_mb": round(repo["size_kb"] / 1024, 1),
                                "cloned": False,
                                "in_catalog": False,
                                "pushed_at": repo.get("pushed_at", ""),
                                "nfcore_tool_exact": [],
                                "nfcore_tool_evidence": [],
                                "nfcore_subworkflow_exact": [],
                                "nfcore_subworkflow_custom": [],
                                "total_process_count": 0,
                                "module_style": "unknown",
                                "module_subtype": "unknown",
                                "skip_counter": {},
                                "parse_fail_count": 0,
                                "script_interpreters": {},
                            }
                        )
                    i = len(module_results)
                    progress_bar(i, total, "  Analyzing repos ")

                if pending:
                    remaining = int(deadline - time.time())
                    names = [futs[f]["full_name"] for f in list(pending)[:3]]
                    # print(f"\n  Waiting on {len(pending)} repos"
                    #       f" (timeout in {remaining}s): {', '.join(names)}{'...' if len(pending) > 3 else ''}")

            # Force-timeout any remaining stuck repos
            for fut in pending:
                repo = futs[fut]
                skip_errors.setdefault("TIMEOUT", []).append(repo["full_name"])
                module_results.append(
                    {
                        "full_name": repo["full_name"],
                        "size_mb": round(repo["size_kb"] / 1024, 1),
                        "cloned": False,
                        "in_catalog": False,
                        "pushed_at": repo.get("pushed_at", ""),
                        "nfcore_tool_exact": [],
                        "nfcore_tool_evidence": [],
                        "nfcore_subworkflow_exact": [],
                        "nfcore_subworkflow_custom": [],
                        "total_process_count": 0,
                        "module_style": "unknown",
                        "module_subtype": "unknown",
                        "skip_counter": {},
                        "parse_fail_count": 0,
                        "script_interpreters": {},
                    }
                )
            i = len(module_results)
            progress_bar(i, total, "  Analyzing repos ")

        # --- Aggregate skip summary ---
        agg_skip = {}
        total_parse_fail = 0
        for r in module_results:
            for k, v in r.get("skip_counter", {}).items():
                agg_skip[k] = agg_skip.get(k, 0) + v
            total_parse_fail += r.get("parse_fail_count", 0)
        if sum(agg_skip.values()) or total_parse_fail:
            print_skip_summary(agg_skip, parse_fail_count=total_parse_fail)

        if skip_errors:
            total_skipped = sum(len(v) for v in skip_errors.values())
            print(f"\n  Skipped repos ({total_skipped} total):")
            for err_msg, pipelines in sorted(
                skip_errors.items(), key=lambda x: -len(x[1])
            ):
                print(f" - ERROR:\t`{err_msg}`")
                print(f"\t- Pipelines: {pipelines}")
        else:
            print(f"\n  Zero skipped repos (no errors)")

        # --- Summary metrics ---
        t = len(module_results)
        c = cloned_count
        has_entry = sum(1 for r in module_results if r.get("entrypoint"))
        has_cfg = sum(1 for r in module_results if r.get("has_nextflow_config"))
        has_main = sum(1 for r in module_results if r.get("has_main_nf"))

        dir_styles = {}
        for r in module_results:
            s = r.get("module_style", "unknown")
            dir_styles[s] = dir_styles.get(s, 0) + 1

        nfcore_via_dir = sum(1 for r in module_results if r.get("has_nfcore_dir"))
        nfcore_via_json_only = sum(
            1
            for r in module_results
            if r.get("has_modules_json") and not r.get("has_nfcore_dir")
        )
        nfcore_total = nfcore_via_dir + nfcore_via_json_only
        local_via_dir = sum(1 for r in module_results if r.get("has_local_dir"))
        no_modules_total = sum(
            1
            for r in module_results
            if not r.get("modules_dir_contents") and not r.get("has_modules_json")
        )

        nfcore_subtype_map = {
            "nfcore_declared",
            "nfcore_direct",
            "nfcore_include",
            "nfcore_submodule",
            "nfcore_only",
        }

        # ------ Section 3: Directory Structure ------
        print_header("3. Module Directory Structure")
        print(f"  Total repos analyzed:        {t}")
        if t:
            print(f"  Cloned (< 50 MB):            {c} ({c / t * 100:.0f}%)")
            print(
                f"  Has nextflow.config:         {has_cfg} ({has_cfg / t * 100:.0f}%)"
            )
            print(
                f"  Has main.nf:                 {has_main} ({has_main / t * 100:.0f}%)"
            )
            print(
                f"  Has entrypoint (pipeline):   {has_entry} ({has_entry / t * 100:.0f}%)"
            )
            no_entry = t - has_entry
            if no_entry:
                no_entry_cfg = sum(
                    1
                    for r in module_results
                    if not r.get("entrypoint") and r.get("has_nextflow_config")
                )
                no_entry_none = no_entry - no_entry_cfg
                print(
                    f"  No entrypoint:               {no_entry} ({no_entry / t * 100:.0f}%)"
                    f"  (has config: {no_entry_cfg}, no config: {no_entry_none})"
                )
            print(f"  Directory style:")
            for st in [
                "nf-core",
                "nf-core+local",
                "nf-core+other",
                "local",
                "local+other",
                "nf-core+local+other",
                "custom",
                "no_modules",
            ]:
                sc = dir_styles.get(st, 0)
                if sc:
                    print(f"    {st:<20} {sc:>4} ({sc / t * 100:.0f}%)")

            # -- Module subtype breakdown by style --
            sub_breakdown_styles = ["no_modules", "local", "local+other", "custom"]
            for ss in sub_breakdown_styles:
                group = [r for r in module_results if r.get("module_style") == ss]
                if not group:
                    continue
                sub_counts = {}
                for r in group:
                    st = r.get("module_subtype", "unknown")
                    sub_counts[st] = sub_counts.get(st, 0) + 1
                print(f"  {ss} breakdown:")
                order = (
                    [
                        "nfcore_declared",
                        "nfcore_include",
                        "nfcore_submodule",
                        "flat_modules_dir",
                        "has_include_modules",
                        "has_module_subdirs",
                        "has_submodules",
                        "config_only",
                        "entrypoint_only",
                        "local_reimpl",
                        "local_custom",
                        "custom_reimpl",
                        "custom_nocore",
                        "truly_empty",
                        "unknown",
                    ]
                    if ss == "no_modules"
                    else [
                        "nfcore_declared",
                        "nfcore_include",
                        "nfcore_submodule",
                        "local_reimpl",
                        "local_custom",
                        "custom_reimpl",
                        "custom_nocore",
                        "truly_empty",
                        "unknown",
                    ]
                )
                for st0 in order:
                    sc = sub_counts.get(st0, 0)
                    if sc:
                        print(f"    {st0:<20} {sc:>4} ({sc / t * 100:.0f}%)")

            # -- Last commit year for nf-core-independent repos --
            nf_indep = [
                r
                for r in module_results
                if not r.get("has_modules_json")
                and not r.get("has_nfcore_dir")
                and r.get("module_subtype", "") not in nfcore_subtype_map
            ]
            if nf_indep:
                year_counts = {}
                no_date = 0
                for r in nf_indep:
                    lc = r.get("last_commit", "")
                    yr = lc[:4] if len(lc) >= 4 else ""
                    if yr:
                        year_counts[yr] = year_counts.get(yr, 0) + 1
                    else:
                        no_date += 1
                print(
                    f"  Last commit year for nf-core-independent repos"
                    f" ({len(nf_indep)} total):"
                )
                for yr in sorted(year_counts):
                    print(
                        f"    {yr}: {year_counts[yr]:>4}"
                        f" ({year_counts[yr] / len(nf_indep) * 100:.0f}%)"
                    )
                if no_date:
                    print(
                        f"    no date: {no_date:>4}"
                        f" ({no_date / len(nf_indep) * 100:.0f}%)"
                    )

            # -- nf-core engagement level --
            if nf_indep:
                aware = [
                    r
                    for r in nf_indep
                    if r.get("reimplemented_count", 0) > 0
                    or r.get("module_subtype")
                    in (
                        "nfcore_declared",
                        "nfcore_include",
                        "nfcore_submodule",
                        "local_reimpl",
                        "custom_reimpl",
                    )
                ]
                unaware = [r for r in nf_indep if r not in aware]
                print(f"  nf-core engagement ({len(nf_indep)} independent repos):")
                print(
                    f"    aware (re-impl, modules.json, nf-core includes):"
                    f" {len(aware):>4} ({len(aware) / len(nf_indep) * 100:.0f}%)"
                )
                print(
                    f"    unaware (no evidence of nf-core knowledge):"
                    f" {len(unaware):>4} ({len(unaware) / len(nf_indep) * 100:.0f}%)"
                )
                if aware:
                    print(f"    aware breakdown:")
                    aware_sub = {}
                    for r in aware:
                        st = r.get("module_subtype", "unknown")
                        aware_sub[st] = aware_sub.get(st, 0) + 1
                    for st0 in sorted(aware_sub, key=lambda x: -aware_sub[x]):
                        print(f"      {st0:<20} {aware_sub[st0]:>4}")

            # -- nf-core subworkflow usage --
            if nf_indep:
                sw_counter = {}
                repos_with_sw = 0
                repos_with_custom_sw = 0
                for r in nf_indep:
                    exact_sw = r.get("nfcore_subworkflow_exact", [])
                    custom_sw = r.get("nfcore_subworkflow_custom", [])
                    if exact_sw:
                        repos_with_sw += 1
                        for sw in exact_sw:
                            sw_counter[sw] = sw_counter.get(sw, 0) + 1
                    if custom_sw:
                        repos_with_custom_sw += 1
                        for sw in custom_sw:
                            sw_counter[sw] = sw_counter.get(sw, 0) - 1
                if repos_with_sw or repos_with_custom_sw:
                    print(f"  nf-core subworkflow usage:")
                    print(f"    repos using nf-core subworkflows:  {repos_with_sw:>4}")
                    print(
                        f"    repos with custom subworkflows:    {repos_with_custom_sw:>4}"
                    )
                    top_sw = sorted(sw_counter.items(), key=lambda x: -abs(x[1]))[:10]
                    if top_sw:
                        print(f"    Top subworkflows:")
                        for sw, cnt in top_sw:
                            label = "exact" if cnt > 0 else "custom"
                            print(f"      {sw:<45} {abs(cnt):>4} repos ({label})")
                print()

            # -- nf-core tool reuse opportunities --
            if nf_indep:
                indep_cloned = sum(1 for r in nf_indep if r.get("cloned"))
                tool_counter = {}
                tool_examples = {}
                repos_with_reuse = 0
                for r in nf_indep:
                    exact = r.get("nfcore_tool_exact", [])
                    if exact:
                        repos_with_reuse += 1
                        for tn in exact:
                            tool_counter[tn] = tool_counter.get(tn, 0) + 1
                            if tn not in tool_examples:
                                ev = r.get("nfcore_tool_evidence", [])
                                for e in ev:
                                    if e[3] == tn and e[4] == "exact":
                                        tool_examples[tn] = (
                                            r["full_name"],
                                            e[0],
                                            e[1],
                                            e[2],
                                            e[5],
                                        )
                                        break
                repos_no_reuse = len(nf_indep) - repos_with_reuse
                print(
                    f"  nf-core tool reuse opportunities"
                    f" (scanned {indep_cloned}/{len(nf_indep)} cloned repos):"
                )
                print(
                    f"    reference nf-core tool names: {repos_with_reuse:>4}"
                    f" ({repos_with_reuse / len(nf_indep) * 100:.0f}%)"
                )
                print(
                    f"    no nf-core tool name overlap: {repos_no_reuse:>4}"
                    f" ({repos_no_reuse / len(nf_indep) * 100:.0f}%)"
                )
                if tool_counter:
                    top_tools = sorted(tool_counter.items(), key=lambda x: -x[1])[:15]
                    print(f"    Top referenced nf-core tools with reuse scores:")
                    for tname, cnt in top_tools:
                        ex = tool_examples.get(tname)
                        if ex:
                            repo, fpath, lineno, content, score = ex
                            print(
                                f"      {tname:<25} {cnt:>4} repos  score={score:.2f}"
                                f"  e.g. {repo:<40} {fpath}:{lineno}"
                            )
                            print(f"      {'':<25} {'':>4}              {content}")
                        else:
                            print(f"      {tname:<25} {cnt:>4} repos  score=?")

                # -- Reuse score distribution --
                all_scores = []
                for r in nf_indep:
                    for e in r.get("nfcore_tool_evidence", []):
                        score = e[5]
                        if e[4] == "exact" and score is not None:
                            all_scores.append(score)
                if all_scores:
                    high = sum(1 for s in all_scores if s >= 0.7)
                    mid = sum(1 for s in all_scores if 0.4 <= s < 0.7)
                    low = sum(1 for s in all_scores if s < 0.4)
                    print(
                        f"  Reuse score distribution ({len(all_scores)} exact matches):"
                    )
                    print(
                        f"    \u2265 0.7 \u2014 likely drop-in:      {high:>4}"
                        f" ({high / len(all_scores) * 100:.0f}%)"
                    )
                    print(
                        f"    0.4\u20130.7 \u2014 needs refactoring: {mid:>4}"
                        f" ({mid / len(all_scores) * 100:.0f}%)"
                    )
                    print(
                        f"    < 0.4 \u2014 heavily custom:       {low:>4}"
                        f" ({low / len(all_scores) * 100:.0f}%)"
                    )

        # ------ Section 4: Module Declaration ------
        print_header("4. Module Declaration (with modules.json)")
        if t:
            print(
                f"  Uses nf-core modules:        {nfcore_total:>4}"
                f" ({nfcore_total / t * 100:.0f}%)"
            )
            print(f"    Via modules/nf-core/ dir:   {nfcore_via_dir:>4}")
            print(f"    Via modules.json only:      {nfcore_via_json_only:>4}")
            print(
                f"  Has local modules (dir):     {local_via_dir:>4}"
                f" ({local_via_dir / t * 100:.0f}%)"
            )
            print(
                f"  No modules at all:           {no_modules_total:>4}"
                f" ({no_modules_total / t * 100:.0f}%)"
            )

        # ------ Section 5: Re-implementation ------
        reimp_repos = [r for r in module_results if r.get("reimplemented_count", 0) > 0]
        total_reimp = sum(r.get("reimplemented_count", 0) for r in module_results)
        reimp_counter = {}
        for r in reimp_repos:
            for m in r.get("reimplemented_modules", []):
                reimp_counter[m] = reimp_counter.get(m, 0) + 1
        top_reimp = sorted(reimp_counter.items(), key=lambda x: -x[1])[:10]

        print_header("5. Re-implementation Analysis")
        reimp_pct = f" ({len(reimp_repos) / t * 100:.0f}%)" if t else ""
        print(f"  Repos with re-implementations:   {len(reimp_repos)}{reimp_pct}")
        print(f"  Total re-implemented modules:    {total_reimp}")
        if top_reimp:
            print(f"\n  Top re-implemented nf-core modules:")
            for mod, cnt in top_reimp:
                print(f"    {mod:<30} {cnt:>4} times")

        # ------ Section 5b: Process Script Interpreters ------
        comm_interp = Counter()
        for repo in module_results:
            comm_interp.update(repo.get("script_interpreters") or {})

        nfcore_interp = Counter()
        nfcore_repos = [r for r in all_repos if r.get("owner") == "nf-core"]
        for repo in nfcore_repos:
            cd = clone_base / repo["full_name"].replace("/", "__")
            if not cd.is_dir():
                continue
            try:
                nfcore_interp.update(count_script_interpreters(cd, nfcore_subworkflows))
            except Exception:
                continue

        def _print_interp_table(title, counter):
            total = sum(counter.values())
            print(f"  {title} ({total} parsed blocks)")
            if total:
                print(f"    {'interpreter':<14}{'count':>8}")
                for name, cnt in counter.most_common():
                    print(f"    {name:<14}{cnt:>8}")
            else:
                print("    (none)")

        print_header("6. Script Interpreters")
        _print_interp_table("Community", comm_interp)
        _print_interp_table("nf-core", nfcore_interp)

        # ------ Section 7: nf-core Module Tools ------
        module_tools = {}
        try:
            module_tools_dir = cache_root / "nfcore_modules_content"
            if not module_tools_dir.is_dir() or not any(module_tools_dir.glob("*.nf")):
                ensure_nfcore_module_files(module_tools_dir, nfcore_modules)
            module_tools = count_nfcore_module_tools(module_tools_dir)
        except Exception as e:
            print(f"  Warning: nf-core module tool count failed: {e}")

        print_header("7. nf-core Module Tools")
        if not module_tools or not module_tools.get("modules_total"):
            print("  (no nf-core module files found)")
        else:
            mt = module_tools
            print(f"  Modules analyzed:             {mt['modules_total']}")
            print(
                f"  Modules declaring tools:      {mt['with_declared_tools']}"
                f" ({mt['with_declared_tools'] / mt['modules_total'] * 100:.0f}%)"
            )
            print(f"  Parse failures:               {mt['parse_fail']}")
            dist = mt["by_n_declared"]
            if dist:
                print(f"\n  Declared tools per module:")
                print(f"    {'# tools':<10}{'modules':>8}")
                for n, cnt in sorted(dist.items()):
                    print(f"    {n:<10}{cnt:>8}")
            top = mt["top_declared_tools"]
            if top:
                print(f"\n  Top declared tools in nf-core modules:")
                print(f"    {'tool':<20}{'modules':>8}")
                for tool, cnt in top[:15]:
                    print(f"    {tool:<20}{cnt:>8}")
            multi = mt["multi_tool_modules"]
            if multi:
                print(f"\n  Multi-tool modules ({len(multi)}):")
                for mname, tools in list(multi.items())[:10]:
                    print(f"    {mname:<28}{', '.join(tools)}")
            disc = mt["discrepancies"]
            if disc:
                print(f"\n  Declared vs script discrepancies ({len(disc)}):")
                for mname, rec in list(disc.items())[:10]:
                    print(
                        f"    {mname:<28}declared={rec['declared']} "
                        f"script={rec['script']}"
                    )

    scores = []
    for c in mrs_catalog_results:
        for n in c["nfcore_tool_evidence"]:
            scores.append((n[5], c))

    print("Catalog analysis:\n\t- Number of processes", len(scores))
    print("\t- Number of ones", sum(1 for s in scores if s[0] == 1))
    print("\t- Number of zeros", sum(1 for s in scores if s[0] == 0))

    def terminal_histogram(data, num_bins=10, max_bar_width=50):
        if not data:
            return

        min_val, max_val = min(data), max(data)
        # Prevent division by zero if all values are identical
        bin_width = (max_val - min_val) / num_bins if max_val > min_val else 1

        counts = [0] * num_bins
        for value in data:
            # Place value in the correct bin, clamping the maximum value to the last bin
            bin_index = min(int((value - min_val) / bin_width), num_bins - 1)
            counts[bin_index] += 1

        max_count = max(counts)

        for i in range(num_bins):
            bin_start = min_val + i * bin_width
            bin_end = bin_start + bin_width

            # Scale bar length relative to the most populated bin
            bar_len = (
                int((counts[i] / max_count) * max_bar_width) if max_count > 0 else 0
            )
            bar = "█" * bar_len

            print(f"[{bin_start:.2f} - {bin_end:.2f}) | {bar} ({counts[i]})")

    terminal_histogram([s[0] for s in scores], num_bins=10)

    # ---------------------------------------------------------------
    # 6. Save JSON
    # ---------------------------------------------------------------
    eligible = (
        sum(
            1
            for r in all_repos
            if r["owner"] not in EXCLUDED_ORGS and not r["in_catalog"]
        )
        if all_repos
        else 0
    )

    output = {
        "query": SEARCH_QUERY,
        "catalog": {
            "total_pipelines": total_catalog,
            "total_organizations": total_catalog_orgs,
            "by_org": dict(sorted_catalog_orgs),
            "by_group": cat_group,
            "other_catalog_orgs_count": other_cat_orgs_n,
        },
        "cross_reference": {
            "total_github_repos": len(all_repos),
            "total_github_orgs": len(set(r["owner"] for r in all_repos)),
        },
        "module_analysis": {
            "eligible_repos": eligible,
            "analyzed": len(module_results),
            "cloned": sum(1 for r in module_results if r.get("cloned")),
            "uses_nfcore": sum(1 for r in module_results if r.get("uses_nfcore")),
            "has_local": sum(1 for r in module_results if r.get("has_local")),
            "hybrid": sum(
                1 for r in module_results if r.get("uses_nfcore") and r.get("has_local")
            ),
            "neither": sum(
                1
                for r in module_results
                if not r.get("uses_nfcore") and not r.get("has_local")
            ),
            "mrs_weights": (weights_config["weights"] if weights_config else None),
            "mrs_weights_source": args.weights or "default",
            "script_interpreters": {
                "community": dict(comm_interp),
                "nfcore": dict(nfcore_interp),
            },
            "nfcore_module_tools": module_tools,
            "repos": module_results,
        },
        "mrs_catalog_results": mrs_catalog_results,
    }
    with open(args.json, "w") as f:
        json.dump(output, f, indent=2)
    print(f"\nSaved to {args.json}")
