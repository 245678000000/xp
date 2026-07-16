from __future__ import annotations

from pathlib import Path

from xp import session as sess


def test_save_load_list(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("XP_SESSIONS_DIR", str(tmp_path))
    sid = "test-session-1"
    messages = [
        {"role": "system", "content": "sys"},
        {"role": "user", "content": "hi"},
        {"role": "assistant", "content": "hello"},
    ]
    path = sess.save_session(sid, messages, model="m", cwd="/tmp")
    assert path.is_file()
    loaded = sess.load_session(sid)
    assert loaded == messages
    items = sess.list_sessions()
    assert any(i["id"] == sid for i in items)
    assert sess.latest_session_id() == sid
