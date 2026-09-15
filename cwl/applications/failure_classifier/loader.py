import os

from failure_classifier.scanner import read_tail


def load_pipeline_dir(
    pipeline_dir,
    error_str=None,
    exit_code=None,
    log_path=None,
    debug_log_path=None,
    pipeline_name=None,
):
    pipeline_dir = os.path.abspath(pipeline_dir)
    if not os.path.isdir(pipeline_dir):
        raise NotADirectoryError(f"Not a directory: {pipeline_dir}")

    output_log = log_path or os.path.join(pipeline_dir, "nextflow_output.log")
    nf_log = debug_log_path or os.path.join(pipeline_dir, ".nextflow.log")

    return {
        "pipeline_dir": pipeline_dir,
        "pipeline": pipeline_name or os.path.basename(pipeline_dir),
        "exit_code": exit_code,
        "error_str": error_str or "",
        "output_log_tail": read_tail(
            output_log if os.path.isfile(output_log) else None
        ),
        "dot_log_tail": read_tail(nf_log if os.path.isfile(nf_log) else None),
        "output_log_path": output_log if os.path.isfile(output_log) else None,
        "dot_log_path": nf_log if os.path.isfile(nf_log) else None,
    }
