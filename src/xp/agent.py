"""OpenAI-compatible / Anthropic tool loop with stream, retry, usage, compaction."""

from __future__ import annotations

import copy
import json
from collections.abc import Callable
from typing import Any, List, Optional

from rich.console import Console
from rich.markup import escape

from xp.backends import create_with_retry
from xp.config import RuntimeConfig
from xp.diffutil import format_diff_for_terminal
from xp.prompts import build_system_prompt
from xp.session import new_session_id, save_session
from xp.skills import Skill
from xp.tools import get_tool_defs, ToolRuntime

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
        read_only: bool = False,
        allow_spawn: bool = True,
    ) -> None:
        self.config = config
        self.skill = skill
        self.agent_name = agent_name
        self.console = console or Console(stderr=True)
        self.on_event = on_event
        self.persist = persist
        self.session_id = session_id or (new_session_id() if persist else None)
        self.total_usage = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
        self.read_only = read_only
        self.tool_defs = get_tool_defs(
            enable_web=config.enable_web,
            enable_spawn=config.enable_spawn and allow_spawn and not read_only,
            read_only=read_only,
        )

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
            enable_web=config.enable_web,
            read_only=read_only,
            spawn_task_fn=None if read_only or not allow_spawn else self._spawn_task,
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
                        enable_web=config.enable_web,
                        enable_spawn=config.enable_spawn and allow_spawn and not read_only,
                        read_only=read_only,
                    ),
                }
            ]

    def _spawn_task(self, goal: str, max_turns: int = 6) -> str:
        self._emit("status", f"spawn_task: {goal[:120]}")
        child_cfg = copy.copy(self.config)
        child_cfg.max_turns = max(1, min(int(max_turns), 12))
        child_cfg.stream = False  # quieter sub-run
        child = Agent(
            child_cfg,
            skill=None,
            agent_name=None,
            console=self.console,
            on_event=lambda k, t: self._emit(k, t) if k in ("tool_call", "status") else None,
            persist=False,
            read_only=True,
            allow_spawn=False,
        )
        # Override system prompt emphasis
        child.messages[0]["content"] = (
            "You are a read-only investigator for xp. "
            "Use only read tools (read_file, list_dir, grep, bash for read-only commands). "
            "Do not modify files. Return a concise factual summary with paths.\n\n"
            + child.messages[0]["content"]
        )
        try:
            summary = child.run(goal)
        except SystemExit as e:
            return f"error: spawn_task failed: {e}"
        # roll child usage into parent
        for k, v in child.total_usage.items():
            self.total_usage[k] = self.total_usage.get(k, 0) + int(v or 0)
        if len(summary) > 12_000:
            summary = summary[:12_000] + "\n…[truncated]"
        return f"## spawn_task result\n\n{summary}"

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

    def _create_completion(self):
        return create_with_retry(
            self.config,
            messages=self.messages,
            tools=self.tool_defs,
            stream=self.config.stream and not self.read_only,
            emit=self._emit,
        )

    def run(self, user_message: str) -> str:
        self.messages.append({"role": "user", "content": user_message})
        self._compact()
        self._persist()
        final = ""

        for turn in range(self.config.max_turns):
            self._emit(
                "status",
                f"turn {turn + 1}/{self.config.max_turns} · {self.config.model}"
                + (" · ro" if self.read_only else ""),
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
                elif name in (
                    "read_file",
                    "write_file",
                    "str_replace",
                    "list_dir",
                    "fetch_url",
                ) and isinstance(args_obj, dict):
                    summary = f"{name}: {args_obj.get('path') or args_obj.get('url', '')}"
                elif name == "apply_patch":
                    summary = "apply_patch"
                elif name == "web_search" and isinstance(args_obj, dict):
                    summary = f"web_search: {args_obj.get('query', '')[:80]}"
                elif name == "spawn_task" and isinstance(args_obj, dict):
                    summary = f"spawn_task: {str(args_obj.get('goal', ''))[:80]}"
                elif name == "grep" and isinstance(args_obj, dict):
                    summary = f"grep: {args_obj.get('pattern', '')}"
                self._emit("tool_call", summary)

                result = self.tools.run(name, args_raw)
                if self.tools.last_diffs:
                    for rel, diff in self.tools.last_diffs:
                        self._emit("status", f"diff {rel}")
                        self._emit("diff", diff)
                    first_line = result.split("\n\n", 1)[0]
                    self._emit("tool_result", first_line)
                else:
                    self._emit("tool_result", result)
                self.messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": tc["id"],
                        "content": result,
                    }
                )
            self._compact()
            self._persist()

        self._persist()
        return final or f"(stopped after {self.config.max_turns} turns)"
