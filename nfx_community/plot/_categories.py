from ._colors import C_LOW, C_MID

# RMS threshold — only categorize evidence entries whose RMS >= this value.
# RMS=0 is exact nf-core reuse (no categorization needed).
# RMS 0–0.4 are near-nf-core processes, excluded here for clarity.
RMS_CATEGORIZE_THRESHOLD = 0.4

DROPIN_COLOR = "#27ae60"
MATCH_TOOL_COLOR = "#3498db"
MULTI_TOOLS_COLOR = C_MID
BASH_OPS_COLOR = C_LOW
IO_COLOR = "#1abc9c"
MISMATCH_INPUT_COLOR = "#d35400"
MISMATCH_OUTPUT_COLOR = "#e84393"


def categorize(comp):
    cats = set()
    tool_ratio = comp.get("tool_ratio", 0)
    tool_cmds = comp.get("tool_cmds", [])
    penalties = comp.get("penalties", {})
    inp = comp.get("input", {})
    out = comp.get("output", {})

    unique_tools = set(tool_cmds)

    if tool_ratio >= 0.9 and len(unique_tools) == 1:
        cats.add("match_tool")

    if len(unique_tools) >= 2:
        cats.add("multi_tools")

    bash_op_keys = {"pipe", "while", "for", "redirect"}
    if any(penalties.get(k) for k in bash_op_keys):
        cats.add("bash_operators")

    input_sim = comp.get("input_similarity", 1.0)
    output_sim = comp.get("output_similarity", 1.0)
    # if (inp.get("has_complex_processing") or out.get("has_complex_processing")
    #         or input_sim < 1.0 or output_sim < 1.0):
    #     cats.add("io_processing")
    if (
        inp.get("has_complex_processing")
        or out.get("has_complex_processing")
        or penalties.get("input_transform")
        or penalties.get("output_transform")
    ):
        cats.add("io_processing")

    if input_sim < 1.0:
        cats.add("input_mismatch")
    if output_sim < 1.0:
        cats.add("output_mismatch")

    if cats == {"match_tool"}:
        cats.add("exact_dropin")
        cats.discard("match_tool")

    return cats


OVERLAP_HATCH = "//"

CATEGORY_META = [
    ("exact_dropin", "Exact drop-in (zero effort)", DROPIN_COLOR, None),
    ("match_tool", "Match script", MATCH_TOOL_COLOR, OVERLAP_HATCH),
    ("multi_tools", "Multi-tools script", MULTI_TOOLS_COLOR, OVERLAP_HATCH),
    ("bash_operators", "Bash control flow", BASH_OPS_COLOR, OVERLAP_HATCH),
    ("io_processing", "I/O channel processing", IO_COLOR, OVERLAP_HATCH),
    ("input_mismatch", "Input channel mismatch", MISMATCH_INPUT_COLOR, OVERLAP_HATCH),
    (
        "output_mismatch",
        "Output channel mismatch",
        MISMATCH_OUTPUT_COLOR,
        OVERLAP_HATCH,
    ),
]
