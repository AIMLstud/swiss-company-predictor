"""
Swiss UID format conversions.

Zefix API uses compact form:   CHE107251578
HR-Auszug URL uses formatted:  CHE-107.251.578
"""

import re

_COMPACT_RE = re.compile(r"^(CHE)(\d{3})(\d{3})(\d{3})$")
_FORMATTED_RE = re.compile(r"^(CHE)-(\d{3})\.(\d{3})\.(\d{3})$")


def compact_to_formatted(uid: str) -> str:
    """CHE107251578 → CHE-107.251.578"""
    m = _COMPACT_RE.match(uid)
    if not m:
        raise ValueError(f"Invalid compact UID: {uid!r}")
    return f"{m.group(1)}-{m.group(2)}.{m.group(3)}.{m.group(4)}"


def formatted_to_compact(uid: str) -> str:
    """CHE-107.251.578 → CHE107251578"""
    m = _FORMATTED_RE.match(uid)
    if not m:
        raise ValueError(f"Invalid formatted UID: {uid!r}")
    return f"{m.group(1)}{m.group(2)}{m.group(3)}{m.group(4)}"
