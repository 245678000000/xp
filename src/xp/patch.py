"""Apply unified / freeform patches to workspace files."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, List, Optional, Tuple


@dataclass
class PatchResult:
    ok: bool
    message: str
    diffs: List[Tuple[str, str, str]]  # path, old, new


def apply_patch_text(
    patch_text: str,
    *,
    resolve: Callable[[str], Path],
    read_text: Callable[[Path], str],
    write_text: Callable[[Path, str], None],
) -> PatchResult:
    """
    Accept either:
    1) Freeform blocks:
       *** Begin Patch
       *** Update File: path
       @@
        context
       -old
       +new
       *** End Patch

    2) Standard unified diff with --- a/path / +++ b/path / @@ hunks
    """
    text = patch_text.strip()
    if not text:
        return PatchResult(False, "error: empty patch", [])

    if "*** Begin Patch" in text or "*** Update File:" in text or "*** Add File:" in text:
        return _apply_freeform(text, resolve=resolve, read_text=read_text, write_text=write_text)
    if re.search(r"^---\s+", text, re.M) and re.search(r"^\+\+\+\s+", text, re.M):
        return _apply_unified(text, resolve=resolve, read_text=read_text, write_text=write_text)
    return PatchResult(
        False,
        "error: unrecognized patch format. Use *** Begin Patch / *** Update File: "
        "or unified diff (--- / +++ / @@).",
        [],
    )


def _apply_freeform(
    text: str,
    *,
    resolve: Callable[[str], Path],
    read_text: Callable[[Path], str],
    write_text: Callable[[Path, str], None],
) -> PatchResult:
    # Strip begin/end wrappers
    text = re.sub(r"^\*\*\*\s*Begin Patch\s*$", "", text, flags=re.M)
    text = re.sub(r"^\*\*\*\s*End Patch\s*$", "", text, flags=re.M)

    file_re = re.compile(
        r"^\*\*\*\s*(Update|Add|Delete)\s+File:\s*(.+?)\s*$",
        re.M | re.I,
    )
    matches = list(file_re.finditer(text))
    if not matches:
        return PatchResult(False, "error: no *** Update/Add/Delete File: headers found", [])

    diffs: List[Tuple[str, str, str]] = []
    messages: List[str] = []

    for i, m in enumerate(matches):
        action = m.group(1).lower()
        rel = m.group(2).strip()
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        body = text[start:end].strip("\n")
        path = resolve(rel)

        if action == "delete":
            old = read_text(path) if path.is_file() else ""
            if path.is_file():
                path.unlink()
            diffs.append((rel, old, ""))
            messages.append(f"deleted {rel}")
            continue

        if action == "add":
            # body lines may be prefixed with +
            content = _strip_plus_block(body)
            if path.exists():
                return PatchResult(False, f"error: add file exists: {rel}", diffs)
            path.parent.mkdir(parents=True, exist_ok=True)
            write_text(path, content)
            diffs.append((rel, "", content))
            messages.append(f"added {rel}")
            continue

        # update
        if not path.is_file():
            return PatchResult(False, f"error: update target missing: {rel}", diffs)
        old = read_text(path)
        new, err = _apply_hunks_to_text(old, body)
        if err:
            return PatchResult(False, f"error: {rel}: {err}", diffs)
        write_text(path, new)
        diffs.append((rel, old, new))
        messages.append(f"updated {rel}")

    return PatchResult(True, "; ".join(messages), diffs)


def _strip_plus_block(body: str) -> str:
    lines = []
    for line in body.splitlines():
        if line.startswith("+"):
            lines.append(line[1:])
        elif line.startswith("***"):
            continue
        elif line.startswith("@@"):
            continue
        else:
            # allow raw content without prefix
            if line.startswith("-"):
                continue
            lines.append(line)
    return "\n".join(lines) + ("\n" if body.endswith("\n") or lines else "")


def _apply_hunks_to_text(original: str, body: str) -> Tuple[Optional[str], Optional[str]]:
    """
    Apply one or more @@ hunks. Each hunk uses:
      space = context, - = remove, + = add
    If no @@ headers, treat whole body as a single hunk.
    """
    hunks = _split_hunks(body)
    text = original
    # Work line-oriented without requiring keepends consistency
    for hunk in hunks:
        text, err = _apply_one_hunk(text, hunk)
        if err:
            return None, err
    return text, None


def _split_hunks(body: str) -> List[List[str]]:
    lines = body.splitlines()
    if not any(l.startswith("@@") for l in lines):
        return [lines] if lines else []
    hunks: List[List[str]] = []
    cur: List[str] = []
    for line in lines:
        if line.startswith("@@"):
            if cur:
                hunks.append(cur)
            cur = []
            continue
        if line.startswith("***"):
            continue
        cur.append(line)
    if cur:
        hunks.append(cur)
    return hunks


def _apply_one_hunk(text: str, hunk_lines: List[str]) -> Tuple[Optional[str], Optional[str]]:
    old_block: List[str] = []
    new_block: List[str] = []
    for line in hunk_lines:
        if line.startswith("\\"):
            continue
        if not line:
            # blank line as context only if we already have content
            if old_block or new_block:
                old_block.append("")
                new_block.append("")
            continue
        tag, rest = line[0], line[1:]
        if tag == " ":
            old_block.append(rest)
            new_block.append(rest)
        elif tag == "-":
            old_block.append(rest)
        elif tag == "+":
            new_block.append(rest)
        elif tag == "@":
            continue
        else:
            # bare context without prefix
            old_block.append(line)
            new_block.append(line)

    old_s = "\n".join(old_block)
    new_s = "\n".join(new_block)

    # Try exact match first
    if old_s and old_s in text:
        return text.replace(old_s, new_s, 1), None

    # Try line-list sliding window (ignore trailing whitespace)
    src_lines = text.splitlines()
    old_lines = old_block
    if not old_lines:
        # pure insert at EOF
        if text and not text.endswith("\n"):
            text += "\n"
        return text + new_s + ("\n" if new_s and not new_s.endswith("\n") else ""), None

    n = len(old_lines)
    for i in range(0, len(src_lines) - n + 1):
        window = src_lines[i : i + n]
        if all(a.rstrip() == b.rstrip() for a, b in zip(window, old_lines)):
            out = src_lines[:i] + new_block + src_lines[i + n :]
            result = "\n".join(out)
            if text.endswith("\n"):
                result += "\n"
            return result, None

    preview = old_s[:120].replace("\n", "\\n")
    return None, f"hunk context not found: {preview!r}"


def _apply_unified(
    text: str,
    *,
    resolve: Callable[[str], Path],
    read_text: Callable[[Path], str],
    write_text: Callable[[Path, str], None],
) -> PatchResult:
    """Minimal multi-file unified diff applier."""
    file_chunks = re.split(r"(?=^---\s+)", text, flags=re.M)
    diffs: List[Tuple[str, str, str]] = []
    messages: List[str] = []

    for chunk in file_chunks:
        chunk = chunk.strip()
        if not chunk.startswith("---"):
            continue
        m_old = re.match(r"^---\s+(\S+)", chunk, re.M)
        m_new = re.search(r"^\+\+\+\s+(\S+)", chunk, re.M)
        if not m_old or not m_new:
            return PatchResult(False, "error: malformed unified diff headers", diffs)
        old_name = m_old.group(1)
        new_name = m_new.group(1)
        # strip a/ b/ prefixes
        rel = new_name[2:] if new_name.startswith("b/") else new_name
        if rel == "/dev/null":
            rel = old_name[2:] if old_name.startswith("a/") else old_name
            path = resolve(rel)
            old = read_text(path) if path.is_file() else ""
            if path.is_file():
                path.unlink()
            diffs.append((rel, old, ""))
            messages.append(f"deleted {rel}")
            continue

        rel = rel if not rel.startswith("b/") else rel[2:]
        path = resolve(rel)
        is_new = old_name.endswith("/dev/null") or old_name == "/dev/null"
        old = "" if is_new or not path.is_file() else read_text(path)

        # Extract from first @@
        idx = chunk.find("\n@@")
        if idx < 0:
            idx = chunk.find("@@")
        body = chunk[idx:] if idx >= 0 else ""
        # Convert unified body: keep @@ separated hunks with -+ 
        # Remove the +++ --- header lines from body already cut
        body_lines = []
        for line in body.splitlines():
            if line.startswith("---") or line.startswith("+++"):
                continue
            body_lines.append(line)
        new, err = _apply_hunks_to_text(old, "\n".join(body_lines))
        if err:
            return PatchResult(False, f"error: {rel}: {err}", diffs)
        assert new is not None
        path.parent.mkdir(parents=True, exist_ok=True)
        write_text(path, new)
        diffs.append((rel, old, new))
        messages.append(f"{'created' if is_new else 'updated'} {rel}")

    if not messages:
        return PatchResult(False, "error: no file hunks in unified diff", [])
    return PatchResult(True, "; ".join(messages), diffs)
