import os

GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN")
SEARCH_URL = "https://api.github.com/search/repositories"
CATALOG_URL = "https://nf-co.re/pipelines.json"
NF_CORE_MODULES_TREE = (
    "https://api.github.com/repos/nf-core/modules/git/trees/master?recursive=1"
)
PER_PAGE = 100
DEFAULT_CACHE_DIR = ".nfcore_study_cache"
SIZE_THRESHOLD_KB = 30 * 1024 * 2014
EXCLUDED_ORGS = {"nf-core", "nextflow-io", "seqeralabs"}
SEARCH_QUERY = "language:nextflow"
MAX_PAGES = 10
