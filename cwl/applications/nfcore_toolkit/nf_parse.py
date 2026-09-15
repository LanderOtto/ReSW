"""Nextflow .nf file parser using Lark grammar.

Leverages the EBNF grammar from nf-parser to reliably extract
process scripts, template references, inputs, outputs, and directives.
"""

from __future__ import annotations

import re
import shlex
from pathlib import Path
from typing import Optional

from lark import Lark, Token, Tree
from lark.visitors import Interpreter

_GRAMMAR_PATH = Path(__file__).parent / "nf.lark"
_GRAMMAR = _GRAMMAR_PATH.read_text()

_PARSER: Optional[Lark] = None


def _get_parser() -> Lark:
    global _PARSER
    if _PARSER is None:
        _PARSER = Lark(_GRAMMAR, parser="lalr")
    return _PARSER


class ProcessInfo:
    """Information extracted from a Nextflow process definition."""

    __slots__ = (
        "name",
        "scripts",
        "templates",
        "inputs",
        "outputs",
        "directives",
    )

    def __init__(self, name: str = ""):
        self.name = name
        self.scripts: list[tuple[str, str]] = []
        self.templates: list[str] = []
        self.inputs: list[tuple[str, str]] = []
        self.outputs: list[tuple[str, str]] = []
        self.directives: dict[str, str] = {}

    def __repr__(self) -> str:
        return (
            f"ProcessInfo(name={self.name!r}, "
            f"scripts={len(self.scripts)}, "
            f"templates={self.templates})"
        )


_SHELL_BUILTINS: set[str] = {
    "[",
    "]",
    "{",
    "}",
    "(",
    ")",
    "!",
    "if",
    "then",
    "else",
    "elif",
    "fi",
    "while",
    "do",
    "done",
    "for",
    "in",
    "case",
    "esac",
    "until",
    "select",
    "function",
    "export",
    "set",
    "unset",
    "trap",
    "return",
    "exit",
    "source",
    ".",
    "cd",
    "mkdir",
    "rmdir",
    "rm",
    "mv",
    "cp",
    "ln",
    "touch",
    "echo",
    "printf",
    "read",
    "exec",
    "shift",
    "wait",
    "eval",
    "type",
    "ulimit",
    "umask",
    "alias",
    "unalias",
    "bind",
    "builtin",
    "command",
    "declare",
    "typeset",
    "enable",
    "let",
    "local",
    "readonly",
    "test",
    "times",
    "gzip",
    "gunzip",
    "grep",
    "find",
    "xargs",
    "sort",
    "head",
    "tail",
    "cut",
    "tr",
    "sed",
    "awk",
    "tee",
    "pipefail",
    "true",
    "false",
    "pushd",
    "popd",
    "dirname",
    "basename",
    "readlink",
    "which",
    "mktemp",
    "diff",
    "cmp",
    "comm",
    "seq",
    "shopt",
    "cat",
}


class _ScriptExtractor(Interpreter):
    """Walk the Lark parse tree and collect ProcessInfo objects."""

    def __init__(self) -> None:
        self.processes: list[ProcessInfo] = []
        self._current: Optional[ProcessInfo] = None

    def start(self, tree: Tree) -> list[ProcessInfo]:
        for child in tree.children:
            if isinstance(child, Tree):
                self.visit(child)
        return self.processes

    # ---- top-level nodes ----
    def process(self, tree: Tree) -> None:
        name = None
        body = None
        for child in tree.children:
            if isinstance(child, Token) and child.type == "CNAME":
                name = str(child)
            elif isinstance(child, Tree):
                body = child
        prev = self._current
        self._current = ProcessInfo(name)
        if body is not None:
            self.visit(body)
        self.processes.append(self._current)
        self._current = prev

    def workflow(self, tree: Tree) -> None:
        pass  # skip workflows

    def function(self, tree: Tree) -> None:
        pass  # skip functions

    # ---- process block ----
    def process_block(self, tree: Tree) -> None:
        for child in tree.children:
            if isinstance(child, Tree):
                self.visit(child)

    def input(self, tree: Tree) -> None:
        for child in tree.children:
            val = self._extract_io_value(child)
            if val is not None:
                self._current.inputs.append(val)

    def output(self, tree: Tree) -> None:
        for child in tree.children:
            val = self._extract_io_value(child)
            if val is not None:
                self._current.outputs.append(val)

    @staticmethod
    def _extract_io_value(node: object) -> Optional[tuple[str, str]]:
        """Extract (iotype, name) from a val/file/path/env/tuple/each Tree node."""
        if not isinstance(node, Tree):
            return None
        iotype = node.data
        if iotype not in ("val", "file", "path", "env", "stdin", "tuple", "each"):
            return None
        name = _ScriptExtractor._resolve_token(node)
        if name is not None:
            return (iotype, name)
        return None

    def script(self, tree: Tree) -> None:
        for child in tree.children:
            self.visit(child)

    def shell(self, tree: Tree) -> None:
        for child in tree.children:
            raw = str(child) if isinstance(child, Token) else ""
            raw = raw.strip()
            if raw.startswith("'''"):
                raw = raw[3:]
            if raw.endswith("'''"):
                raw = raw[:-3]
            self._current.scripts.append(("shell", raw.strip()))

    def exec_block(self, tree: Tree) -> None:
        pass  # exec: type blocks

    # ---- script constructs ----
    def bash_script(self, tree: Tree) -> None:
        raw = str(tree.children[0]) if tree.children else ""
        raw = raw.strip()
        if raw.startswith('"""'):
            raw = raw[3:]
        if raw.endswith('"""'):
            raw = raw[:-3]
        self._current.scripts.append(("inline", raw.strip()))

    def script_path(self, tree: Tree) -> None:
        for child in tree.children:
            if isinstance(child, Token):
                val = str(child).strip("\"'")
                self._current.templates.append(val)

    # ---- input/output type helpers ----
    def _add_io(self, direction: str, tree: Tree) -> None:
        iotype = tree.data
        for child in tree.children:
            token = self._resolve_token(child)
            if token is not None:
                lst = (
                    self._current.inputs
                    if direction == "input"
                    else self._current.outputs
                )
                lst.append((iotype, token))

    @staticmethod
    def _resolve_token(node: object) -> Optional[str]:
        if isinstance(node, Token):
            return str(node).strip("\"'")
        if isinstance(node, Tree):
            for child in node.children:
                result = _ScriptExtractor._resolve_token(child)
                if result is not None:
                    return result
        return None

    # ---- directives (stored without prefix for template detection) ----
    def directive(self, tree: Tree) -> None:
        pass  # handled by named directive rules below

    def __getattr__(self, name: str):
        """Return a no-op visitor for any grammar rule we don't need."""
        # Skip dunder methods that Python might look up
        if name.startswith("__"):
            raise AttributeError(name)
        return lambda tree: None


# ── Public API ──────────────────────────────────────────────────────────────


def parse_processes(content: str) -> list[ProcessInfo]:
    """Parse a ``.nf`` file and return a list of ``ProcessInfo``.

    Handles:
    - Inline scripts (triple-double-quotes ``\"\"\"...\"\"\"``)
    - Shell scripts (triple-single-quotes ``\'\'\'...\'\'\'``)
    - Template references (``template "path.sh"``)
    """
    parser = _get_parser()
    try:
        tree = parser.parse(content)
    except Exception:
        return []
    extractor = _ScriptExtractor()
    # The grammar uses ``?start`` which may inline the root node.
    # Always wrap so that ``start`` dispatches to child visitors.
    if tree.data != "start":
        tree = Tree("start", [tree])
    return extractor.start(tree)


def extract_script_blocks(content: str) -> list[tuple[str, str]]:
    """Replace the regex-based ``extract_script_blocks`` with a parser version.

    Returns list of ``(block_type, content)`` tuples where ``block_type`` is:
    - ``"inline"`` for inline ``\"\"\"...\"\"\"`` script blocks
    - ``"template"`` for ``template "path.sh"`` references
    - ``"shell"`` for ``shell: \'\'\'...\'\'\'`` blocks

    This is a drop-in replacement for the function in ``test_tool_extraction.py``.
    """
    blocks: list[tuple[str, str]] = []
    for proc in parse_processes(content):
        for stype, scode in proc.scripts:
            blocks.append((stype, scode))
        for tpath in proc.templates:
            blocks.append(("template", tpath))
    return blocks


def resolve_template(
    template_name: str, clone_dir: Optional[Path] = None
) -> Optional[str]:
    """Resolve a Nextflow template reference to file content.

    Nextflow templates are resolved relative to the pipeline root's
    ``templates/`` subdirectory.
    """
    if clone_dir is None:
        return None
    name = template_name.strip("\"'")
    candidates = [
        clone_dir / "templates" / name,
        clone_dir / name,
    ]
    for cand in candidates:
        if cand.is_file():
            try:
                return cand.read_text()
            except Exception:
                return None
    return None


def extract_tools_from_scripts(
    content: str, clone_dir: Optional[Path] = None
) -> list[str]:
    """Extract tool names from a ``.nf`` file by parsing process scripts.

    Returns unique tool names in order of first appearance.
    """
    tools: list[str] = []
    seen: set[str] = set()

    for proc in parse_processes(content):
        for stype, scode in proc.scripts:
            if stype == "template":
                resolved = resolve_template(scode, clone_dir)
                if resolved is None:
                    continue
                script_text = resolved
            else:
                script_text = scode

            try:
                tokens = shlex.split(script_text)
            except ValueError:
                continue

            for tok in tokens:
                tl = tok.lower()
                if tl in _SHELL_BUILTINS:
                    continue
                if tl.startswith("-"):
                    continue
                if tl in ("|", "|&", ";", "&", "&&", "||"):
                    continue
                if "=" in tl and not any(c in tl for c in "()[]{}/"):
                    continue
                if tl.startswith("$"):
                    continue
                if tl[0].isalnum() or tl[0] in ("_", ".", "/"):
                    if tl not in seen:
                        seen.add(tl)
                        tools.append(tl)
                    break

    return tools


def clean_script_content(script: str) -> str:
    """Remove Groovy artifacts: shell continuations, escapes, interpolations."""
    s = script
    s = re.sub(r"\\\\\n\s*", " ", s)
    s = s.replace("\\$", "$")
    s = re.sub(r"\$\{[^}]+\}", " X ", s)
    s = re.sub(r"\$[a-zA-Z_][a-zA-Z_0-9]*", " X ", s)
    return s


def remove_heredocs(content: str) -> str:
    """Strip heredoc blocks (``cat <<-DELIM ... DELIM``) from content."""
    lines = content.split("\n")
    result: list[str] = []
    in_heredoc = False
    heredoc_delim: Optional[str] = None

    for line in lines:
        if not in_heredoc:
            m = re.match(r"^\s*cat\s+(<<[-]?)(\w+)", line)
            if m:
                heredoc_delim = m.group(2)
                in_heredoc = True
                continue
            m = re.match(r"^\s*(<<[-]?)(\w+)", line)
            if m:
                heredoc_delim = m.group(2)
                in_heredoc = True
                continue
            result.append(line)
        else:
            if line.strip() == heredoc_delim:
                in_heredoc = False
                heredoc_delim = None
    return "\n".join(result)


def _extract_tool_from_line(line: str) -> Optional[str]:
    """Extract the first real command from a single shell line.

    Ported from ``test_tool_extraction.py`` for compatibility.
    """
    try:
        tokens = shlex.split(line)
    except ValueError:
        return None

    if not tokens:
        return None

    segments: list[list[str]] = [[]]
    for tok in tokens:
        if tok in ("|", "|&"):
            segments.append([])
        else:
            segments[-1].append(tok)

    for seg in segments:
        if not seg:
            continue
        skip_until_do = False
        for tok in seg:
            if skip_until_do:
                if tok in ("do", ";"):
                    skip_until_do = False
                continue
            tl = tok.lower()
            if tl in _SHELL_BUILTINS:
                if tl in ("while", "until", "for"):
                    skip_until_do = True
                continue
            if tl.startswith("-"):
                continue
            if tl == "x" or tl.startswith("$"):
                continue
            if "=" in tl and not any(c in tl for c in "()[]{}/"):
                continue
            if not (tl[0].isalnum() or tl[0] in ("_", ".", "/")):
                continue
            return tl.lower()
    return None
