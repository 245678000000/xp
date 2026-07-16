"""Optional local audit log for tool calls (opt-in, never uploads)."""

from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any, Optional


def audit_dir() -> Path:
    if env := os.environ.get("XP_AUDIT_DIR"):
        return Path(env).expanduser()
    xdg = os.environ.get("XDG_DATA_HOME")
    if xdg:
        return Path(xdg) / "xp" / "audit"
    return Path.home() / ".local" / "share" / "xp" / "audit"


class AuditLog:
    def __init__(self, enabled: bool = False, session_id: Optional[str] = None) -> None:
        self.enabled = enabled
        self.session_id = session_id or time.strftime("%Y%m%d-%H%M%S")
        self.path = audit_dir() / f"{self.session_id}.jsonl"

    def write(self, event: str, **fields: Any) -> None:
        if not self.enabled:
            return
        self.path.parent.mkdir(parents=True, exist_ok=True)
        row = {
            "ts": time.time(),
            "event": event,
            "session": self.session_id,
            **fields,
        }
        # Never log full API keys
        with self.path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(row, ensure_ascii=False, default=str) + "\n")

    def tool_call(self, name: str, arguments: str, result: str) -> None:
        # Truncate bulky payloads
        args = arguments if len(arguments) <= 4000 else arguments[:4000] + "…"
        res = result if len(result) <= 8000 else result[:4000] + "\n…\n" + result[-2000:]
        self.write("tool_call", tool=name, arguments=args, result=res)
