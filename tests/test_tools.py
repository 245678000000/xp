from __future__ import annotations

from pathlib import Path

import pytest

from xp.tools import ToolRuntime


@pytest.fixture()
def rt(tmp_path: Path) -> ToolRuntime:
    return ToolRuntime(tmp_path, yolo=False, sandbox=True, confirm_risky=False)


def test_write_read_list(rt: ToolRuntime, tmp_path: Path):
    assert "wrote" in rt.tool_write_file("a.txt", "hello\nworld\n")
    out = rt.tool_read_file("a.txt")
    assert "hello" in out
    listing = rt.tool_list_dir(".")
    assert "a.txt" in listing


def test_str_replace(rt: ToolRuntime):
    rt.tool_write_file("b.txt", "foo bar foo")
    msg = rt.tool_str_replace("b.txt", "bar", "baz")
    assert "updated" in msg
    assert "foo baz foo" in Path(rt.cwd / "b.txt").read_text()


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
        assert "wrote" in msg
    finally:
        if outside.exists():
            outside.unlink()
