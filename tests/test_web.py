from __future__ import annotations

from xp.web import _strip_html, _parse_ddg_html
from xp.tools import ToolRuntime, get_tool_defs


def test_strip_html():
    assert "hello" in _strip_html("<p>hello <b>world</b></p>")


def test_parse_ddg_sample():
    raw = """
    <a class="result__a" href="https://example.com/docs">Example Docs</a>
    <a class="result__snippet">About the example API</a>
    """
    items = _parse_ddg_html(raw, max_results=3)
    assert items
    assert "example.com" in items[0][1]


def test_web_tools_gated(tmp_path):
    rt = ToolRuntime(tmp_path, enable_web=False)
    assert "disabled" in rt.tool_fetch_url("https://example.com").lower()


def test_tool_defs_web_spawn():
    base = get_tool_defs(enable_web=False, enable_spawn=False)
    names = {t["function"]["name"] for t in base}
    assert "fetch_url" not in names
    assert "spawn_task" not in names
    full = get_tool_defs(enable_web=True, enable_spawn=True)
    names2 = {t["function"]["name"] for t in full}
    assert "fetch_url" in names2 and "web_search" in names2 and "spawn_task" in names2
