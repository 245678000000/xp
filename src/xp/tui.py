"""Lightweight interactive input helpers (optional prompt_toolkit)."""

from __future__ import annotations

from typing import Callable, List, Optional

SLASH_COMMANDS = [
    "/skills",
    "/skill ",
    "/agent ",
    "/commit",
    "/pr",
    "/fix",
    "/ship",
    "/review",
    "/test",
    "/refactor",
    "/release",
    "/quit",
    "/exit",
]


def read_line_simple(prompt: str = "you> ") -> str:
    return input(prompt)


def read_line_tui(
    prompt: str = "you> ",
    *,
    history_path: Optional[str] = None,
) -> str:
    """
    Multiline-friendly prompt with history and slash completions when
    prompt_toolkit is installed; otherwise falls back to input().
    """
    try:
        from prompt_toolkit import PromptSession
        from prompt_toolkit.auto_suggest import AutoSuggestFromHistory
        from prompt_toolkit.completion import Completer, Completion, WordCompleter
        from prompt_toolkit.history import FileHistory, InMemoryHistory
        from prompt_toolkit.key_binding import KeyBindings
        from prompt_toolkit.styles import Style
    except ImportError:
        return read_line_simple(prompt)

    class SlashCompleter(Completer):
        def get_completions(self, document, complete_event):  # type: ignore[no-untyped-def]
            text = document.text_before_cursor
            if not text.startswith("/"):
                return
            for cmd in SLASH_COMMANDS:
                if cmd.startswith(text):
                    yield Completion(cmd, start_position=-len(text))

    history = InMemoryHistory()
    if history_path:
        try:
            from pathlib import Path

            Path(history_path).parent.mkdir(parents=True, exist_ok=True)
            history = FileHistory(history_path)
        except OSError:
            history = InMemoryHistory()

    kb = KeyBindings()

    @kb.add("escape", "enter")  # Meta+Enter submit if multiline feels stuck
    def _(event):  # type: ignore[no-untyped-def]
        event.current_buffer.validate_and_handle()

    session: PromptSession[str] = PromptSession(
        history=history,
        auto_suggest=AutoSuggestFromHistory(),
        completer=SlashCompleter(),
        key_bindings=kb,
        style=Style.from_dict(
            {
                "prompt": "ansigreen bold",
            }
        ),
    )
    # Enter submits; paste multi-line works; use \\ + Enter habits less needed
    return session.prompt([("class:prompt", prompt)])


def make_reader(*, tui: bool, history_path: Optional[str] = None) -> Callable[[str], str]:
    if not tui:
        return read_line_simple

    def _read(prompt: str = "you> ") -> str:
        return read_line_tui(prompt, history_path=history_path)

    return _read


def tui_available() -> bool:
    try:
        import prompt_toolkit  # noqa: F401

        return True
    except ImportError:
        return False
