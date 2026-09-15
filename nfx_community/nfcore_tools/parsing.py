import re
import signal

import bashlex

_BUILTINS = {
    # Shell builtins
    "if",
    "then",
    "else",
    "fi",
    "for",
    "while",
    "do",
    "done",
    "in",
    "export",
    "set",
    "unset",
    "echo",
    "exit",
    "return",
    "local",
    "declare",
    "typeset",
    "let",
    "read",
    "shift",
    "source",
    ".",
    "[[",
    "[",
    "]]",
    "]",
    "eval",
    "exec",
    "trap",
    "ulimit",
    "umask",
    "wait",
    "alias",
    "unalias",
    "type",
    "times",
    "printf",
    "ln",
    "touch",
    "cat",
    "rm",
    # Unix infrastructure commands (not bioinformatics tools)
    "sed",
    "awk",
    "grep",
    "egrep",
    "fgrep",
    "mkdir",
    "cp",
    "mv",
    "cut",
    "sort",
    "wc",
    "head",
    "tail",
    "tr",
    "tee",
    "zcat",
    "gzip",
    "gunzip",
    "bzip2",
    "bunzip2",
    "xz",
    "unxz",
    "tar",
    "unzip",
    "basename",
    "dirname",
    "find",
    "xargs",
    "chmod",
    "chown",
    "chgrp",
    "env",
    "nice",
    "sleep",
    "date",
    "seq",
    "uniq",
    "paste",
    "join",
    "comm",
    "cmp",
    "diff",
    "patch",
    "readlink",
    "which",
    "file",
    "stat",
    "du",
    "strings",
    "expr",
    "cd",
    "pwd",
    "ls",
    "rmdir",
    "true",
    "false",
    "yes",
    "test",
    "timeout",
    "nohup",
    # Shell scripting / infra
    "bash",
    "curl",
    "wget",
    "git",
    "jq",
    "pigz",
    "gawk",
    "mawk",
    "rev",
    "convert",
    "module",
    "msg",
    "df",
    "watch",
    "rsync",
    "scp",
    "ssh",
    "ping",
    "traceroute",
    # Package/version management
    "require",
    "library",
    "options",
    "enable",
    "disable",
    "load",
    "unload",
    "use",
    "add",
    "remove",
    "install",
    "config",
    # nf-core template helper (not a real tool)
    "end_versions",
}

_SHELL_SHEBANG = re.compile(r"#!.*[/ ](?:bash|sh|dash|ksh|zsh)(?:\s|$)")


# ----
def extract_process_block(lines, start_lineno):
    idx = start_lineno - 1
    brace = -1
    for i in range(idx, min(idx + 5, len(lines))):
        if "{" in lines[i]:
            brace = i
            break
    if brace < 0:
        return None
    depth = 0
    started = False
    start = brace
    for i in range(brace, len(lines)):
        line = lines[i]
        for ch in line:
            if ch == "{":
                depth += 1
                started = True
            elif ch == "}":
                depth -= 1
        if started and depth == 0:
            return (start, i)
    return None


def _extract_shell_script(block_lines, clone_path=None):
    shell_lines = []
    try:
        from applications.nfcore_toolkit.nf_parse import (
            parse_processes,
            resolve_template,
        )

        full_text = "\n".join(block_lines)
        procs = parse_processes(full_text)
        if procs and procs[0].scripts:
            for stype, scode in procs[0].scripts:
                if not _is_non_shell_script(scode):
                    shell_lines.append(scode)
        if procs and procs[0].templates:
            for tpath in procs[0].templates:
                resolved = resolve_template(tpath, clone_path)
                if resolved and not _is_non_shell_script(resolved):
                    shell_lines.append(resolved)
    except Exception:
        pass
    if not shell_lines:
        in_heredoc = False
        heredoc_lines = []
        for line in block_lines:
            ls = line.strip()
            if ls.startswith('"""') and not in_heredoc:
                in_heredoc = True
                rest = ls[3:].strip()
                if rest:
                    heredoc_lines.append(rest)
                continue
            if ls.startswith('"""') and in_heredoc:
                rest = ls[3:].strip()
                if rest:
                    heredoc_lines.append(rest)
                break
            if in_heredoc:
                heredoc_lines.append(ls)
        if heredoc_lines and not _is_non_shell_script(heredoc_lines[0]):
            shell_lines = heredoc_lines
    return shell_lines


_GROOVY_ESC = re.compile(r'\\([\\$"n])')


def _decode_groovy_escapes(text):
    def repl(m):
        ch = m.group(1)
        mapping = {"\\": "\\", "$": "$", '"': '"', "n": "\n"}
        return mapping.get(ch, ch)

    return _GROOVY_ESC.sub(repl, text)


def _normalize_heredocs(text):
    lines = text.split("\n")
    result = []
    heredocs = []
    for i, line in enumerate(lines):
        m = re.search(r"<<(-)?\s*(\S+)", line)
        if m:
            dash = m.group(1)
            delim = m.group(2)
            heredocs.append((delim, len(result)))
            if dash:
                line = line[: m.start()] + "<<" + line[m.end(1) :]
        trimmed = line.strip()
        for idx, (delim, _) in enumerate(heredocs):
            if trimmed == delim and i > 0:
                line = trimmed
                heredocs.pop(idx)
                break
        result.append(line)
    return "\n".join(result)


def _is_non_shell_script(text):
    first = text.lstrip().split("\n", 1)[0] if text else ""
    return first.startswith("#!/") and not _SHELL_SHEBANG.match(first)


def detect_script_interpreter(block_lines):
    """Return the script interpreter for a process block, else ``"default"``.

    The interpreter is taken from the first ``#!`` shebang line found in the
    block. ``/usr/bin/env <interp>`` is resolved to ``<interp>``; flag-only
    shebangs fall back to ``"default"``. Blocks with no ``#!`` line at all
    (the common Nextflow style, implicitly shell) are reported as ``"default"``.
    """
    for line in block_lines:
        s = line.strip()
        if not s.startswith("#!/"):
            continue
        m = re.match(r"#!\s*(\S+)", s)
        if not m:
            return "default"
        tok = m.group(1)
        if tok.startswith("-"):
            return "default"
        exe = tok.rstrip("/").split("/")[-1]
        if exe == "env":
            rest = s[m.end() :].lstrip()
            toks = rest.split()
            if len(toks) > 1 and toks[0].startswith("-"):
                toks = toks[1:]
            nxt = toks[0] if toks else ""
            exe = nxt.split("/")[-1] if nxt else "env"
        return exe if exe else "default"
    return "default"


_parse_fail_count = 0
_PARSE_TIMEOUT = 15  # seconds per script (integer for signal.alarm)


def _timeout_handler(signum, frame):
    raise TimeoutError("bashlex parse timed out")


try:
    signal.signal(signal.SIGALRM, _timeout_handler)
except ValueError:
    pass  # not in main thread — alarm-based timeout won't be available


class TimeoutError(Exception):
    pass


def reset_parse_fail_counter():
    global _parse_fail_count
    _parse_fail_count = 0


def _parse_bashlex(script_text):
    signal.alarm(_PARSE_TIMEOUT)
    try:
        return bashlex.parser.parse(script_text)
    finally:
        signal.alarm(0)


def get_parse_fail_count():
    return _parse_fail_count


def _walk_ast(node, all_tokens, all_fullname):
    kind = node.kind

    if kind == "command":
        for part in node.parts:
            if part.kind == "word" and hasattr(part, "word") and part.word:
                cmd = part.word.strip("'\"")
                if cmd and not cmd.startswith(("-", "$")) and cmd != "\\":
                    all_tokens.append(cmd)
                    fullname = cmd
                    if len(node.parts) > 1:
                        from .resolve import MULTITOOL_KITS

                        if cmd in MULTITOOL_KITS:
                            for sub_part in node.parts[1:]:
                                if sub_part.kind == "word" and hasattr(
                                    sub_part, "word"
                                ):
                                    sub = sub_part.word.strip("'\"")
                                    if (
                                        sub
                                        and not sub.startswith("-")
                                        and "." not in sub
                                    ):
                                        fullname = f"{cmd}/{sub}"
                                        break
                    all_fullname.append(fullname)
                break

    elif kind == "reservedword":
        word = getattr(node, "word", "")
        if word in ("for", "while", "until", "if", "case"):
            all_tokens.append(word)
            all_fullname.append(word)

    if hasattr(node, "list"):
        for child in node.list:
            _walk_ast(child, all_tokens, all_fullname)
    if hasattr(node, "parts"):
        for child in node.parts:
            _walk_ast(child, all_tokens, all_fullname)


def _normalize_brackets(text):
    return text.replace("[[", "[").replace("]]", "]")


def _extract_all_tools(shell_lines):
    global _parse_fail_count
    all_tokens = []
    all_fullname = []
    script_text = "\n".join(shell_lines)
    script_text = _decode_groovy_escapes(script_text)
    script_text = _normalize_heredocs(script_text)
    script_text = _normalize_brackets(script_text)
    try:
        parts = _parse_bashlex(script_text)
    except Exception:
        _parse_fail_count += 1
        return [], [], []
    for node_list in parts:
        _walk_ast(node_list, all_tokens, all_fullname)
    tools = [t for t in all_tokens if t.lower() not in _BUILTINS]
    tools_fullname = [
        f for t, f in zip(all_tokens, all_fullname) if t.lower() not in _BUILTINS
    ]
    return all_tokens, tools, tools_fullname


_CONTAINER_RE = re.compile(r"(?:([^/]+)/)?([^/:]+)(?::.+)?")


def _parse_container(container_str):
    if not container_str:
        return None, None
    m = _CONTAINER_RE.match(container_str)
    if m:
        org = m.group(1) or None
        tool = m.group(2)
        return org, tool
    return None, container_str


def _parse_bash_operators(shell_lines):
    text = "\n".join(shell_lines)
    lower_text = text.lower()
    return {
        "conditional": bool(re.search(r"\bif\b|\belif\b|\bcase\b", lower_text)),
        "pipe": "|" in text and "|>" not in text,
        "while": bool(re.search(r"\bwhile\b", lower_text)),
        "for": bool(re.search(r"\bfor\b", lower_text)),
        "redirect": bool(
            re.search(r"(?:^|\s)>(?:>|&)?|&>|<>|\b\d>&?\d?(?!\w)", text)
            or re.search(r"(?:^|\s)<(?!<)", text)
        ),
        "andor": bool(re.search(r"(?:^|\s)&&(?:\s|$)|(?:^|\s)\|\|(?:\s|$)", text)),
    }


def _extract_container(block_lines):
    for line in block_lines:
        ls = line.strip().lower()
        if ls.startswith("container"):
            rest = line.strip()
            rest = rest[len("container") :].strip().strip("'\"")
            return rest if rest else None
    return None


SECTION_HEADER = re.compile(
    r"^\s*(input|output|script|when|exec|workflow)\s*:", re.IGNORECASE
)

INPUT_CHAIN_OPS = re.compile(r"\.(mix|join|map|filter)\s*\(")


def _parse_input_section(block_lines):
    result = {
        "num_channels": 0,
        "has_mix": False,
        "has_join": False,
        "has_map": False,
        "has_filter": False,
        "has_complex_processing": False,
    }
    in_input = False
    continuation = False
    for line in block_lines:
        ls = line.strip()
        m = SECTION_HEADER.match(ls)
        if m:
            section = m.group(1).lower()
            if section == "input":
                in_input = True
            elif in_input:
                break
            continuation = False
            continue
        if not in_input:
            continue
        if ls.startswith(")"):
            continue
        if continuation:
            continuation = ls.endswith(",")
            continue
        is_channel = ls.lower().startswith(
            ("tuple ", "val(", "path(", "file(", "env(", "channel ", "from ")
        )
        if is_channel:
            result["num_channels"] += 1
            continuation = ls.endswith(",")
        for op in INPUT_CHAIN_OPS.finditer(ls):
            name = op.group(1)
            if name == "mix":
                result["has_mix"] = True
            elif name == "join":
                result["has_join"] = True
            elif name == "map":
                result["has_map"] = True
            elif name == "filter":
                result["has_filter"] = True
    result["has_complex_processing"] = any(
        (
            result["has_mix"],
            result["has_join"],
            result["has_map"],
            result["has_filter"],
            result["num_channels"] > 1,
        )
    )
    return result


OUTPUT_CHAIN_OPS = re.compile(r"\.(mix|join|map|filter|into)\s*\(")


def _parse_output_section(block_lines):
    result = {
        "num_channels": 0,
        "has_mix": False,
        "has_join": False,
        "has_map": False,
        "has_filter": False,
        "has_into": False,
        "has_complex_processing": False,
    }
    in_output = False
    for line in block_lines:
        ls = line.strip()
        m = SECTION_HEADER.match(ls)
        if m:
            section = m.group(1).lower()
            if section == "output":
                in_output = True
            elif in_output:
                break
            continue
        if not in_output:
            continue
        if ls.startswith(")"):
            continue
        if re.match(r"emit\s", ls, re.IGNORECASE):
            result["num_channels"] += 1
            continue
        if ls.lower().startswith(("tuple ", "val(", "path(")):
            result["num_channels"] += 1
        for op in OUTPUT_CHAIN_OPS.finditer(ls):
            name = op.group(1)
            if name == "mix":
                result["has_mix"] = True
            elif name == "join":
                result["has_join"] = True
            elif name == "map":
                result["has_map"] = True
            elif name == "filter":
                result["has_filter"] = True
            elif name == "into":
                result["has_into"] = True
    result["has_complex_processing"] = any(
        (
            result["has_mix"],
            result["has_join"],
            result["has_map"],
            result["has_filter"],
            result["has_into"],
            result["num_channels"] > 1,
        )
    )
    return result
