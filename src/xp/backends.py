"""LLM backends: OpenAI chat.completions + Anthropic messages."""

from __future__ import annotations

import json
import time
from typing import Any, Callable, Dict, List, Optional, Tuple

import httpx
from openai import APIConnectionError, APIStatusError, OpenAI, RateLimitError

from xp.config import RuntimeConfig

Emit = Callable[[str, str], None]


def openai_client(config: RuntimeConfig) -> OpenAI:
    return OpenAI(
        api_key=config.api_key,
        base_url=config.base_url,
        timeout=config.timeout,
        max_retries=0,
    )


def create_with_retry(
    config: RuntimeConfig,
    *,
    messages: List[dict[str, Any]],
    tools: List[dict[str, Any]],
    stream: bool,
    emit: Emit,
) -> Tuple[str, List[dict[str, Any]], Any]:
    backend = (config.api_backend or "chat_completions").lower()
    last_err: Exception | None = None
    for attempt in range(config.max_retries + 1):
        try:
            if backend in ("messages", "anthropic"):
                return _anthropic_create(config, messages=messages, tools=tools, stream=stream, emit=emit)
            return _openai_create(config, messages=messages, tools=tools, stream=stream, emit=emit)
        except (RateLimitError, APIConnectionError) as e:
            last_err = e
        except APIStatusError as e:
            last_err = e
            if e.status_code not in (408, 409, 429, 500, 502, 503, 504):
                raise
        except httpx.HTTPError as e:
            last_err = e
        if attempt < config.max_retries:
            delay = min(2**attempt, 20)
            emit("status", f"retry {attempt + 1}/{config.max_retries} in {delay}s: {last_err}")
            time.sleep(delay)
    raise SystemExit(f"API error after retries: {last_err}")


def _openai_create(
    config: RuntimeConfig,
    *,
    messages: List[dict[str, Any]],
    tools: List[dict[str, Any]],
    stream: bool,
    emit: Emit,
) -> Tuple[str, List[dict[str, Any]], Any]:
    client = openai_client(config)
    kwargs: Dict[str, Any] = {
        "model": config.model,
        "messages": messages,
        "tools": tools if tools else None,
        "temperature": config.temperature,
    }
    # omit tools key if empty — some providers reject tools=[]
    if not tools:
        kwargs.pop("tools", None)

    if not stream:
        resp = client.chat.completions.create(**kwargs)
        msg = resp.choices[0].message
        tool_calls: List[dict[str, Any]] = []
        if msg.tool_calls:
            for tc in msg.tool_calls:
                tool_calls.append(
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {
                            "name": tc.function.name,
                            "arguments": tc.function.arguments or "{}",
                        },
                    }
                )
        return msg.content or "", tool_calls, getattr(resp, "usage", None)

    try:
        stream_obj = client.chat.completions.create(
            **kwargs, stream=True, stream_options={"include_usage": True}
        )
    except Exception:
        stream_obj = client.chat.completions.create(**kwargs, stream=True)

    content_parts: List[str] = []
    tools_acc: Dict[int, dict[str, Any]] = {}
    usage = None
    printed = False
    for event in stream_obj:
        if getattr(event, "usage", None):
            usage = event.usage
        if not event.choices:
            continue
        delta = event.choices[0].delta
        if delta and delta.content:
            content_parts.append(delta.content)
            emit("assistant_delta", delta.content)
            printed = True
        if delta and delta.tool_calls:
            for tc in delta.tool_calls:
                idx = tc.index if tc.index is not None else 0
                slot = tools_acc.setdefault(
                    idx,
                    {"id": "", "type": "function", "function": {"name": "", "arguments": ""}},
                )
                if tc.id:
                    slot["id"] = tc.id
                if tc.function:
                    if tc.function.name:
                        slot["function"]["name"] += tc.function.name
                    if tc.function.arguments:
                        slot["function"]["arguments"] += tc.function.arguments
    if printed:
        emit("assistant_delta", "\n")
    tool_list = [tools_acc[i] for i in sorted(tools_acc)]
    for t in tool_list:
        t["function"]["arguments"] = t["function"].get("arguments") or "{}"
        if not t.get("id"):
            t["id"] = f"call_{t['function']['name']}"
    return "".join(content_parts), tool_list, usage


def _anthropic_create(
    config: RuntimeConfig,
    *,
    messages: List[dict[str, Any]],
    tools: List[dict[str, Any]],
    stream: bool,
    emit: Emit,
) -> Tuple[str, List[dict[str, Any]], Any]:
    """
    Anthropic Messages API (non-stream for reliability; stream optional later).
    base_url should be like https://api.anthropic.com (no /v1) or .../v1.
    """
    base = config.base_url.rstrip("/")
    if base.endswith("/v1"):
        url = base + "/messages"
    else:
        url = base + "/v1/messages"

    system_parts: List[str] = []
    anth_messages: List[dict[str, Any]] = []
    for m in messages:
        role = m.get("role")
        if role == "system":
            system_parts.append(m.get("content") or "")
        elif role == "user":
            anth_messages.append({"role": "user", "content": m.get("content") or ""})
        elif role == "assistant":
            content_blocks: List[dict[str, Any]] = []
            if m.get("content"):
                content_blocks.append({"type": "text", "text": m["content"]})
            for tc in m.get("tool_calls") or []:
                args = tc["function"].get("arguments") or "{}"
                try:
                    inp = json.loads(args)
                except json.JSONDecodeError:
                    inp = {"raw": args}
                content_blocks.append(
                    {
                        "type": "tool_use",
                        "id": tc["id"],
                        "name": tc["function"]["name"],
                        "input": inp,
                    }
                )
            if not content_blocks:
                content_blocks = [{"type": "text", "text": ""}]
            anth_messages.append({"role": "assistant", "content": content_blocks})
        elif role == "tool":
            # Anthropic wants tool_result as user content
            block = {
                "type": "tool_result",
                "tool_use_id": m.get("tool_call_id"),
                "content": m.get("content") or "",
            }
            if anth_messages and anth_messages[-1]["role"] == "user" and isinstance(
                anth_messages[-1]["content"], list
            ):
                anth_messages[-1]["content"].append(block)
            else:
                anth_messages.append({"role": "user", "content": [block]})

    anth_tools = []
    for t in tools:
        fn = t.get("function") or {}
        anth_tools.append(
            {
                "name": fn.get("name"),
                "description": fn.get("description") or "",
                "input_schema": fn.get("parameters")
                or {"type": "object", "properties": {}},
            }
        )

    body: Dict[str, Any] = {
        "model": config.model,
        "max_tokens": 8192,
        "temperature": config.temperature,
        "messages": anth_messages,
    }
    if system_parts:
        body["system"] = "\n\n".join(system_parts)
    if anth_tools:
        body["tools"] = anth_tools
    # streaming support: keep non-stream for simpler tool parsing
    if stream:
        emit("status", "anthropic backend: streaming disabled (tool-safe non-stream)")

    headers = {
        "x-api-key": config.api_key,
        "anthropic-version": "2023-06-01",
        "content-type": "application/json",
    }
    with httpx.Client(timeout=config.timeout) as client:
        resp = client.post(url, headers=headers, json=body)
        if resp.status_code >= 400:
            raise httpx.HTTPStatusError(
                f"Anthropic {resp.status_code}: {resp.text[:500]}",
                request=resp.request,
                response=resp,
            )
        data = resp.json()

    content = ""
    tool_calls: List[dict[str, Any]] = []
    for block in data.get("content") or []:
        if block.get("type") == "text":
            content += block.get("text") or ""
        elif block.get("type") == "tool_use":
            tool_calls.append(
                {
                    "id": block.get("id") or f"tool_{block.get('name')}",
                    "type": "function",
                    "function": {
                        "name": block.get("name"),
                        "arguments": json.dumps(block.get("input") or {}, ensure_ascii=False),
                    },
                }
            )
    usage = data.get("usage")
    # normalize usage keys for agent accumulator
    if usage:
        usage = {
            "prompt_tokens": usage.get("input_tokens", 0),
            "completion_tokens": usage.get("output_tokens", 0),
            "total_tokens": usage.get("input_tokens", 0) + usage.get("output_tokens", 0),
        }
    if content and not tool_calls:
        emit("assistant", content)
    return content, tool_calls, usage
