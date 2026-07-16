"""Unified diffs and colored previews."""

from __future__ import annotations

import difflib
from typing import List, Optional, Tuple


def unified_diff(
    path: str,
    old: str,
    new: str,
    *,
    context: int = 3,
) -> str:
    old_lines = old.splitlines(keepends=True)
    new_lines = new.splitlines(keepends=True)
    if old and not old.endswith("\n") and old_lines:
        old_lines[-1] += "\n"
    if new and not new.endswith("\n") and new_lines:
        new_lines[-1] += "\n"
    lines = list(
        difflib.unified_diff(
            old_lines,
            new_lines,
            fromfile=f"a/{path}",
            tofile=f"b/{path}",
            n=context,
        )
    )
    if not lines:
        return ""
    return "".join(lines).rstrip("\n")


def format_diff_for_terminal(diff_text: str) -> List[Tuple[str, str]]:
    """
    Return list of (style, line) for rich printing.
    style: green | red | cyan | dim | bold
    """
    rows: List[Tuple[str, str]] = []
    if not diff_text.strip():
        return rows
    for line in diff_text.splitlines():
        if line.startswith("+++") or line.startswith("---"):
            rows.append(("bold", line))
        elif line.startswith("@@"):
            rows.append(("cyan", line))
        elif line.startswith("+"):
            rows.append(("green", line))
        elif line.startswith("-"):
            rows.append(("red", line))
        else:
            rows.append(("dim", line))
    return rows


def clip_diff(diff_text: str, max_lines: int = 80) -> str:
    lines = diff_text.splitlines()
    if len(lines) <= max_lines:
        return diff_text
    head = lines[: max_lines - 1]
    return "\n".join(head) + f"\n… ({len(lines) - max_lines + 1} more lines)"


def summarize_change(path: str, old: Optional[str], new: str) -> str:
    if old is None:
        n = len(new.splitlines())
        return f"created {path} ({n} lines)"
    if old == new:
        return f"no change {path}"
    old_n, new_n = len(old.splitlines()), len(new.splitlines())
    return f"updated {path} ({old_n} → {new_n} lines)"
