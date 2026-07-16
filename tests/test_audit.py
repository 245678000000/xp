from __future__ import annotations

from pathlib import Path

from xp.audit import AuditLog
from xp.agent import _truncate_tool_result


def test_audit_write(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("XP_AUDIT_DIR", str(tmp_path))
    log = AuditLog(enabled=True, session_id="t1")
    log.tool_call("bash", '{"command":"echo hi"}', "ok\n")
    assert log.path.is_file()
    text = log.path.read_text(encoding="utf-8")
    assert "tool_call" in text
    assert "bash" in text


def test_audit_disabled(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("XP_AUDIT_DIR", str(tmp_path))
    log = AuditLog(enabled=False, session_id="t2")
    log.tool_call("bash", "{}", "x")
    assert not log.path.exists()


def test_truncate_tool_result():
    big = "a" * 100_000
    out = _truncate_tool_result(big, 10_000)
    assert len(out) < 12_000
    assert "truncated" in out
