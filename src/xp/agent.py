"""OpenAI-compatible tool loop."""

from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any

from openai import OpenAI
from rich.console import Console
from rich.markup import escape

from xp.config import RuntimeConfig
from xp.prompts import build_system_prompt
from xp.skills import Skill
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
    ) -> None:
        self.config = config
        self.skill = skill
        self.agent_name = agent_name
        self.console = console or Console(stderr=True)
        self.on_event = on_event
        self.tools = ToolRuntime(config.cwd, yolo=config.yolo)
        self.client = OpenAI(
            api_key=config.api_key,
            base_url=config.base_url,
            timeout=config.timeout,
        )
        self.messages: list[dict[str, Any]] = [
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
        elif kind == "tool_call":
            self.console.print(f"[dim]→ {escape(text)}[/]")
        elif kind == "tool_result":
            preview = text if len(text) <= 1200 else text[:1200] + "\n…[truncated]"
            self.console.print(f"[dim]{escape(preview)}[/]")
        elif kind == "status":
            self.console.print(f"[dim]{escape(text)}[/]")

    def run(self, user_message: str) -> str:
        self.messages.append({"role": "user", "content": user_message})
        final = ""

        for turn in range(self.config.max_turns):
            self._emit("status", f"turn {turn + 1}/{self.config.max_turns} · {self.config.model}")
            try:
                resp = self.client.chat.completions.create(
                    model=self.config.model,
                    messages=self.messages,
                    tools=TOOL_DEFS,
                    temperature=self.config.temperature,
                )
            except Exception as e:  # noqa: BLE001
                raise SystemExit(f"API error: {e}") from e

            choice = resp.choices[0]
            msg = choice.message
            tool_calls = msg.tool_calls or []

            # Record assistant message (with tool_calls if any)
            assistant_record: dict[str, Any] = {
                "role": "assistant",
                "content": msg.content or "",
            }
            if tool_calls:
                assistant_record["tool_calls"] = [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {
                            "name": tc.function.name,
                            "arguments": tc.function.arguments or "{}",
                        },
                    }
                    for tc in tool_calls
                ]
            self.messages.append(assistant_record)

            if msg.content:
                final = msg.content
                if not tool_calls:
                    self._emit("assistant", msg.content)

            if not tool_calls:
                return final or "(no response)"

            for tc in tool_calls:
                name = tc.function.name
                args_raw = tc.function.arguments or "{}"
                try:
                    args_obj = json.loads(args_raw)
                except json.JSONDecodeError:
                    args_obj = {}
                # Compact display
                summary = name
                if name == "bash" and isinstance(args_obj, dict):
                    summary = f"bash: {args_obj.get('command', '')[:200]}"
                elif name in ("read_file", "write_file", "str_replace", "list_dir") and isinstance(
                    args_obj, dict
                ):
                    summary = f"{name}: {args_obj.get('path', '')}"
                elif name == "grep" and isinstance(args_obj, dict):
                    summary = f"grep: {args_obj.get('pattern', '')}"
                self._emit("tool_call", summary)

                result = self.tools.run(name, args_raw)
                self._emit("tool_result", result)
                self.messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": tc.id,
                        "content": result,
                    }
                )

        return final or f"(stopped after {self.config.max_turns} turns)"
