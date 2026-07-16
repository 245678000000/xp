"""Session persistence (jsonl transcripts)."""

from __future__ import annotations

import json
import os
import time
import uuid
from pathlib import Path
from typing import Any, List, Optional


def sessions_dir() -> Path:
    if env := os.environ.get("XP_SESSIONS_DIR"):
        return Path(env).expanduser()
    xdg = os.environ.get("XDG_DATA_HOME")
    if xdg:
        return Path(xdg) / "xp" / "sessions"
    return Path.home() / ".local" / "share" / "xp" / "sessions"


def new_session_id() -> str:
    return time.strftime("%Y%m%d-%H%M%S") + "-" + uuid.uuid4().hex[:8]


def session_path(session_id: str) -> Path:
    return sessions_dir() / f"{session_id}.jsonl"


def list_sessions(limit: int = 20) -> List[dict[str, Any]]:
    root = sessions_dir()
    if not root.is_dir():
        return []
    files = sorted(root.glob("*.jsonl"), key=lambda p: p.stat().st_mtime, reverse=True)
    out: List[dict[str, Any]] = []
    for f in files[:limit]:
        meta = _read_meta(f)
        out.append(
            {
                "id": f.stem,
                "path": str(f),
                "mtime": f.stat().st_mtime,
                "model": meta.get("model", ""),
                "cwd": meta.get("cwd", ""),
                "messages": meta.get("message_count", 0),
            }
        )
    return out


def latest_session_id() -> Optional[str]:
    items = list_sessions(1)
    return items[0]["id"] if items else None


def _read_meta(path: Path) -> dict[str, Any]:
    meta: dict[str, Any] = {"message_count": 0}
    try:
        with path.open(encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if obj.get("type") == "meta":
                    meta.update(obj)
                elif obj.get("type") == "message":
                    meta["message_count"] = int(meta.get("message_count", 0)) + 1
    except OSError:
        pass
    return meta


def save_session(
    session_id: str,
    messages: List[dict[str, Any]],
    *,
    model: str = "",
    cwd: str = "",
) -> Path:
    root = sessions_dir()
    root.mkdir(parents=True, exist_ok=True)
    path = session_path(session_id)
    with path.open("w", encoding="utf-8") as fh:
        fh.write(
            json.dumps(
                {
                    "type": "meta",
                    "id": session_id,
                    "model": model,
                    "cwd": cwd,
                    "updated_at": time.time(),
                },
                ensure_ascii=False,
            )
            + "\n"
        )
        for msg in messages:
            fh.write(
                json.dumps({"type": "message", "message": msg}, ensure_ascii=False) + "\n"
            )
    return path


def load_session(session_id: str) -> List[dict[str, Any]]:
    path = session_path(session_id)
    if not path.is_file():
        raise FileNotFoundError(f"session not found: {session_id} ({path})")
    messages: List[dict[str, Any]] = []
    with path.open(encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            obj = json.loads(line)
            if obj.get("type") == "message" and "message" in obj:
                messages.append(obj["message"])
    return messages
