from __future__ import annotations

from xp.tui import SLASH_COMMANDS, make_reader, tui_available


def test_slash_commands_include_quit():
    assert "/quit" in SLASH_COMMANDS
    assert any(c.startswith("/commit") for c in SLASH_COMMANDS)


def test_make_reader_simple(monkeypatch):
    monkeypatch.setattr("builtins.input", lambda p: "hello")
    read = make_reader(tui=False)
    assert read("you> ") == "hello"


def test_tui_available_bool():
    assert isinstance(tui_available(), bool)
