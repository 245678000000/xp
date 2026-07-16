"""OpenAI-compatible tool loop with stream, retry, usage, compaction."""

from __future__ import annotations

import json
import time
from collections.abc import Callable
from typing import Any, Dict, List, Optional, Tuple

from openai import APIConnectionError, APIStatusError, OpenAI, RateLimitError
from rich.console import Console
from rich.markup import escape

from xp.config import RuntimeConfig
from xp.prompts import build_system_prompt
from xp.session import new_session_id, save_session
from xp.skills import Skill
from xp.diffutil import format_diff_for_terminal
from xp.tools import TOOL_DEFS, ToolRuntime

OnEvent = Callable[[str, str], None]


class Agent:
    def __init__(
        self,
        config: RuntimeConfig,
        *,
        skill: Skill | None = None,
        agent_name: str | None = None,
        console: Console | None = None,
        on_event: OnEvent | None = None,
        messages: List[dict[str, Any]] | None = None,
        session_id: str | None = None,
        persist: bool = False,
        confirm_fn: Optional[Callable[[str], bool]] = None,
    ) -> None:
        self.config = config
        self.skill = skill
        self.agent_name = agent_name
        self.console = console or Console(stderr=True)
        self.on_event = on_event
        self.persist = persist
        self.session_id = session_id or (new_session_id() if persist else None)
        self.total_usage = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}

        def _default_confirm(prompt: str) -> bool:
            try:
                ans = self.console.input(f"[yellow]{escape(prompt)}[/] [y/N] ").strip().lower()
            except (EOFError, KeyboardInterrupt):
                return False
            return ans in ("y", "yes")

        self.tools = ToolRuntime(
            config.cwd,
            yolo=config.yolo,
            sandbox=config.sandbox,
            confirm_risky=config.confirm_risky,
            confirm_fn=confirm_fn or _default_confirm,
        )
        self.client = OpenAI(
            api_key=config.api_key,
            base_url=config.base_url,
            timeout=config.timeout,
            max_retries=0,  # we handle retries ourselves
        )
        if messages is not None:
            self.messages = messages
        else:
            self.messages = [
                {
                    "role": "system",
                    "content": build_system_prompt(
                        skill=skill,
                        agent=agent_name,
                        system_extra=config.system_extra,
                        cwd=config.cwd,
                    ),
                }
            ]

    def _emit(self, kind: str, text: str) -> None:
        if self.on_event:
            self.on_event(kind, text)
            return
        if kind == "assistant":
            self.console.print(f"[bold cyan]xp[/] {escape(text)}")
        elif kind == "assistant_delta":
            self.console.print(escape(text), end="")
        elif kind == "tool_call":
            self.console.print(f"[dim]→ {escape(text)}[/]")
        elif kind == "tool_result":
            preview = text if len(text) <= 1200 else text[:1200] + "\n…[truncated]"
            self.console.print(f"[dim]{escape(preview)}[/]")
        elif kind == "diff":
            self._print_diff(text)
        elif kind == "status":
            self.console.print(f"[dim]{escape(text)}[/]")
        elif kind == "usage":
            self.console.print(f"[dim]{escape(text)}[/]")

    def _print_diff(self, diff_text: str) -> None:
        style_map = {
            "green": "green",
            "red": "red",
            "cyan": "cyan",
            "dim": "dim",
            "bold": "bold",
        }
        for style, line in format_diff_for_terminal(diff_text):
            self.console.print(f"[{style_map.get(style, 'dim')}]{escape(line)}[/]")

    def _persist(self) -> None:
        if self.persist and self.session_id:
            save_session(
                self.session_id,
                self.messages,
                model=self.config.model,
                cwd=str(self.config.cwd),
            )

    def _compact(self) -> None:
        max_m = max(10, self.config.max_messages)
        if len(self.messages) <= max_m:
            return
        system = self.messages[0] if self.messages and self.messages[0].get("role") == "system" else None
        tail = self.messages[-(max_m - 1) :]
        # Drop orphan tool messages at the start of tail
        while tail and tail[0].get("role") == "tool":
            tail = tail[1:]
        note = {
            "role": "system",
            "content": "[context compacted: older turns dropped to fit max_messages]",
        }
        if system:
            self.messages = [system, note, *tail]
        else:
            self.messages = [note, *tail]
        self._emit("status", f"compacted context → {len(self.messages)} messages")

    def _accumulate_usage(self, usage: Any) -> None:
        if not usage:
            return
        for k in ("prompt_tokens", "completion_tokens", "total_tokens"):
            v = getattr(usage, k, None)
            if v is None and isinstance(usage, dict):
                v = usage.get(k)
            if v is not None:
                self.total_usage[k] = self.total_usage.get(k, 0) + int(v)

    def _create_completion(self) -> Tuple[str, List[dict[str, Any]], Any]:
        """Return (content, tool_calls_as_dicts, usage)."""
        kwargs: Dict[str, Any] = {
            "model": self.config.model,
            "messages": self.messages,
            "tools": TOOL_DEFS,
            "temperature": self.config.temperature,
        }
        last_err: Exception | None = None
        for attempt in range(self.config.max_retries + 1):
            try:
                if self.config.stream:
                    return self._stream_completion(kwargs)
                resp = self.client.chat.completions.create(**kwargs)
                choice = resp.choices[0]
                msg = choice.message
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
            except (RateLimitError, APIConnectionError) as e:
                last_err = e
            except APIStatusError as e:
                last_err = e
                if e.status_code not in (408, 409, 429, 500, 502, 503, 504):
                    raise
            if attempt < self.config.max_retries:
                delay = min(2**attempt, 20)
                self._emit("status", f"retry {attempt + 1}/{self.config.max_retries} in {delay}s: {last_err}")
                time.sleep(delay)
        raise SystemExit(f"API error after retries: {last_err}")

    def _stream_completion(
        self, kwargs: Dict[str, Any]
    ) -> Tuple[str, List[dict[str, Any]], Any]:
        try:
            stream = self.client.chat.completions.create(
                **kwargs, stream=True, stream_options={"include_usage": True}
            )
        except Exception:
            # Some providers reject stream_options
            stream = self.client.chat.completions.create(**kwargs, stream=True)
        content_parts: List[str] = []
        # tool_index -> {id, name, arguments}
        tools: Dict[int, dict[str, Any]] = {}
        usage = None
        printed = False
        for event in stream:
            if getattr(event, "usage", None):
                usage = event.usage
            if not event.choices:
                continue
            delta = event.choices[0].delta
            if delta and delta.content:
                content_parts.append(delta.content)
                self._emit("assistant_delta", delta.content)
                printed = True
            if delta and delta.tool_calls:
                for tc in delta.tool_calls:
                    idx = tc.index if tc.index is not None else 0
                    slot = tools.setdefault(
                        idx,
                        {"id": "", "type": "function", "function": {"name": "", "arguments": ""}},
                    )
                    if tc.id:
                        slot["id"] = tc.id
                    if tc.function:
                        if tc.function.name:
                            slot["function"]["name"] = (
                                slot["function"].get("name", "") + tc.function.name
                            )
                        if tc.function.arguments:
                            slot["function"]["arguments"] = (
                                slot["function"].get("arguments", "") + tc.function.arguments
                            )
        if printed:
            self._emit("assistant_delta", "\n")
        content = "".join(content_parts)
        tool_list = [tools[i] for i in sorted(tools)]
        for t in tool_list:
            t["function"]["arguments"] = t["function"].get("arguments") or "{}"
            if not t.get("id"):
                t["id"] = f"call_{t['function']['name']}_{len(t['function']['arguments'])}"
        return content, tool_list, usage

    def run(self, user_message: str) -> str:
        self.messages.append({"role": "user", "content": user_message})
        self._compact()
        self._persist()
        final = ""

        for turn in range(self.config.max_turns):
            self._emit(
                "status",
                f"turn {turn + 1}/{self.config.max_turns} · {self.config.model}",
            )
            content, tool_calls, usage = self._create_completion()
            self._accumulate_usage(usage)

            assistant_record: dict[str, Any] = {
                "role": "assistant",
                "content": content or "",
            }
            if tool_calls:
                assistant_record["tool_calls"] = tool_calls
            self.messages.append(assistant_record)

            if content:
                final = content
                if not tool_calls and not self.config.stream:
                    self._emit("assistant", content)

            if not tool_calls:
                if self.total_usage.get("total_tokens"):
                    u = self.total_usage
                    self._emit(
                        "usage",
                        f"tokens: prompt={u['prompt_tokens']} completion={u['completion_tokens']} total={u['total_tokens']}",
                    )
                self._persist()
                return final or "(no response)"

            for tc in tool_calls:
                name = tc["function"]["name"]
                args_raw = tc["function"].get("arguments") or "{}"
                try:
                    args_obj = json.loads(args_raw)
                except json.JSONDecodeError:
                    args_obj = {}
                summary = name
                if name == "bash" and isinstance(args_obj, dict):
                    summary = f"bash: {str(args_obj.get('command', ''))[:200]}"
                elif name in ("read_file", "write_file", "str_replace", "list_dir") and isinstance(
                    args_obj, dict
                ):
                    summary = f"{name}: {args_obj.get('path', '')}"
                elif name == "apply_patch":
                    summary = "apply_patch"
                elif name == "grep" and isinstance(args_obj, dict):
                    summary = f"grep: {args_obj.get('pattern', '')}"
                self._emit("tool_call", summary)

                result = self.tools.run(name, args_raw)
                # Colored diff preview for mutating tools
                if self.tools.last_diffs:
                    for rel, diff in self.tools.last_diffs:
                        self._emit("status", f"diff {rel}")
                        self._emit("diff", diff)
                    # Keep tool message compact for the model
                    first_line = result.split("\n\n", 1)[0]
                    self._emit("tool_result", first_line)
                    tool_content = result
                else:
                    self._emit("tool_result", result)
                    tool_content = result
                self.messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": tc["id"],
                        "content": tool_content,
                    }
                )
            self._compact()
            self._persist()

        self._persist()
        return final or f"(stopped after {self.config.max_turns} turns)"
