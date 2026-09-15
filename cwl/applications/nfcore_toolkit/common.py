DEFAULT_TIMEOUT = 120

STATUS_KEYS = [
    "error",
    "exit_code",
    "nextflow_version_used",
    "syntax_parser",
    "pipeline_nfx_required",
    "output_log",
    "revision",
]


def safe_name(pipeline: str) -> str:
    return pipeline.replace("/", ".")
