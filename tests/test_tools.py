from __future__ import annotations

from pathlib import Path

import pytest

from xp.tools import ToolRuntime


@pytest.fixture()
def rt(tmp_path: Path) -> ToolRuntime:
    return ToolRuntime(tmp_path, yolo=False, sandbox=True, confirm_risky=False)


def test_write_read_list(rt: ToolRuntime, tmp_path: Path):
    msg = rt.tool_write_file("a.txt", "hello\nworld\n")
    assert "a.txt" in msg
    assert rt.last_diffs  # colored-diff source
    out = rt.tool_read_file("a.txt")
    assert "hello" in out
    listing = rt.tool_list_dir(".")
    assert "a.txt" in listing


def test_str_replace(rt: ToolRuntime):
    rt.tool_write_file("b.txt", "foo bar foo")
    msg = rt.tool_str_replace("b.txt", "bar", "baz")
    assert "replacement" in msg
    assert "foo baz foo" in Path(rt.cwd / "b.txt").read_text()
    assert any("b.txt" in p for p, _ in rt.last_diffs)


def test_sandbox_blocks_outside(rt: ToolRuntime, tmp_path: Path):
    outside = tmp_path.parent / "outside-xp-test.txt"
    result = rt.run("write_file", {"path": str(outside), "content": "nope"})
    assert result.startswith("error:")
    assert "sandbox" in result.lower()


def test_bash_blocklist(rt: ToolRuntime):
    result = rt.tool_bash("git reset --hard")
    assert "blocked" in result.lower()


def test_bash_ok(rt: ToolRuntime):
    result = rt.tool_bash("echo hello-xp")
    assert "hello-xp" in result
    assert "exit 0" in result


def test_yolo_allows_outside(tmp_path: Path):
    rt = ToolRuntime(tmp_path, yolo=True)
    outside = tmp_path.parent / f"xp-yolo-{tmp_path.name}.txt"
    try:
        msg = rt.tool_write_file(str(outside), "ok")
        assert "ok" in outside.read_text() or "created" in msg or "updated" in msg
    finally:
        if outside.exists():
            outside.unlink()


def test_apply_patch_freeform(rt: ToolRuntime):
    rt.tool_write_file("c.py", "def f():\n    return 1\n")
    patch = """\
*** Begin Patch
*** Update File: c.py
@@
 def f():
-    return 1
+    return 2
*** End Patch
"""
    msg = rt.tool_apply_patch(patch)
    assert "error" not in msg.lower() or "updated" in msg.lower()
    assert "return 2" in (rt.cwd / "c.py").read_text()
    assert rt.last_diffs
