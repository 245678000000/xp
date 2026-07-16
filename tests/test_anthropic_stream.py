from __future__ import annotations

import json
from typing import List

from xp.backends import _anthropic_stream


class _FakeStreamResp:
    def __init__(self, lines: List[str], status_code: int = 200):
        self.status_code = status_code
        self._lines = lines
        self.request = None

    def read(self):
        return b"err"

    def iter_lines(self):
        for line in self._lines:
            yield line

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


class _FakeClient:
    def __init__(self, lines: List[str]):
        self._lines = lines

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def stream(self, *args, **kwargs):
        return _FakeStreamResp(self._lines)


def test_anthropic_sse_text_and_tool(monkeypatch):
    events = [
        'event: content_block_start',
        'data: {"type":"content_block_start","index":0,"content_block":{"type":"text","text":""}}',
        '',
        'event: content_block_delta',
        'data: {"type":"content_block_delta","index":0,"delta":{"type":"text_delta","text":"Hi "}}',
        '',
        'event: content_block_delta',
        'data: {"type":"content_block_delta","index":0,"delta":{"type":"text_delta","text":"there"}}',
        '',
        'event: content_block_start',
        'data: {"type":"content_block_start","index":1,"content_block":{"type":"tool_use","id":"t1","name":"bash","input":{}}}',
        '',
        'event: content_block_delta',
        'data: {"type":"content_block_delta","index":1,"delta":{"type":"input_json_delta","partial_json":"{\\"command\\":\\"echo hi\\"}"}}',
        '',
        'event: message_delta',
        'data: {"type":"message_delta","usage":{"output_tokens":12}}',
        '',
    ]

    import xp.backends as backends

    monkeypatch.setattr(
        backends.httpx,
        "Client",
        lambda **kwargs: _FakeClient(events),
    )

    deltas: List[str] = []

    def emit(kind: str, text: str) -> None:
        if kind == "assistant_delta":
            deltas.append(text)

    content, tools, usage = _anthropic_stream(
        "https://example.com/v1/messages",
        {"x-api-key": "x"},
        {"stream": True},
        emit=emit,
        timeout=10,
    )
    assert "Hi there" in content.replace("\n", "")
    assert len(tools) == 1
    assert tools[0]["function"]["name"] == "bash"
    args = json.loads(tools[0]["function"]["arguments"])
    assert args["command"] == "echo hi"
    assert usage and usage["completion_tokens"] == 12
