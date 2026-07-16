from __future__ import annotations

from types import SimpleNamespace
from typing import Any, List
from pathlib import Path

from xp.agent import Agent
from xp.config import RuntimeConfig


class _FakeFn:
    def __init__(self, name: str, arguments: str):
        self.name = name
        self.arguments = arguments


class _FakeTC:
    def __init__(self, id: str, name: str, arguments: str):
        self.id = id
        self.function = _FakeFn(name, arguments)


class _FakeMsg:
    def __init__(self, content: str = "", tool_calls=None):
        self.content = content
        self.tool_calls = tool_calls


class _FakeChoice:
    def __init__(self, message):
        self.message = message


class _FakeResp:
    def __init__(self, message, usage=None):
        self.choices = [_FakeChoice(message)]
        self.usage = usage


class _FakeCompletions:
    def __init__(self, responses: List[Any]):
        self._responses = list(responses)
        self.calls = 0

    def create(self, **kwargs):
        self.calls += 1
        assert "tools" in kwargs
        if not self._responses:
            raise RuntimeError("no more fake responses")
        return self._responses.pop(0)


class _FakeChat:
    def __init__(self, completions: _FakeCompletions):
        self.completions = completions


class _FakeClient:
    def __init__(self, completions: _FakeCompletions):
        self.chat = _FakeChat(completions)


def test_tool_loop_then_final(tmp_path: Path, monkeypatch):
    cfg = RuntimeConfig(
        api_key="test",
        model="fake",
        cwd=tmp_path,
        stream=False,
        sandbox=True,
        yolo=False,
        confirm_risky=False,
        max_retries=0,
    )
    usage = SimpleNamespace(prompt_tokens=10, completion_tokens=5, total_tokens=15)
    responses = [
        _FakeResp(
            _FakeMsg(
                content="",
                tool_calls=[
                    _FakeTC("1", "bash", '{"command":"echo tool-loop-ok"}'),
                ],
            ),
            usage=usage,
        ),
        _FakeResp(_FakeMsg(content="done: tool-loop-ok"), usage=usage),
    ]
    fake = _FakeCompletions(responses)

    agent = Agent(cfg, persist=False)
    agent.client = _FakeClient(fake)  # type: ignore[assignment]
    # silence output
    agent.on_event = lambda *_: None

    result = agent.run("run a command")
    assert "done" in result
    assert fake.calls == 2
    assert agent.total_usage["total_tokens"] == 30
