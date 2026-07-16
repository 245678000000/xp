from __future__ import annotations

from pathlib import Path

from xp.telemetry import Telemetry, clear_local, summarize_local


def test_telemetry_disabled(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("XP_TELEMETRY_DIR", str(tmp_path))
    t = Telemetry(enabled=False, session_id="s0", cwd="/tmp/x")
    t.session_start()
    t.tool("bash")
    t.session_end({"prompt_tokens": 1, "completion_tokens": 2})
    assert list(tmp_path.glob("*.jsonl")) == []


def test_telemetry_local(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("XP_TELEMETRY_DIR", str(tmp_path))
    t = Telemetry(enabled=True, session_id="s1", model="m", backend="chat_completions", cwd="/tmp/proj")
    t.session_start()
    t.turn()
    t.tool("bash")
    t.tool("mcp__fs__read")
    t.session_end({"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15})
    assert t.path.is_file()
    text = t.path.read_text(encoding="utf-8")
    assert "session_start" in text
    assert "tool" in text
    assert "bash" in text
    # no prompt content fields
    assert "api_key" not in text
    summary = summarize_local()
    assert summary["files"] >= 1
    n = clear_local()
    assert n >= 1
