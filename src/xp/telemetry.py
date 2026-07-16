"""
Opt-in telemetry (default OFF).

Privacy defaults:
- Disabled unless enable_telemetry=true or XP_TELEMETRY=1
- Local JSONL only by default (~/.local/share/xp/telemetry/)
- Never logs prompts, file contents, secrets, or full tool arguments
- Optional webhook: POST anonymized counters only (no content)
"""

from __future__ import annotations

import hashlib
import json
import os
import time
import uuid
from pathlib import Path
from typing import Any, Dict, Optional

import httpx

from xp import __version__


def telemetry_dir() -> Path:
    if env := os.environ.get("XP_TELEMETRY_DIR"):
        return Path(env).expanduser()
    xdg = os.environ.get("XDG_DATA_HOME")
    if xdg:
        return Path(xdg) / "xp" / "telemetry"
    return Path.home() / ".local" / "share" / "xp" / "telemetry"


def install_id_path() -> Path:
    return telemetry_dir() / "install_id"


def get_install_id() -> str:
    path = install_id_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.is_file():
        return path.read_text(encoding="utf-8").strip() or _new_id(path)
    return _new_id(path)


def _new_id(path: Path) -> str:
    val = uuid.uuid4().hex
    path.write_text(val, encoding="utf-8")
    return val


def _anon_cwd(cwd: str) -> str:
    """Stable non-reversible workspace id (not the real path)."""
    return hashlib.sha256(cwd.encode("utf-8")).hexdigest()[:16]


class Telemetry:
    def __init__(
        self,
        *,
        enabled: bool = False,
        endpoint: str = "",
        session_id: Optional[str] = None,
        model: str = "",
        backend: str = "",
        cwd: str = "",
    ) -> None:
        self.enabled = enabled
        self.endpoint = (endpoint or "").strip()
        self.session_id = session_id or time.strftime("%Y%m%d-%H%M%S")
        self.model = model
        self.backend = backend
        self.cwd_hash = _anon_cwd(cwd) if cwd else ""
        self.install_id = get_install_id() if enabled else ""
        self.path = telemetry_dir() / f"{self.session_id}.jsonl"
        self.counters: Dict[str, int] = {
            "turns": 0,
            "tool_calls": 0,
            "sessions": 0,
            "prompt_tokens": 0,
            "completion_tokens": 0,
        }
        self._tool_hist: Dict[str, int] = {}

    def emit(self, event: str, **fields: Any) -> None:
        if not self.enabled:
            return
        row = {
            "ts": time.time(),
            "event": event,
            "xp_version": __version__,
            "install_id": self.install_id,
            "session_id": self.session_id,
            "model": self.model,
            "backend": self.backend,
            "cwd_hash": self.cwd_hash,
            **fields,
        }
        # Strip any accidental sensitive keys
        for banned in ("api_key", "prompt", "content", "arguments", "result", "path"):
            row.pop(banned, None)

        telemetry_dir().mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")

        if self.endpoint.startswith("http"):
            self._post_webhook(row)

    def _post_webhook(self, row: dict[str, Any]) -> None:
        try:
            with httpx.Client(timeout=5.0) as client:
                client.post(self.endpoint, json=row)
        except Exception:
            # Never break the agent for telemetry failures
            pass

    def session_start(self) -> None:
        self.counters["sessions"] += 1
        self.emit("session_start")

    def session_end(self, usage: Optional[dict[str, int]] = None) -> None:
        if usage:
            self.counters["prompt_tokens"] += int(usage.get("prompt_tokens") or 0)
            self.counters["completion_tokens"] += int(usage.get("completion_tokens") or 0)
        self.emit(
            "session_end",
            counters=dict(self.counters),
            tools=dict(self._tool_hist),
        )

    def turn(self) -> None:
        self.counters["turns"] += 1
        self.emit("turn", turn=self.counters["turns"])

    def tool(self, name: str) -> None:
        # name only — no args
        tool = name.split("__")[0] if name.startswith("mcp__") else name
        if name.startswith("mcp__"):
            tool = "mcp"
        self.counters["tool_calls"] += 1
        self._tool_hist[tool] = self._tool_hist.get(tool, 0) + 1
        self.emit("tool", tool=tool)


def summarize_local(limit_files: int = 20) -> dict[str, Any]:
    root = telemetry_dir()
    if not root.is_dir():
        return {"enabled_files": 0, "sessions": [], "dir": str(root)}
    files = sorted(root.glob("*.jsonl"), key=lambda p: p.stat().st_mtime, reverse=True)
    sessions = []
    for f in files[:limit_files]:
        if f.name == "install_id":
            continue
        n = 0
        tools: Dict[str, int] = {}
        try:
            for line in f.read_text(encoding="utf-8").splitlines():
                if not line.strip():
                    continue
                n += 1
                try:
                    obj = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if obj.get("event") == "tool":
                    t = obj.get("tool") or "?"
                    tools[t] = tools.get(t, 0) + 1
        except OSError:
            continue
        sessions.append(
            {
                "id": f.stem,
                "events": n,
                "tools": tools,
                "mtime": f.stat().st_mtime,
            }
        )
    return {
        "dir": str(root),
        "install_id": get_install_id() if install_id_path().is_file() else None,
        "files": len(files),
        "sessions": sessions,
    }


def clear_local() -> int:
    root = telemetry_dir()
    if not root.is_dir():
        return 0
    n = 0
    for f in root.glob("*.jsonl"):
        f.unlink(missing_ok=True)
        n += 1
    return n
