"""Nextflow version resolution and detection utilities."""

import re
import subprocess

from packaging.specifiers import InvalidSpecifier, SpecifierSet
from packaging.version import Version

NXF_ANTLR4_THRESHOLD = (24, 0, 0)
PREVIEW_MIN_VERSION = (22, 0, 0)  # -preview flag added in NF 22.04.0
JAVA17_MAX_VERSION = (22, 10, 99)  # NF <= 22.10.x needs Java <= 17


# Hardcoded list of Nextflow releases for NXF_VER resolution.
# Source: https://github.com/nextflow-io/nextflow/releases
NFX_VERSIONS = [
    "0.3.0",
    "0.3.1",
    "0.3.2",
    "0.3.3",
    "0.3.4",
    "0.5.1",
    "0.5.4",
    "0.6.0",
    "0.6.1",
    "0.6.2",
    "0.7.0",
    "0.7.1",
    "0.7.2",
    "0.7.3",
    "0.8.0",
    "0.8.1",
    "0.8.2",
    "0.8.3",
    "0.8.4",
    "0.8.5",
    "0.9.0",
    "0.10.0",
    "0.10.1",
    "0.10.3",
    "0.11.0",
    "0.11.1",
    "0.11.2",
    "0.11.3",
    "0.11.4",
    "0.12.0",
    "0.12.1",
    "0.12.2",
    "0.12.3",
    "0.12.4",
    "0.12.5",
    "0.13.0",
    "0.13.1",
    "0.13.2",
    "0.13.3",
    "0.13.4",
    "0.13.5",
    "0.14.0",
    "0.14.1",
    "0.14.2",
    "0.14.3",
    "0.14.4",
    "0.15.0",
    "0.15.1",
    "0.15.2",
    "0.15.3",
    "0.15.4",
    "0.15.5",
    "0.15.6",
    "0.16.0",
    "0.16.1",
    "0.16.2",
    "0.16.3",
    "0.16.4",
    "0.16.5",
    "0.17.0",
    "0.17.1",
    "0.17.2",
    "0.17.3",
    "0.18.0",
    "0.18.1",
    "0.18.2",
    "0.18.3",
    "0.19.0",
    "0.19.1",
    "0.19.2",
    "0.19.3",
    "0.19.4",
    "0.20.0",
    "0.20.1",
    "0.21.0",
    "0.21.1",
    "0.21.2",
    "0.21.3",
    "0.22.0",
    "0.22.1",
    "0.22.2",
    "0.22.3",
    "0.22.4",
    "0.22.5",
    "0.22.6",
    "0.23.0",
    "0.23.1",
    "0.23.2",
    "0.23.3",
    "0.23.4",
    "0.24.0",
    "0.24.1",
    "0.24.2",
    "0.24.3",
    "0.24.4",
    "0.25.0",
    "0.25.1",
    "0.25.2",
    "0.25.3",
    "0.25.4",
    "0.25.5",
    "0.25.6",
    "0.25.7",
    "0.26.0",
    "0.26.1",
    "0.26.2",
    "0.26.3",
    "0.26.4",
    "0.27.0",
    "0.27.1",
    "0.27.2",
    "0.27.3",
    "0.27.4",
    "0.27.5",
    "0.27.6",
    "0.28.0",
    "0.28.1",
    "0.28.2",
    "0.29.0",
    "0.29.1",
    "0.30.0",
    "0.30.1",
    "0.30.2",
    "0.31.0",
    "0.31.1",
    "0.32.0",
    "18.10.1",
    "19.01.0",
    "19.04.0",
    "19.04.1",
    "19.07.0",
    "19.10.0",
    "20.01.0",
    "20.04.1",
    "20.07.1",
    "20.10.0",
    "21.04.0",
    "21.04.1",
    "21.04.2",
    "21.04.3",
    "21.10.0",
    "21.10.1",
    "21.10.2",
    "21.10.3",
    "21.10.4",
    "21.10.5",
    "21.10.6",
    "22.04.0",
    "22.04.1",
    "22.04.2",
    "22.04.3",
    "22.04.4",
    "22.04.5",
    "22.10.0",
    "22.10.1",
    "22.10.2",
    "22.10.3",
    "22.10.4",
    "22.10.5",
    "22.10.6",
    "22.10.7",
    "22.10.8",
    "23.04.0",
    "23.04.1",
    "23.04.2",
    "23.04.3",
    "23.04.4",
    "23.04.5",
    "23.10.0",
    "23.10.1",
    "23.10.2",
    "23.10.3",
    "23.10.4",
    "24.04.0",
    "24.04.1",
    "24.04.2",
    "24.04.3",
    "24.04.4",
    "24.04.5",
    "24.04.6",
    "24.10.0",
    "24.10.1",
    "24.10.2",
    "24.10.3",
    "24.10.4",
    "24.10.5",
    "24.10.6",
    "24.10.8",
    "24.10.9",
    "25.04.0",
    "25.04.1",
    "25.04.2",
    "25.04.3",
    "25.04.4",
    "25.04.5",
    "25.04.6",
    "25.04.7",
    "25.04.8",
    "25.10.0",
    "25.10.1",
    "25.10.2",
    "25.10.3",
    "25.10.4",
    "25.10.5",
    "25.10.6",
    "26.04.0",
    "26.04.1",
    "26.04.2",
    "26.04.3",
    "26.04.4",
]

_SEMVER = re.compile(r"(\d+\.\d+\.\d+)")


def _parse_version(v):
    parts = v.split(".")
    return tuple(int(p) for p in parts[:3])


def needs_groovy_parser(version_str):
    """Return True if *version_str* requires the Groovy (v1) parser."""
    if not version_str:
        return False
    try:
        return _parse_version(version_str) < NXF_ANTLR4_THRESHOLD
    except (ValueError, IndexError):
        return False


def supports_preview(version_str):
    """Return True if *version_str* supports the -preview flag (NF >= 22.04.0)."""
    if not version_str:
        return False
    try:
        return _parse_version(version_str) >= PREVIEW_MIN_VERSION
    except (ValueError, IndexError):
        return False


def needs_java17(version_str):
    """Return True if *version_str* requires Java <= 17 (NF <= 22.10.x)."""
    if not version_str:
        return False
    try:
        return _parse_version(version_str) <= JAVA17_MAX_VERSION
    except (ValueError, IndexError):
        return False


def _pick(candidates, operator):
    """Select a version from sorted candidates based on the operator.

    - >= / >  → newest (latest satisfying)
    - <= / <  → newest (latest satisfying)
    - ==      → exact (mid, since all are equal)
    - !=      → mid (exclusion — pick middle of everything else)
    - ~=      → newest (compatible release, has implicit upper bound)
    """
    if not candidates:
        return None
    if operator in (">=", ">", "<=", "<", "~="):
        return candidates[-1]
    if operator in ("<=", "<", "~="):
        return candidates[-1]
    return candidates[len(candidates) // 2]


def resolve_nfx_version(raw_constraint):
    """Resolve a version constraint against NFX_VERSIONS.

    Accepts PEP 440 specifiers (>=X, <=X, ==X, !=X, ~=X, >X, <X),
    bare versions (treated as >=X), or None (no pinning).

    Selection policy:
      - Single >=X / >X / <=X / <X / ~=X  → newest satisfying version
      - Combined (e.g. >=X,<Y)            → newest satisfying version
      - ==X, !=X                          → mid

    Returns a version string from NFX_VERSIONS, or None if no match.
    """
    if not raw_constraint:
        return None
    raw = raw_constraint.strip()

    PEP440_OPS = (">=", "<=", "==", "!=", "~=", ">", "<")
    try:
        if any(raw.startswith(op) for op in PEP440_OPS):
            spec = SpecifierSet(raw)
        else:
            spec = SpecifierSet(f">={raw}")
    except (InvalidSpecifier, ValueError):
        return None

    candidates = [v for v in NFX_VERSIONS if Version(v) in spec]
    if not candidates:
        return None

    # Prefer the newest version below 26.0.0 to avoid NF 26.x regressions
    # (config parsing, GPars API removal). Only use 26.x when the
    # constraint cannot be satisfied by any pre-26 release.
    pre_26 = [v for v in candidates if Version(v) < Version("26.0.0")]
    pool = pre_26 if pre_26 else candidates

    # Single specifier → edge policy; combined → newest within range
    specs = list(spec)
    if len(specs) == 1:
        return _pick(pool, specs[0].operator)
    return pool[-1]


def get_system_nfx_version():
    """Return the installed Nextflow version string, or None."""
    try:
        out = subprocess.check_output(
            ["nextflow", "-version"], stderr=subprocess.STDOUT, text=True, timeout=15
        )
        for line in out.splitlines():
            if "version" in line:
                parts = line.strip().split()
                for p in parts:
                    if p[0].isdigit():
                        return p
    except Exception:
        pass
    return None
