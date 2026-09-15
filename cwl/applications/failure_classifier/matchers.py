import re


class MatchResult:
    def __init__(self, category, label, confidence, evidence):
        self.category = category
        self.label = label
        self.confidence = confidence
        self.evidence = evidence


def _scan(text, *patterns):
    if not text:
        return None
    for p in patterns:
        m = re.search(p, text)
        if m:
            return m.group().strip()
    return None


def _find(ctx, *patterns):
    ev = _scan(ctx.get("output_log_tail", ""), *patterns)
    if ev:
        return ev
    ev = _scan(ctx.get("error_str", ""), *patterns)
    if ev:
        return ev
    return None


def match_config_parsing(ctx):
    # NF 26.x introduced stricter config parsing. Multiple distinct
    # regressions have been identified. Patterns are ordered from most
    # specific to most generic so the first match wins.

    # Type A: "Variable declarations cannot be mixed with config statements"
    # e.g., `def trace_timestamp = new java.util.Date().format(...)` in config.
    # NF 26.x disallows variable assignments in config scope.
    ev = _find(ctx, r"Variable declarations cannot be mixed with config statements")
    if ev:
        return MatchResult(
            "config_parsing",
            "Variable declarations not allowed in Nextflow 26.x config",
            0.95,
            ev,
        )

    # Type B: <name> is not defined (manifest, validation, etc.)
    # e.g., `` `manifest` is not defined `` — new scoping rules require
    # explicit variable declaration before use in config.
    ev = _find(ctx, r"`manifest` is not defined", r"`validation` is not defined")
    if ev:
        return MatchResult(
            "config_parsing",
            "Config variable not declared (new scoping in Nextflow 26.x)",
            0.95,
            ev,
        )

    # Type C: "Invalid include source"
    # e.g., test_full_sispa profile includes a config file path that
    # does not exist at the resolved pipeline revision.
    ev = _find(ctx, r"Invalid include source")
    if ev:
        return MatchResult(
            "config_parsing",
            "Config file include source not found at resolved revision",
            0.95,
            ev,
        )

    # Type D: "Unexpected input: ':'"
    # e.g., `withName:` syntax (with trailing colon) no longer allowed.
    ev = _find(ctx, r"Unexpected input:")
    if ev:
        return MatchResult(
            "config_parsing",
            "Unexpected config syntax (Nextflow 26.x stricter parsing)",
            0.95,
            ev,
        )

    # Type E: "If statements cannot be mixed with config statements"
    # NF 26.x no longer allows `if {}` blocks inside nextflow.config.
    ev = _find(ctx, r"If statements cannot be mixed with config statements")
    if ev:
        return MatchResult(
            "config_parsing",
            "if/else blocks not allowed in Nextflow 26.x config",
            0.95,
            ev,
        )

    # Generic fallback for any other "Config parsing failed" messages
    ev = _find(ctx, r"Config parsing failed")
    if ev:
        return MatchResult(
            "config_parsing", "Nextflow config format regression", 0.95, ev
        )
    return None


def match_groovy_api(ctx):
    # Matches: "No signature of method: groovyx.gpars.dataflow.DataflowBroadcast.into()"
    # Matches: "Cannot invoke method optional() on null object"
    # NF 26.x removed GPars-based channel APIs (DataflowBroadcast, DataflowQueue)
    # and deprecated Channel.from(), Channel.optional().
    ev = _find(
        ctx,
        r"No signature of method: groovyx\.gpars\.dataflow\.",
        r"Cannot invoke method (optional|into|from)\(\) on null object",
    )
    if ev:
        return MatchResult("groovy_api", "Nextflow GPars API removed", 0.95, ev)
    return None


def match_script_compilation(ctx):
    # Matches: "`NFCORE_DETAXIZER` is not defined"
    # and: "Script compilation failed"
    # Pipeline references subworkflow entry points that require the
    # nf-schema plugin to be loaded at runtime.
    err = ctx.get("error_str", "")
    log = ctx.get("output_log_tail", "")
    combined = log + "\n" + err
    ev = _scan(combined, r"is not defined", r"Script compilation failed")
    if ev:
        return MatchResult(
            "script_compilation",
            "Missing module or plugin import",
            0.90 if "not defined" in (ev.lower()) else 0.80,
            ev,
        )
    return None


def match_timeout(ctx):
    # Matches: "Timeout 300 seconds"
    # Runner-level timeout (depends on the pipeline orchestrator's timeout value).
    # General: any "Timeout <N> seconds" in the output.
    ev = _find(ctx, r"Timeout \d+ seconds")
    if ev:
        return MatchResult(
            "timeout", "Pipeline execution or DAG generation timed out", 0.95, ev
        )
    return None


def match_missing_file(ctx):
    # Matches: "No such file or directory: /path/to/some/file"
    # Nextflow runtime error when a required input file, reference genome,
    # or asset is not present at the expected path.
    ev = _find(ctx, r"No such file or directory:\s*\S+")
    if ev:
        return MatchResult("missing_file", "Required file not found", 0.90, ev)
    return None


def match_param_validation(ctx):
    # Matches: "Validation of pipeline parameters failed"
    # and: "Missing required parameter(s): --input"
    # Pipeline uses nf-validation or nf-schema plugin and required
    # parameters were not provided.
    ev = _find(ctx, r"Validation of pipeline parameters failed")
    if ev:
        detail = _find(ctx, r"Missing required parameter")
        return MatchResult(
            "param_validation",
            "Missing required pipeline parameters",
            0.95,
            detail or ev,
        )
    return None


def match_channel_mismatch(ctx):
    # Matches: "Workflow `PIPELINE_INITIALISATION` declares 8 input channels but 6 were given"
    # Subworkflow template was updated but the entry workflow wasn't regenerated,
    # causing a channel count mismatch between the workflow and its subworkflow.
    ev = _find(ctx, r"declares \d+ input channels but \d+ were given")
    if ev:
        return MatchResult(
            "channel_mismatch", "Subworkflow input channel count mismatch", 0.95, ev
        )
    return None


def match_permissions(ctx):
    # Matches: "Cannot create work-dir '/work_ikmb/...'"
    # Pipeline hardcodes an absolute work directory path from a different
    # cluster filesystem, or the runner lacks write permissions.
    ev = _find(ctx, r"Cannot create work-dir")
    if ev:
        return MatchResult(
            "permissions",
            "Cannot create work directory (hardcoded path or missing permissions)",
            0.95,
            ev,
        )
    return None


def match_unknown_config(ctx):
    # Matches: "Unknown config attribute `params.PSRDB_URL`"
    # Pipeline config references a parameter name that was removed or
    # renamed in the current pipeline version.
    ev = _find(ctx, r"Unknown config attribute")
    if ev:
        return MatchResult(
            "unknown_config", "Config references unknown parameter", 0.95, ev
        )
    return None


def match_validation(ctx):
    # Matches: "Error for field 'tool' (centrifuger): Expected any of [...]"
    # Pipeline input validation (e.g., samplesheet CSV) found an invalid
    # value that doesn't match the allowed enum set.
    ev = _find(ctx, r"Error for field '.*'")
    if ev:
        return MatchResult("validation", "Input validation failed", 0.95, ev)
    return None


def match_dsl1_not_supported(ctx):
    ev = _find(ctx, r"DSL1 is no longer supported")
    if ev:
        return MatchResult(
            "dsl1_not_supported",
            "Pipeline uses DSL1 — requires Nextflow ≤ 22.10.x + Java 17",
            0.95,
            ev,
        )
    return None


def match_unknown_option(ctx):
    # Matches: "Unknown option: -preview"
    # NF versions before 22.04.0 don't support the -preview flag.
    # The pre-flight check in run_nextflow_preview should catch this
    # early, but this matcher acts as a fallback for cases where the
    # version check was skipped (e.g. unknown system version).
    ev = _find(ctx, r"Unknown option:")
    if ev:
        return MatchResult(
            "unknown_option", "Nextflow version too old for -preview flag", 0.95, ev
        )
    return None


def match_jvm_error(ctx):
    # Matches: "NoClassDefFoundError"
    # JVM class not found — typically means the NF version is too old
    # for the installed Java runtime (e.g. NF 20.04.x with Java 21).
    ev = _find(ctx, r"NoClassDefFoundError")
    if ev:
        return MatchResult(
            "jvm_error",
            "JVM class not found (Nextflow too old for installed Java)",
            0.90,
            ev,
        )
    return None


def match_preview_failed(ctx):
    # Matches: "dag.dot not generated" (rc==0, no DAG produced)
    # and "nextflow preview failed — empty workflow ..." (parse_dot_to_json fallback).
    # This covers cases where nextflow exited successfully (rc==0) but
    # produced no DAG output (no DOT file or no process nodes).
    # Cases where rc != 0 are handled by other matchers using the raw
    # nextflow error message.
    ev = _find(
        ctx, r"dag\.dot not generated", r"nextflow preview failed", r"empty workflow"
    )
    if ev:
        return MatchResult(
            "preview_failed",
            "nextflow produced no DAG (rc==0, no DOT file or empty workflow)",
            0.85,
            ev,
        )
    return None


def match_missing_input(ctx):
    # Matches: "Missing required parameter(s): input"
    # and: "Input samplesheet not specified!"
    # Pipeline was launched with -profile test but the test profile
    # doesn't define all mandatory parameters (e.g., --input, --fasta).
    # The two regexes cover the nf-validation schema plugin variant
    # and the older nf-core template variant.
    ev = _find(ctx, r"Missing required parameter", r"[Ii]nput\s+\S*\s*not specified")
    if ev:
        return MatchResult(
            "missing_input", "Required parameter not provided by test profile", 0.95, ev
        )
    return None


def match_generic_error(ctx):
    # Matches: "ERROR ~ <message>"
    # Catch-all for any ERROR-level line in the Nextflow output that
    # wasn't matched by a more specific rule above.
    ev = _find(ctx, r"ERROR\s*~.*")
    if ev:
        return MatchResult("compilatior_error", ev, 0.50, ev)
    return None


# Priority order: most specific / highest confidence first.
# If multiple matchers could fire, the first one wins.
MATCHERS = [
    ("timeout", match_timeout),
    ("preview_failed", match_preview_failed),
    ("unknown_option", match_unknown_option),
    ("jvm_error", match_jvm_error),
    ("config_parsing", match_config_parsing),
    ("groovy_api", match_groovy_api),
    ("script_compilation", match_script_compilation),
    ("channel_mismatch", match_channel_mismatch),
    ("permissions", match_permissions),
    ("unknown_config", match_unknown_config),
    ("missing_file", match_missing_file),
    ("missing_input", match_missing_input),
    ("param_validation", match_param_validation),
    ("validation", match_validation),
    ("dsl1_not_supported", match_dsl1_not_supported),
    ("compilatior_error", match_generic_error),
]

CATEGORIES = {t[0] for t in MATCHERS}
