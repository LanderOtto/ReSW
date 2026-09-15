"""Fetch pipeline metadata from nf-core API."""

import json
from urllib.request import urlopen

API_URL = "https://nf-co.re/pipelines.json"


def fetch_pipelines(
    filter_keyword=None, include_archived=False, include_unreleased=False
):
    resp = urlopen(API_URL)
    data = json.loads(resp.read())
    workflows = data["remote_workflows"]

    if not include_archived:
        workflows = [wf for wf in workflows if not wf.get("archived")]

    if not include_unreleased:
        workflows = [
            wf
            for wf in workflows
            if wf.get("releases") and wf["releases"][0].get("tag_name", "") != "dev"
        ]

    if filter_keyword:
        kw = filter_keyword.lower()
        workflows = [
            wf
            for wf in workflows
            if kw in wf["name"].lower()
            or kw in (wf.get("description") or "").lower()
            or any(kw in t.lower() for t in wf.get("topics", []))
        ]

    return workflows


def extract_pipeline_tools(pipeline_data):
    releases = pipeline_data.get("releases", [])
    if not releases:
        return {"modules": [], "tools": []}

    latest = releases[0]
    comps = latest.get("components") or {}
    modules = comps.get("modules", [])
    subworkflows = comps.get("subworkflows", [])

    tools = sorted(
        set(m.split("_")[0].lower() if "_" in m else m.lower() for m in modules)
    )

    return {
        "modules": sorted(set(modules)),
        "subworkflows": sorted(set(subworkflows)),
        "tools": tools,
        # NOTE: latest.get("nextflow_version") may be null for some pipelines
        # (e.g. nf-core/demo). The "or ''" ensures we always get a string.
        # TODO: investigate why some pipeline entries lack nextflow_version in the API.
        "nextflow_version": latest.get("nextflow_version", "") or "",
        "nf_core_version": latest.get("nf_core_version", ""),
        "latest_release": latest.get("tag_name", ""),
    }


def fetch_pipeline_info(pipeline_name):
    """Fetch full pipeline metadata dict from the nf-core API.

    Returns the raw workflow dict (including 'archived', 'full_name',
    'description', 'stargazers_count', 'releases', etc.)
    or None if not found. Includes archived pipelines in the search.
    """
    workflows = fetch_pipelines(include_archived=True)
    for wf in workflows:
        if wf["full_name"] == pipeline_name:
            return wf
    return None


def fetch_pipeline_nextflow_version(pipeline_name):
    """Fetch the Nextflow version constraint for a specific pipeline.

    Returns e.g. '>=25.10.4', '24.01.0', or None if not found.
    Strips the nf-core '!' prefix (used as a formatting marker) when
    present — but preserves '!=' which is a valid PEP 440 operator.
    """
    wf = fetch_pipeline_info(pipeline_name)
    if wf is None:
        return None
    info = extract_pipeline_tools(wf)
    raw = info.get("nextflow_version", "") or ""
    raw = raw.strip()
    if raw.startswith("!") and not raw.startswith("!="):
        raw = raw[1:]
    return raw.strip() or None


def extract_all_tools(workflows):
    result = []
    for wf in workflows:
        info = extract_pipeline_tools(wf)
        result.append(
            {
                "full_name": wf["full_name"],
                "description": (wf.get("description") or "")[:120],
                "stars": wf.get("stargazers_count", 0),
                "archived": wf.get("archived", False),
                "modules": info["modules"],
                "tools": info["tools"],
                "subworkflows": info["subworkflows"],
                "nextflow_version": info["nextflow_version"],
                "latest_release": info["latest_release"],
            }
        )
    return result
