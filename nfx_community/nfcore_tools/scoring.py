from .cache import (
    _NFCORE_BASH_CACHE,
    _NFCORE_CONTAINER_CACHE,
    _NFCORE_INPUT_CACHE,
    _NFCORE_OUTPUT_CACHE,
    DEFAULT_NFCORE_INPUT,
    DEFAULT_NFCORE_OUTPUT,
)
from .parsing import (
    _BUILTINS,
    _extract_all_tools,
    _extract_container,
    _extract_shell_script,
    _parse_bash_operators,
    _parse_container,
    _parse_input_section,
    _parse_output_section,
)

_OUTPUT_OPS = {"has_mix", "has_join", "has_map", "has_filter", "has_into"}


def _output_similarity(
    community,
    reference,
    optional_penalty_factor=0.25,
    ops_weight=0.7,
    channel_weight=0.3,
):
    c_ops = {k for k in _OUTPUT_OPS if community.get(k)}
    r_ops = {k for k in _OUTPUT_OPS if reference.get(k)}
    if not c_ops and not r_ops:
        ops_jaccard = 1.0
    else:
        intersection = c_ops & r_ops
        union = c_ops | r_ops
        ops_jaccard = len(intersection) / len(union) if union else 1.0
    c_comm = community.get("num_channels", 0)
    c_ref = reference.get("num_channels", 0)
    diff = c_comm - c_ref
    max_c = max(c_comm, c_ref, 1)
    if diff > 0:
        channel_sim = 1.0 - (diff / max_c)
    elif diff < 0:
        channel_sim = 1.0 - (optional_penalty_factor * abs(diff) / max_c)
    else:
        channel_sim = 1.0
    return round(ops_weight * ops_jaccard + channel_weight * channel_sim, 3)


_INPUT_OPS = {"has_mix", "has_join", "has_map", "has_filter"}


def _input_similarity(
    community,
    reference,
    optional_penalty_factor=0.25,
    ops_weight=0.7,
    channel_weight=0.3,
):
    c_ops = {k for k in _INPUT_OPS if community.get(k)}
    r_ops = {k for k in _INPUT_OPS if reference.get(k)}
    if not c_ops and not r_ops:
        ops_jaccard = 1.0
    else:
        intersection = c_ops & r_ops
        union = c_ops | r_ops
        ops_jaccard = len(intersection) / len(union) if union else 1.0
    c_comm = community.get("num_channels", 0)
    c_ref = reference.get("num_channels", 0)
    diff = c_comm - c_ref
    max_c = max(c_comm, c_ref, 1)
    if diff > 0:
        channel_sim = 1.0 - (diff / max_c)
    elif diff < 0:
        channel_sim = 1.0 - (optional_penalty_factor * abs(diff) / max_c)
    else:
        channel_sim = 1.0
    return round(ops_weight * ops_jaccard + channel_weight * channel_sim, 3)


def _input_differs(community, reference):
    for key in ("has_mix", "has_join", "has_map", "has_filter"):
        if community.get(key) and not reference.get(key):
            return True
    if community.get("num_channels", 0) != reference.get("num_channels", 0):
        return True
    return False


def _output_differs(community, reference):
    for key in ("has_mix", "has_join", "has_map", "has_filter", "has_into"):
        if community.get(key) and not reference.get(key):
            return True
    if community.get("num_channels", 0) != reference.get("num_channels", 0):
        return True
    return False


def _ops_jaccard(community, reference, ops):
    """Probability that a random operator in the universe matches the reference."""
    c_ops = {k for k in ops if community.get(k)}
    r_ops = {k for k in ops if reference.get(k)}
    if not c_ops and not r_ops:
        return 1.0
    inter = len(c_ops & r_ops)
    union = len(c_ops | r_ops)
    return inter / union if union else 1.0


def _channel_prob(community_count, reference_count):
    """Bounded channel-count compatibility probability."""
    c, r = community_count, reference_count
    if c == 0 and r == 0:
        return 1.0
    return (2.0 * min(c, r)) / (c + r)


def compute_rms_old(
    block_lines, nfcore_base_names=None, clone_path=None, cache_key=None
):
    result = {
        "score": 0.0,
        "tool_ratio": 0.0,
        "tool_cmds": [],
        "input": {
            "num_channels": 0,
            "has_mix": False,
            "has_join": False,
            "has_map": False,
            "has_filter": False,
            "has_complex_processing": False,
        },
        "output": {
            "num_channels": 0,
            "has_mix": False,
            "has_join": False,
            "has_map": False,
            "has_filter": False,
            "has_into": False,
            "has_complex_processing": False,
        },
        "input_similarity": 1.0,
        "output_similarity": 1.0,
        "container": None,
        "container_adjustment": 0.0,
        "penalties": {
            "pipe": False,
            "while": False,
            "for": False,
            "redirect": False,
            "input_transform": False,
            "output_transform": False,
        },
    }

    shell_lines = _extract_shell_script(block_lines, clone_path)
    if not shell_lines:
        result["score"] = 0.30
        return result

    all_tokens, tools, tools_fullname = _extract_all_tools(shell_lines)
    if not tools:
        result["score"] = 0.30
        return result

    result["tool_cmds"] = tools
    result["tool_cmds_fullname"] = tools_fullname

    ########################
    # nfcore_base_set = set(b.lower() for b in (nfcore_base_names or []))
    # nfcore_tools = [t for t in tools if t.lower() in nfcore_base_set]
    # R = len(nfcore_tools) / len(tools)

    #######################
    # nfcore_base_set = set(b.lower() for b in (nfcore_base_names or []))
    # unique_tools = set(t.lower() for t in tools)
    # unique_nfcore = set(t for t in unique_tools if t in nfcore_base_set)
    # R = len(unique_nfcore) / len(unique_tools) if unique_tools else 0.0

    ########################
    nfcore_base_set = set(b.lower() for b in (nfcore_base_names or []))
    unique_tools = set(t.lower() for t in tools)
    unique_nfcore = set(t for t in unique_tools if t in nfcore_base_set)
    base_ratio = len(unique_nfcore) / len(unique_tools) if unique_tools else 0.0
    tool_density = len(tools) / max(1, len(all_tokens))
    density_penalty = 0.0
    if tool_density < 0.20:
        density_penalty = (0.20 - tool_density) * 1.5
    R = max(0.0, base_ratio - density_penalty)
    #####################

    result["tool_ratio"] = R
    score = R

    primary_tool = None
    for t in tools:
        if t.lower() in nfcore_base_set:
            primary_tool = t.lower()
            break

    if primary_tool:
        ref_input = _NFCORE_INPUT_CACHE.get(primary_tool, DEFAULT_NFCORE_INPUT)
        ref_output = _NFCORE_OUTPUT_CACHE.get(primary_tool, DEFAULT_NFCORE_OUTPUT)
        ref_bash = _NFCORE_BASH_CACHE.get(primary_tool, {})

        community_input = _parse_input_section(block_lines)
        community_output = _parse_output_section(block_lines)
        result["input"] = community_input
        result["output"] = community_output

        input_sim = _input_similarity(community_input, ref_input, 0.25)
        output_sim = _output_similarity(community_output, ref_output, 0.25)
        result["input_similarity"] = input_sim
        result["output_similarity"] = output_sim

        score += -0.05 * (1.0 - input_sim)
        score += -0.05 * (1.0 - output_sim)

        community_container = _extract_container(block_lines)
        result["container"] = community_container
        ref_container_str = _NFCORE_CONTAINER_CACHE.get(primary_tool)

        a_container = 0.0
        if community_container:
            c_org, c_tool = _parse_container(community_container)
            r_org, r_tool = (
                _parse_container(ref_container_str)
                if ref_container_str
                else (None, None)
            )
            org_match = (c_org == r_org) if r_org else False
            tool_match = (c_tool == r_tool) if r_tool else False
            if org_match and tool_match:
                a_container = 0.05
            elif org_match and not tool_match:
                a_container = 0.04
            elif not org_match and tool_match:
                a_container = -0.02
            else:
                a_container = -0.05
        result["container_adjustment"] = a_container
        score += a_container

        community_bash = _parse_bash_operators(shell_lines)
        for op in ("pipe", "while", "for", "redirect"):
            if community_bash.get(op, False) and not ref_bash.get(op, False):
                score -= 0.05
                result["penalties"][op] = True

    # Input/output transformation penalty:
    # Builtin commands before the first nf-core tool → input preprocessing
    # Builtin commands after the last nf-core tool → output postprocessing
    nfcore_base_set_lower = set(b.lower() for b in (nfcore_base_names or []))
    nf_positions = [
        i for i, t in enumerate(all_tokens) if t.lower() in nfcore_base_set_lower
    ]
    if nf_positions:
        first_nf = nf_positions[0]
        last_nf = nf_positions[-1]
        input_builtins = [t for t in all_tokens[:first_nf] if t.lower() in _BUILTINS]
        output_builtins = [
            t for t in all_tokens[last_nf + 1 :] if t.lower() in _BUILTINS
        ]
        if input_builtins:
            score -= 0.02
            result["penalties"]["input_transform"] = True
        if output_builtins:
            score -= 0.02
            result["penalties"]["output_transform"] = True

    result["score"] = max(0.0, min(1.0, score))
    return result


def compute_mrs(
    block_lines, nfcore_base_names=None, clone_path=None, cache_key=None, config=None
):
    """Return the MRS (missed-reuse score): a probability of duplication.

    MRS is a mixture of six per-axis compatibility probabilities `C_i`:

        MRS = Σ_{i=1..6} w_i · C_i ,   Σ w_i = 1 ,   each C_i ∈ [0,1]

    Terms (term order fixes the weight-vector positions):
        C_adjR    tool ratio R = |unique nf-core tools|/|unique tools|
        C_bash    1 − (#bash ops whose presence differs from ref)/4
        C_in_ops  Jaccard over the 4 input operators vs reference
        C_in_ch   2·min(c,r)/(c+r) input-channel compatibility (=1 if both 0)
        C_outops  Jaccard over the 5 output operators vs reference
        C_outchannel 2·min(c,r)/(c+r) output-channel compatibility

    Every `C_i` is a true `[0,1]` probability and equals 1 when the block is a
    byte-for-byte copy of its reference module, so MRS is a mixture of
    probabilities (probability-valued score) that satisfies the identity axiom
    (a perfect duplicate scores ~1). Piecewise guard: if the block contains no
    catalog tool (`R == 0`), including blocks with no shell script or no tools
    at all, `MRS = 0` (a genuinely new / degenerate component).

    A partial `config` (e.g. `{"weights": [...]}`) is merged over the default.
    """
    # Default "provisional" mixture weights: coverage anchored at 0.30, the
    # five reference-relative axes at 0.14 each. Calibration solves this
    # vector later.
    _DEFAULT_CONFIG = {
        "weights": [0.30, 0.14, 0.14, 0.14, 0.14, 0.14],
    }

    weights = list(_DEFAULT_CONFIG["weights"])
    override = (config or {}).get("weights")
    if override:
        for i, v in enumerate(override[: len(weights)]):
            weights[i] = v

    result = {
        "score": 0.0,
        "tool_ratio": 0.0,
        "modifiers": {},  # Track exactly what reduced the score for easy debugging
        "input": {
            "num_channels": 0,
            "has_mix": False,
            "has_join": False,
            "has_map": False,
            "has_filter": False,
            "has_complex_processing": False,
        },
        "output": {
            "num_channels": 0,
            "has_mix": False,
            "has_join": False,
            "has_map": False,
            "has_filter": False,
            "has_into": False,
            "has_complex_processing": False,
        },
        "input_similarity": 1.0,
        "output_similarity": 1.0,
        "penalties": {"pipe": False, "while": False, "for": False, "redirect": False},
    }

    shell_lines = _extract_shell_script(block_lines, clone_path)
    if not shell_lines:
        result["terms"] = {
            "C_adjR": 0.0,
            "C_bash": 0.0,
            "C_in_ops": 0.0,
            "C_in_ch": 0.0,
            "C_out_ops": 0.0,
            "C_out_ch": 0.0,
        }
        result["weights"] = weights
        return result  # no shell script -> no evidence -> R = 0

    all_tokens, tools, tools_fullname = _extract_all_tools(shell_lines)
    result["all_tokens"] = all_tokens
    if not tools:
        result["weights"] = weights
        result["terms"] = {
            "C_adjR": 0.0,
            "C_bash": 0.0,
            "C_in_ops": 0.0,
            "C_in_ch": 0.0,
            "C_out_ops": 0.0,
            "C_out_ch": 0.0,
        }
        return result  # no tools -> no evidence -> R = 0

    result["tool_cmds"] = tools
    result["tool_cmds_fullname"] = tools_fullname

    # C_adjR: tool ratio (nf-core coverage)
    nfcore_base_set = set(b.lower() for b in (nfcore_base_names or []))
    unique_tools = set(t.lower() for t in tools)
    unique_nfcore = set(t for t in unique_tools if t in nfcore_base_set)
    R = len(unique_nfcore) / len(unique_tools) if unique_tools else 0.0
    result["tool_ratio"] = R
    C_adjR = R

    if R == 0.0:
        result["terms"] = {
            "C_adjR": C_adjR,
            "C_bash": 0.0,
            "C_in_ops": 0.0,
            "C_in_ch": 0.0,
            "C_out_ops": 0.0,
            "C_out_ch": 0.0,
        }
        result["weights"] = weights
        return result  # Genuine new component: MRS = 0

    # Reference for the reference-based penalties: the first catalog tool.
    primary_tool = next((t for t in tools if t.lower() in nfcore_base_set), None)
    primary_lower = primary_tool.lower() if primary_tool else None
    ref_input = _NFCORE_INPUT_CACHE.get(primary_lower, DEFAULT_NFCORE_INPUT)
    ref_output = _NFCORE_OUTPUT_CACHE.get(primary_lower, DEFAULT_NFCORE_OUTPUT)
    ref_bash = _NFCORE_BASH_CACHE.get(primary_lower, {})

    community_input = _parse_input_section(block_lines)
    community_output = _parse_output_section(block_lines)
    community_bash = _parse_bash_operators(shell_lines)

    # C_bash: symmetric operator mismatch vs reference
    bash_count = 0
    for op in ("pipe", "while", "for", "redirect"):
        if community_bash.get(op, False) != ref_bash.get(op, False):
            bash_count += 1
            result["penalties"][op] = True
    C_bash = 1.0 - bash_count / 4.0

    # C_in_ops / C_out_ops / C_in_ch / C_out_ch
    C_in_ops = _ops_jaccard(community_input, ref_input, _INPUT_OPS)
    C_out_ops = _ops_jaccard(community_output, ref_output, _OUTPUT_OPS)
    C_in_ch = _channel_prob(
        community_input.get("num_channels", 0), ref_input.get("num_channels", 0)
    )
    C_out_ch = _channel_prob(
        community_output.get("num_channels", 0), ref_output.get("num_channels", 0)
    )

    result["input"] = community_input
    result["output"] = community_output
    # Backward-compatible blended I/O similarity (kept for plot/analysis code).
    result["input_similarity"] = _input_similarity(
        community_input, ref_input, 0.25, 0.7, 0.3
    )
    result["output_similarity"] = _output_similarity(
        community_output, ref_output, 0.25, 0.7, 0.3
    )

    terms = {
        "C_adjR": C_adjR,
        "C_bash": C_bash,
        "C_in_ops": C_in_ops,
        "C_in_ch": C_in_ch,
        "C_out_ops": C_out_ops,
        "C_out_ch": C_out_ch,
    }
    result["terms"] = terms
    result["weights"] = weights

    score = sum(w * c for w, c in zip(weights, terms.values(), strict=True))
    result["modifiers"] = {
        "Base_R": R,
        "C_bash": C_bash,
        "C_in_ops": C_in_ops,
        "C_in_ch": C_in_ch,
        "C_out_ops": C_out_ops,
        "C_out_ch": C_out_ch,
    }
    result["score"] = score

    return result
