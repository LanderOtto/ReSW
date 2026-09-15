"""Shared data-loading helpers and plot style for the pre-analysis snapshot
plots. Every plot module imports its helpers and the font scale from here.
"""

import os
from collections import Counter

import matplotlib.pyplot as plt

DEFAULT_MODULES_TXT = os.path.join(".nfcore_study_cache", "nfcore_modules.txt")
CLONES_DIR = os.path.join(os.path.dirname(DEFAULT_MODULES_TXT), "clones")

ARTIFACT_TOOLS = frozenset({"modules", "software", "nf-core", "nf-cores"})


def setup_fonts():
    # Font scale: title 24, axis labels 22, ticks 20, legend 18, in-plot 16.
    plt.rcParams.update(
        {
            "font.size": 20,
            "axes.titlesize": 24,
            "axes.labelsize": 22,
            "xtick.labelsize": 20,
            "ytick.labelsize": 20,
            "legend.fontsize": 18,
            "figure.titlesize": 24,
        }
    )


setup_fonts()


def _clone_dir(full_name):
    return os.path.join(CLONES_DIR, full_name.replace("/", "__"))


def _load_modules(module_txt_path):
    if not os.path.isfile(module_txt_path):
        return []
    with open(module_txt_path) as f:
        return [ln.strip() for ln in f if ln.strip()]


def _tool_module_usage(repos, module_path=None):
    """Counter[(tool, submodule)] -> pipelines using it, from the cloned
    module trees. When the nf-core module list cache is available it is used
    as the authoritative set of module names (tool or tool/submodule), which
    excludes non-module folders such as ``tests``. A tool that ships no
    submodules is counted under ``("tool", "")``."""
    path = module_path or DEFAULT_MODULES_TXT
    authoritative = None
    if os.path.isfile(path):
        authoritative = {ln.strip().lower() for ln in _load_modules(path)}
    use = Counter()
    for r in repos:
        fn = r.get("full_name") or ""
        nfcore_dir = os.path.join(_clone_dir(fn), "modules", "nf-core")
        if not os.path.isdir(nfcore_dir):
            continue
        for base in r.get("nfcore_modules") or []:
            if "/" in base or base in ARTIFACT_TOOLS:
                continue
            mdir = os.path.join(nfcore_dir, base)
            if not os.path.isdir(mdir):
                continue
            if authoritative is not None:
                b = base.lower()
                matched = sorted(
                    s
                    for s in os.listdir(mdir)
                    if os.path.isdir(os.path.join(mdir, s))
                    and f"{b}/{s.lower()}" in authoritative
                )
                if matched:
                    for s in matched:
                        use[(base, s)] += 1
                elif b in authoritative and os.path.isfile(
                    os.path.join(mdir, "main.nf")
                ):
                    use[(base, "")] += 1
            else:
                subs = sorted(
                    x
                    for x in os.listdir(mdir)
                    if os.path.isdir(os.path.join(mdir, x))
                    and x != "tests"
                    and os.path.isfile(os.path.join(mdir, x, "main.nf"))
                )
                if subs:
                    for s in subs:
                        use[(base, s)] += 1
                elif os.path.isfile(os.path.join(mdir, "main.nf")):
                    use[(base, "")] += 1
    return use


def _tool_module_process_usage(repos, module_path):
    """Counter[(tool, submodule)] -> number of processes invoking it, counted
    from each pipeline's per-process ``nfcore_tool_evidence`` entries. Only
    (tool, submodule) names that exist in the authoritative nf-core module
    list are kept, so non-module commands (Rscript, python, ...) are
    excluded."""
    path = module_path
    authoritative = None
    if os.path.isfile(path):
        authoritative = {ln.strip().lower() for ln in _load_modules(path)}
    use = Counter()
    for r in repos:
        for e in r.get("nfcore_tool_evidence", []) or []:
            cmds = (e[6] or {}).get("tool_cmds_fullname") if len(e) > 6 else None
            if not cmds:
                continue
            for nm in cmds:
                if "/" in nm:
                    t, s = nm.split("/", 1)
                else:
                    t, s = nm, ""
                key = f"{t.lower()}/{s.lower()}" if s else t.lower()
                if authoritative is not None and key not in authoritative:
                    continue
                use[(t, s)] += 1
    return use


def _org_segments(data):
    repos = data["module_analysis"].get("repos") or []
    return sorted(
        Counter(r["full_name"].split("/")[0] for r in repos).items(),
        key=lambda kv: -kv[1],
    )


def _org_hist(data):
    """(segments, {n_pipelines: n_orgs}, max) for community organisations."""
    segments = _org_segments(data)
    if not segments:
        return None
    counts = Counter(c for _, c in segments)
    return segments, counts, max(counts)


def _org_hist_frames(counts, kmax, color_func):
    """Draw the histogram on a single full x-axis (1..kmax, empty bins
    included). Returns (fig, ax)."""
    xs = list(range(1, kmax + 1))
    ys = [counts.get(k, 0) for k in xs]
    fig, ax = plt.subplots(figsize=(11, 6.5))
    ax.bar(xs, ys, color=[color_func(k) for k in xs], edgecolor="white")
    for k, v in zip(xs, ys):
        if v:
            ax.text(k, v * 1.03, str(v), ha="center", fontsize=16)
    ax.set_xlim(0.4, kmax + 0.6)
    ax.set_xticks(xs)
    ax.set_xlabel("pipelines per organisation")
    ax.set_ylabel("number of organisations")
    return fig, ax
