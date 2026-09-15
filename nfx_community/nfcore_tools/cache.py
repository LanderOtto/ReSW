from pathlib import Path

from .parsing import (
    _extract_container,
    _extract_shell_script,
    _parse_bash_operators,
    _parse_input_section,
    _parse_output_section,
    extract_process_block,
)

_NFCORE_INPUT_CACHE = {}
DEFAULT_NFCORE_INPUT = {
    "num_channels": 1,
    "has_mix": False,
    "has_join": False,
    "has_map": False,
    "has_filter": False,
    "has_complex_processing": False,
}

_NFCORE_OUTPUT_CACHE = {}
DEFAULT_NFCORE_OUTPUT = {
    "num_channels": 1,
    "has_mix": False,
    "has_join": False,
    "has_map": False,
    "has_filter": False,
    "has_into": False,
    "has_complex_processing": False,
}

_NFCORE_CONTAINER_CACHE = {}
_NFCORE_BASH_CACHE = {}


def build_input_cache_from_clone(clone_path):
    modules_dir = Path(clone_path) / "modules" / "nf-core"
    if not modules_dir.is_dir():
        return
    for main_nf in sorted(modules_dir.rglob("main.nf")):
        try:
            lines = main_nf.read_text().splitlines()
        except Exception:
            continue
        for lineno, line in enumerate(lines, 1):
            import re

            m = re.match(r"process\s+(\w+)", line.strip(), re.IGNORECASE)
            if m:
                block = extract_process_block(lines, lineno)
                if block:
                    block_text = lines[block[0] : block[1] + 1]
                    input_sig = _parse_input_section(block_text)
                    output_sig = _parse_output_section(block_text)
                    container_tag = _extract_container(block_text)
                    shell_script = _extract_shell_script(block_text, clone_path)
                    bash_ops = _parse_bash_operators(shell_script)
                    rel = main_nf.relative_to(modules_dir)
                    base_name = rel.parts[0].lower()
                    if base_name not in _NFCORE_INPUT_CACHE:
                        _NFCORE_INPUT_CACHE[base_name] = input_sig
                    if base_name not in _NFCORE_OUTPUT_CACHE:
                        _NFCORE_OUTPUT_CACHE[base_name] = output_sig
                    if base_name not in _NFCORE_CONTAINER_CACHE:
                        _NFCORE_CONTAINER_CACHE[base_name] = container_tag
                    if base_name not in _NFCORE_BASH_CACHE:
                        _NFCORE_BASH_CACHE[base_name] = bash_ops
                break
