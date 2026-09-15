import hashlib
import json
import math
import sys
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from .constants import (
    CATALOG_URL,
    GITHUB_TOKEN,
    MAX_PAGES,
    NF_CORE_MODULES_TREE,
    PER_PAGE,
    SEARCH_QUERY,
    SEARCH_URL,
)
from .printing import progress_bar


def api_get(url):
    headers = {"Accept": "application/vnd.github.v3+json"}
    if GITHUB_TOKEN:
        headers["Authorization"] = f"Bearer {GITHUB_TOKEN}"

    for attempt in range(3):
        req = urllib.request.Request(url, headers=headers)
        try:
            with urllib.request.urlopen(req) as resp:
                body = json.loads(resp.read())
                remaining = int(resp.headers.get("X-RateLimit-Remaining", 0))
                return body, remaining
        except urllib.error.HTTPError as e:
            if e.code == 401 or "unauthorized" in str(e).lower():
                print(
                    "Error 401 Unauthorized: Please set the GITHUB_TOKEN environment variable."
                )
                print("Run in terminal: export GITHUB_TOKEN='your_github_token'")
            if e.code == 403 and attempt < 2:
                reset_ts = int(e.headers.get("X-RateLimit-Reset", 0))
                sleep = max(reset_ts - time.time(), 0) + 2
                print(f"  Rate limited — sleeping {sleep:.0f}s ...", file=sys.stderr)
                time.sleep(sleep)
                continue
            raise
    raise Exception(f"Failed after retries: {url}")


def cached_api_get(url, cache_dir, ttl_seconds, force=False):
    cache_dir.mkdir(parents=True, exist_ok=True)
    key = hashlib.md5(url.encode()).hexdigest()
    cache_path = cache_dir / key

    if not force and cache_path.exists():
        age = time.time() - cache_path.stat().st_mtime
        if age < ttl_seconds:
            return json.loads(cache_path.read_text())

    data, _ = api_get(url)
    cache_path.write_text(json.dumps(data))
    return data


def fetch_catalog():
    with urllib.request.urlopen(CATALOG_URL) as resp:
        return json.loads(resp.read())["remote_workflows"]


def build_catalog_index(workflows):
    full_names = set()
    org_counts = {}
    for wf in workflows:
        fn = wf["full_name"]
        full_names.add(fn)
        org = fn.split("/")[0]
        org_counts[org] = org_counts.get(org, 0) + 1
    return full_names, org_counts


def fetch_nfcore_module_list(cache_dir, ttl_seconds, force=False):
    import re

    data = cached_api_get(NF_CORE_MODULES_TREE, cache_dir, ttl_seconds, force)
    names = set()
    for entry in data.get("tree", []):
        m = re.match(r"modules/nf-core/(.+)/main\.nf", entry["path"])
        if m and "/tests" not in m.group(1):
            names.add(m.group(1))
    return sorted(names)


def fetch_nfcore_subworkflow_list(cache_dir, ttl_seconds, force=False):
    import re

    data = cached_api_get(NF_CORE_MODULES_TREE, cache_dir, ttl_seconds, force)
    names = set()
    for entry in data.get("tree", []):
        m = re.match(r"subworkflows/nf-core/(.+)/main\.nf", entry["path"])
        if m and "/tests" not in m.group(1):
            names.add(m.group(1))
    return sorted(names)


def fetch_repos(catalog_full_names, cache_dir, ttl_seconds, force=False):
    url1 = f"{SEARCH_URL}?q={SEARCH_QUERY}&per_page={PER_PAGE}&page=1"
    data1 = cached_api_get(url1, cache_dir, ttl_seconds, force)
    total = data1.get("total_count", 0)

    repos = []

    def extract(item):
        owner = item.get("owner", {})
        if owner.get("type") != "Organization":
            return
        fn = item["full_name"]
        repos.append(
            {
                "full_name": fn,
                "owner": owner["login"],
                "name": item["name"],
                "size_kb": item.get("size", 0),
                "url": item["html_url"],
                "pushed_at": item.get("pushed_at", ""),
                "in_catalog": fn in catalog_full_names,
            }
        )

    for item in data1.get("items", []):
        extract(item)

    total_pages = min(math.ceil(total / PER_PAGE), MAX_PAGES)
    if total_pages > 1:
        with ThreadPoolExecutor(max_workers=3) as exec:
            futs = []
            for pg in range(2, total_pages + 1):
                url = f"{SEARCH_URL}?q={SEARCH_QUERY}&per_page={PER_PAGE}&page={pg}"
                futs.append(
                    exec.submit(cached_api_get, url, cache_dir, ttl_seconds, force)
                )
            for f in futs:
                data = f.result()
                for item in data.get("items", []):
                    extract(item)
    return repos


def fetch_repo_info(full_name):
    url = f"https://api.github.com/repos/{full_name}"
    try:
        data, _ = api_get(url)
        return data
    except urllib.error.HTTPError:
        return None


def contents_list(full_name, path):
    url = f"https://api.github.com/repos/{full_name}/contents/{path}"
    try:
        data, _ = api_get(url)
        return data
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return None
        raise
