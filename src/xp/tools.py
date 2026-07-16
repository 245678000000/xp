"""Agent tools: bash, filesystem, search."""

from __future__ import annotations

import json
import os
import re
import subprocess
from pathlib import Path
from typing import Any, Callable, List, Optional, Tuple

from xp.diffutil import clip_diff, summarize_change, unified_diff
from xp.patch import apply_patch_text

# Hard block when not yolo
_BLOCKED = re.compile(
    r"""(?ix)
    \brm\s+(-[a-z]*r[a-z]*f|-[a-z]*f[a-z]*r)\b.*(/|~|\*)
    |\bmkfs\b
    |\bdd\s+if=
    |\b(shutdown|reboot|halt)\b
    |\bcurl\b.*\|\s*(ba)?sh
    |\bwget\b.*\|\s*(ba)?sh
    |\bgit\s+push\s+.*--force
    |\bgit\s+reset\s+--hard\b
    """
)

# Needs interactive confirm when confirm_risky and not yolo
_RISKY = re.compile(
    r"""(?ix)
    \brm\s+
    |\bsudo\b
    |\bgit\s+push\b
    |\bgit\s+clean\b
    |\bchmod\s+-R\b
    |\bchown\s+-R\b
    |\bkill\s+-9\b
    |\bmkfs\b
    |\bdd\s+
    |\b>\s*/dev/
    """
)

TOOL_DEFS: list[dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "bash",
            "description": "Run a shell command in the workspace. Prefer non-interactive flags.",
            "parameters": {
                "type": "object",
                "properties": {
                    "command": {"type": "string", "description": "Shell command to run"},
                    "timeout": {
                        "type": "integer",
                        "description": "Timeout seconds (default 120)",
                    },
                },
                "required": ["command"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "Read a text file. Optional start_line/end_line (1-based inclusive).",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string"},
                    "start_line": {"type": "integer"},
                    "end_line": {"type": "integer"},
                },
                "required": ["path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "write_file",
            "description": "Create or overwrite a text file with full contents.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string"},
                    "content": {"type": "string"},
                },
                "required": ["path", "content"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "str_replace",
            "description": "Replace exact old_string with new_string in a file (once by default).",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string"},
                    "old_string": {"type": "string"},
                    "new_string": {"type": "string"},
                    "replace_all": {"type": "boolean"},
                },
                "required": ["path", "old_string", "new_string"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "apply_patch",
            "description": (
                "Apply a multi-hunk patch. Prefer this over write_file for surgical edits. "
                "Formats: (1) freeform *** Begin Patch / *** Update File: path / @@ hunks "
                "with ' ' context, '-' remove, '+' add; (2) unified diff (--- / +++ / @@)."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "patch": {
                        "type": "string",
                        "description": "Full patch text",
                    },
                },
                "required": ["patch"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_dir",
            "description": "List files and directories under a path.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Directory path (default .)"},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "grep",
            "description": "Search file contents with a regex (ripgrep if available, else recursive Python).",
            "parameters": {
                "type": "object",
                "properties": {
                    "pattern": {"type": "string"},
                    "path": {"type": "string", "description": "File or directory (default .)"},
                    "glob": {"type": "string", "description": "Optional glob filter e.g. *.py"},
                    "max_matches": {"type": "integer"},
                },
                "required": ["pattern"],
            },
        },
    },
]

WEB_TOOL_DEFS: list[dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "fetch_url",
            "description": "Fetch a public http(s) URL and return text content (HTML stripped).",
            "parameters": {
                "type": "object",
                "properties": {
                    "url": {"type": "string"},
                    "max_chars": {"type": "integer", "description": "Max characters (default 20000)"},
                },
                "required": ["url"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "web_search",
            "description": "Search the public web (DuckDuckGo, no API key). Returns titles, URLs, snippets.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string"},
                    "max_results": {"type": "integer", "description": "1-10, default 5"},
                },
                "required": ["query"],
            },
        },
    },
]

SPAWN_TOOL_DEF: dict[str, Any] = {
    "type": "function",
    "function": {
        "name": "spawn_task",
        "description": (
            "Run a short read-only sub-investigation in a fresh context "
            "(list/read/grep/bash read-only). Returns a summary. Use for parallel research."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "goal": {"type": "string", "description": "What to investigate"},
                "max_turns": {"type": "integer", "description": "Max tool loop turns (default 6)"},
            },
            "required": ["goal"],
        },
    },
}

READ_ONLY_TOOL_NAMES = frozenset({"bash", "read_file", "list_dir", "grep", "fetch_url", "web_search"})


def get_tool_defs(
    *,
    enable_web: bool = False,
    enable_spawn: bool = True,
    read_only: bool = False,
) -> list[dict[str, Any]]:
    if read_only:
        names = {"bash", "read_file", "list_dir", "grep"}
        if enable_web:
            names |= {"fetch_url", "web_search"}
        defs = [t for t in TOOL_DEFS if t["function"]["name"] in names]
        if enable_web:
            defs = defs + WEB_TOOL_DEFS
        return defs
    defs = list(TOOL_DEFS)
    if enable_web:
        defs = defs + WEB_TOOL_DEFS
    if enable_spawn:
        defs = defs + [SPAWN_TOOL_DEF]
    return defs


class ToolRuntime:
    def __init__(
        self,
        cwd: Path,
        *,
        yolo: bool = False,
        sandbox: bool = True,
        confirm_risky: bool = True,
        confirm_fn: Optional[Callable[[str], bool]] = None,
        enable_web: bool = False,
        spawn_task_fn: Optional[Callable[..., str]] = None,
        read_only: bool = False,
        mcp_call: Optional[Callable[..., str]] = None,
    ) -> None:
        self.cwd = cwd.resolve()
        self.yolo = yolo
        self.sandbox = sandbox and not yolo
        self.confirm_risky = confirm_risky and not yolo
        self.confirm_fn = confirm_fn
        self.enable_web = enable_web
        self.spawn_task_fn = spawn_task_fn
        self.read_only = read_only
        self.mcp_call = mcp_call
        # Populated by mutating file tools for UI colored diffs
        self.last_diffs: List[Tuple[str, str]] = []

    def resolve(self, path: str, *, write: bool = False) -> Path:
        p = Path(path).expanduser()
        if not p.is_absolute():
            p = self.cwd / p
        p = p.resolve()
        if self.sandbox:
            try:
                p.relative_to(self.cwd)
            except ValueError:
                kind = "write" if write else "access"
                raise PermissionError(
                    f"sandbox: refusing {kind} outside workspace ({self.cwd}): {p}. "
                    "Pass --allow-outside or set sandbox=false / yolo=true."
                )
        return p

    def run(self, name: str, arguments: dict[str, Any] | str) -> str:
        self.last_diffs = []
        if self.read_only and name not in READ_ONLY_TOOL_NAMES:
            return f"error: tool {name} disabled in read-only spawn_task"
        if isinstance(arguments, str):
            try:
                arguments = json.loads(arguments) if arguments else {}
            except json.JSONDecodeError:
                return f"error: invalid JSON arguments: {arguments[:200]}"
        # MCP tools: mcp__server__toolname
        if name.startswith("mcp__") and self.mcp_call is not None:
            try:
                return self.mcp_call(name, arguments)
            except Exception as e:  # noqa: BLE001
                return f"error: MCP {type(e).__name__}: {e}"
        handler: Callable[..., str] | None = getattr(self, f"tool_{name}", None)
        if handler is None:
            return f"error: unknown tool {name}"
        try:
            return handler(**arguments)
        except TypeError as e:
            return f"error: bad arguments for {name}: {e}"
        except PermissionError as e:
            return f"error: {e}"
        except Exception as e:  # noqa: BLE001
            return f"error: {type(e).__name__}: {e}"

    def _record_diff(self, rel_path: str, old: str, new: str) -> str:
        diff = unified_diff(rel_path, old, new)
        if diff:
            self.last_diffs.append((rel_path, diff))
        created = old == "" and new != ""
        summary = summarize_change(rel_path, None if created else old, new)
        if not diff:
            return summary
        return f"{summary}\n\n{clip_diff(diff)}"

    def tool_bash(self, command: str, timeout: int = 120) -> str:
        if not self.yolo and _BLOCKED.search(command):
            return (
                "error: command blocked by safety policy. "
                "Re-run with --yolo if you really need it (destructive)."
            )
        if self.confirm_risky and _RISKY.search(command):
            ok = False
            if self.confirm_fn is not None:
                ok = self.confirm_fn(f"Risky bash: {command}\nAllow?")
            if not ok:
                return (
                    "error: risky command not confirmed by user "
                    "(rm/sudo/git push/…). Use --yolo to skip confirms."
                )
        try:
            proc = subprocess.run(
                command,
                shell=True,
                cwd=self.cwd,
                capture_output=True,
                text=True,
                timeout=max(1, int(timeout)),
                env=os.environ.copy(),
            )
        except subprocess.TimeoutExpired:
            return f"error: timed out after {timeout}s"
        out = []
        if proc.stdout:
            out.append(proc.stdout)
        if proc.stderr:
            out.append(f"[stderr]\n{proc.stderr}")
        out.append(f"[exit {proc.returncode}]")
        text = "\n".join(out)
        if len(text) > 80_000:
            text = text[:40_000] + "\n...\n[truncated]\n...\n" + text[-20_000:]
        return text

    def tool_read_file(
        self,
        path: str,
        start_line: int | None = None,
        end_line: int | None = None,
    ) -> str:
        p = self.resolve(path)
        if not p.is_file():
            return f"error: not a file: {p}"
        try:
            lines = p.read_text(encoding="utf-8", errors="replace").splitlines()
        except OSError as e:
            return f"error: {e}"
        if start_line is None and end_line is None:
            numbered = [f"{i + 1:>5}|{line}" for i, line in enumerate(lines)]
            text = "\n".join(numbered)
            if len(text) > 100_000:
                return text[:100_000] + "\n...[truncated]"
            return text or "(empty file)"
        start = max(1, start_line or 1)
        end = min(len(lines), end_line or len(lines))
        chunk = lines[start - 1 : end]
        return "\n".join(f"{i + start:>5}|{line}" for i, line in enumerate(chunk)) or "(empty)"

    def tool_write_file(self, path: str, content: str) -> str:
        p = self.resolve(path, write=True)
        old = p.read_text(encoding="utf-8") if p.is_file() else ""
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")
        rel = path
        try:
            rel = str(p.relative_to(self.cwd))
        except ValueError:
            rel = str(p)
        return self._record_diff(rel, old, content)

    def tool_str_replace(
        self,
        path: str,
        old_string: str,
        new_string: str,
        replace_all: bool = False,
    ) -> str:
        p = self.resolve(path, write=True)
        if not p.is_file():
            return f"error: not a file: {p}"
        text = p.read_text(encoding="utf-8")
        count = text.count(old_string)
        if count == 0:
            return "error: old_string not found"
        if count > 1 and not replace_all:
            return f"error: old_string found {count} times; set replace_all=true or make it unique"
        new_text = (
            text.replace(old_string, new_string)
            if replace_all
            else text.replace(old_string, new_string, 1)
        )
        p.write_text(new_text, encoding="utf-8")
        rel = path
        try:
            rel = str(p.relative_to(self.cwd))
        except ValueError:
            rel = str(p)
        n = count if replace_all else 1
        body = self._record_diff(rel, text, new_text)
        return f"{n} replacement(s)\n{body}"

    def tool_apply_patch(self, patch: str) -> str:
        def _resolve(rel: str) -> Path:
            return self.resolve(rel, write=True)

        def _read(p: Path) -> str:
            return p.read_text(encoding="utf-8") if p.is_file() else ""

        def _write(p: Path, content: str) -> None:
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(content, encoding="utf-8")

        result = apply_patch_text(patch, resolve=_resolve, read_text=_read, write_text=_write)
        if not result.ok:
            return result.message
        parts = [result.message]
        for rel, old, new in result.diffs:
            parts.append(self._record_diff(rel, old, new))
        return "\n\n".join(parts)

    def tool_list_dir(self, path: str = ".") -> str:
        p = self.resolve(path)
        if not p.is_dir():
            return f"error: not a directory: {p}"
        entries = sorted(p.iterdir(), key=lambda x: (not x.is_dir(), x.name.lower()))
        lines = []
        for e in entries[:500]:
            suffix = "/" if e.is_dir() else ""
            lines.append(f"{e.name}{suffix}")
        if len(entries) > 500:
            lines.append(f"... and {len(entries) - 500} more")
        return "\n".join(lines) or "(empty)"

    def tool_grep(
        self,
        pattern: str,
        path: str = ".",
        glob: str | None = None,
        max_matches: int = 50,
    ) -> str:
        p = self.resolve(path)
        max_matches = max(1, min(int(max_matches), 200))
        if _which("rg"):
            cmd = ["rg", "-n", "--no-heading", "-m", str(max_matches), pattern]
            if glob:
                cmd.extend(["-g", glob])
            cmd.append(str(p))
            proc = subprocess.run(cmd, capture_output=True, text=True, cwd=self.cwd)
            if proc.returncode not in (0, 1):
                return proc.stderr or f"rg exit {proc.returncode}"
            return proc.stdout or "(no matches)"

        try:
            rx = re.compile(pattern)
        except re.error as e:
            return f"error: invalid regex: {e}"
        matches: list[str] = []
        files: list[Path]
        if p.is_file():
            files = [p]
        else:
            files = list(p.rglob(glob or "*")) if p.is_dir() else []
        for f in files:
            if not f.is_file():
                continue
            if any(part.startswith(".git") for part in f.parts):
                continue
            try:
                for i, line in enumerate(
                    f.read_text(encoding="utf-8", errors="replace").splitlines(), 1
                ):
                    if rx.search(line):
                        matches.append(f"{f}:{i}:{line}")
                        if len(matches) >= max_matches:
                            return "\n".join(matches)
            except OSError:
                continue
        return "\n".join(matches) or "(no matches)"

    def tool_fetch_url(self, url: str, max_chars: int = 20_000) -> str:
        if not self.enable_web:
            return "error: web tools disabled (set enable_web=true or pass --web)"
        from xp.web import fetch_url

        return fetch_url(url, max_chars=int(max_chars))

    def tool_web_search(self, query: str, max_results: int = 5) -> str:
        if not self.enable_web:
            return "error: web tools disabled (set enable_web=true or pass --web)"
        from xp.web import web_search

        return web_search(query, max_results=int(max_results))

    def tool_spawn_task(self, goal: str, max_turns: int = 6) -> str:
        if self.spawn_task_fn is None:
            return "error: spawn_task not available"
        if self.read_only:
            return "error: nested spawn_task not allowed"
        return self.spawn_task_fn(goal=goal, max_turns=int(max_turns))


def _which(name: str) -> str | None:
    from shutil import which

    return which(name)
