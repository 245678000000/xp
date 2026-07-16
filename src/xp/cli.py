"""xp CLI — standalone coding agent."""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

from rich.console import Console
from rich.markdown import Markdown
from rich.markup import escape
from rich.panel import Panel
from rich.table import Table

from xp import __version__
from xp.agent import Agent
from xp.config import load_config
from xp.diffutil import format_diff_for_terminal
from xp.paths import agents_md_path, skills_dir, user_config_path
from xp.prompts import build_system_prompt
from xp.session import latest_session_id, list_sessions, load_session, new_session_id
from xp.skills import get_skill, load_skills, match_skill


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="xp",
        description="xp — standalone coding agent harness (OpenAI-compatible APIs, no Grok required)",
    )
    p.add_argument("-V", "--version", action="version", version=f"xp {__version__}")

    sub = p.add_subparsers(dest="cmd")

    run = sub.add_parser("run", help="Run a one-shot task (default)")
    _add_common(run)
    run.add_argument("prompt", nargs="*", help="Task prompt")
    run.add_argument(
        "-p",
        "--prompt-text",
        dest="prompt_flag",
        default=None,
        help="Prompt text (alternative to positional args)",
    )
    run.add_argument("--json", action="store_true", help="Machine-readable final result")

    chat = sub.add_parser("chat", help="Interactive multi-turn chat")
    _add_common(chat)
    chat.add_argument(
        "--continue",
        dest="continue_session",
        action="store_true",
        help="Resume the latest session",
    )
    chat.add_argument("--session", default=None, help="Resume a specific session id")

    skills = sub.add_parser("skills", help="List skills")
    skills.add_argument("--json", action="store_true")

    sessions = sub.add_parser("sessions", help="List saved chat sessions")
    sessions.add_argument("--json", action="store_true")
    sessions.add_argument("-n", type=int, default=20, help="Max sessions to list")

    doctor = sub.add_parser("doctor", help="Show config / paths / connectivity")
    doctor.add_argument("--model", default=None)
    doctor.add_argument("--base-url", default=None)
    doctor.add_argument("--api-key", default=None)
    doctor.add_argument("--probe", action="store_true", help="Call the API once")

    init = sub.add_parser("init", help="Write a sample ~/.config/xp/config.toml")
    init.add_argument("--force", action="store_true", help="Overwrite existing config")

    cfg_cmd = sub.add_parser("config", help="Show effective runtime config")
    cfg_cmd.add_argument("--json", action="store_true")

    return p


def _add_common(p: argparse.ArgumentParser) -> None:
    p.add_argument("-m", "--model", default=None, help="Model id")
    p.add_argument("--base-url", default=None, help="OpenAI-compatible base URL")
    p.add_argument("--api-key", default=None, help="API key (prefer env XP_API_KEY)")
    p.add_argument("-s", "--skill", default=None, help="Force a skill (commit|pr|fix|ship)")
    p.add_argument("-a", "--agent", default=None, help="Agent profile (ship|debug)")
    p.add_argument("--max-turns", type=int, default=None)
    p.add_argument("--yolo", action="store_true", help="Disable sandbox, blocklist, confirms")
    p.add_argument(
        "--allow-outside",
        action="store_true",
        help="Allow file tools outside cwd",
    )
    p.add_argument("--no-stream", action="store_true", help="Disable streaming")
    p.add_argument(
        "--no-auto-skill",
        action="store_true",
        help="Disable automatic skill matching from the prompt",
    )
    p.add_argument(
        "--web",
        action="store_true",
        help="Enable fetch_url / web_search tools",
    )
    p.add_argument(
        "--no-spawn",
        action="store_true",
        help="Disable spawn_task sub-investigations",
    )
    p.add_argument(
        "--api-backend",
        default=None,
        choices=["chat_completions", "messages"],
        help="chat_completions (OpenAI) or messages (Anthropic)",
    )
    p.add_argument("-C", "--cwd", default=None, help="Working directory")
    p.add_argument("-q", "--quiet", action="store_true", help="Less tool logging")


def main(argv: list[str] | None = None) -> None:
    argv = list(sys.argv[1:] if argv is None else argv)
    console = Console()

    reserved = {
        "run",
        "chat",
        "skills",
        "sessions",
        "doctor",
        "init",
        "config",
        "help",
    }

    if argv and not argv[0].startswith("-") and argv[0] not in reserved:
        if argv[0].startswith("/") or get_skill(argv[0]):
            skill_name = argv[0].lstrip("/")
            rest = argv[1:]
            new = ["run", "--skill", skill_name]
            if rest:
                new.extend(rest)
            else:
                new.append(f"Execute the /{skill_name} skill for the current workspace.")
            argv = new
        else:
            argv = ["run", *argv]

    if not argv:
        argv = ["chat"]

    parser = build_parser()
    args = parser.parse_args(argv)

    if args.cmd == "skills":
        _cmd_skills(console, getattr(args, "json", False))
        return
    if args.cmd == "sessions":
        _cmd_sessions(console, as_json=args.json, limit=args.n)
        return
    if args.cmd == "doctor":
        _cmd_doctor(console, args)
        return
    if args.cmd == "init":
        _cmd_init(console, force=args.force)
        return
    if args.cmd == "config":
        _cmd_config(console, as_json=getattr(args, "json", False))
        return
    if args.cmd == "chat":
        _cmd_chat(console, args)
        return
    if args.cmd == "run":
        prompt = " ".join(args.prompt).strip()
        if getattr(args, "prompt_flag", None):
            flag = args.prompt_flag.strip()
            prompt = f"{prompt} {flag}".strip() if prompt else flag
        if not prompt and not sys.stdin.isatty():
            prompt = sys.stdin.read().strip()
        if not prompt:
            parser.error("run requires a prompt (or pipe stdin / -p)")
        _cmd_run(console, args, prompt)
        return

    parser.print_help()


def _make_config(args: argparse.Namespace):
    cwd = Path(args.cwd).expanduser().resolve() if getattr(args, "cwd", None) else Path.cwd()
    return load_config(
        model=getattr(args, "model", None),
        base_url=getattr(args, "base_url", None),
        api_key=getattr(args, "api_key", None),
        max_turns=getattr(args, "max_turns", None),
        yolo=True if getattr(args, "yolo", False) else None,
        stream=False if getattr(args, "no_stream", False) else None,
        allow_outside=True if getattr(args, "allow_outside", False) else None,
        auto_skill=False if getattr(args, "no_auto_skill", False) else None,
        enable_web=True if getattr(args, "web", False) else None,
        enable_spawn=False if getattr(args, "no_spawn", False) else None,
        api_backend=getattr(args, "api_backend", None),
        cwd=cwd,
    )


def _resolve_skill(args: argparse.Namespace, cfg, prompt: str | None = None):
    name = getattr(args, "skill", None)
    if name:
        skill = get_skill(name, extra_paths=cfg.skills_paths)
        if not skill:
            raise SystemExit(f"Unknown skill: {name}. Try: xp skills")
        return skill, "cli"
    if cfg.auto_skill and prompt:
        hit = match_skill(prompt, extra_paths=cfg.skills_paths)
        if hit:
            return hit[0], f"auto:{hit[1]:.1f}"
    return None, ""


def _event_handler(console: Console, quiet: bool, as_json: bool = False):
    def on_event(kind: str, text: str) -> None:
        if as_json:
            return
        if quiet and kind in ("tool_result", "status", "usage", "diff"):
            return
        if kind == "assistant":
            console.print(Panel(Markdown(text), title="xp", border_style="cyan"))
        elif kind == "assistant_delta":
            console.print(text, end="")
        elif kind == "tool_call":
            console.print(f"[yellow]→[/] {text}")
        elif kind == "tool_result":
            preview = text if len(text) <= 800 else text[:800] + "\n…"
            console.print(f"[dim]{preview}[/]")
        elif kind == "diff":
            style_map = {
                "green": "green",
                "red": "red",
                "cyan": "cyan",
                "dim": "dim",
                "bold": "bold",
            }
            for style, line in format_diff_for_terminal(text):
                console.print(f"[{style_map.get(style, 'dim')}]{escape(line)}[/]")
        elif kind in ("status", "usage"):
            console.print(f"[dim]{text}[/]")

    return on_event


def _cmd_run(console: Console, args: argparse.Namespace, prompt: str) -> None:
    cfg = _make_config(args)
    cfg.require_api_key()
    skill, how = _resolve_skill(args, cfg, prompt)
    as_json = getattr(args, "json", False)
    quiet = getattr(args, "quiet", False) or as_json
    if skill and how.startswith("auto") and not quiet:
        console.print(f"[dim]auto skill → /{skill.name} ({how})[/]")

    agent = Agent(
        cfg,
        skill=skill,
        agent_name=getattr(args, "agent", None),
        console=console,
        on_event=_event_handler(console, quiet, as_json=as_json),
        persist=False,
    )
    try:
        result = agent.run(prompt)
        if as_json:
            print(
                json.dumps(
                    {
                        "result": result,
                        "usage": agent.total_usage,
                        "model": cfg.model,
                    },
                    ensure_ascii=False,
                )
            )
            return
        if result:
            console.print()
            console.print(Panel(Markdown(result), title="result", border_style="green"))
    finally:
        agent.close()


def _cmd_chat(console: Console, args: argparse.Namespace) -> None:
    cfg = _make_config(args)
    cfg.require_api_key()
    skill, how = _resolve_skill(args, cfg, None)
    if skill and how == "cli":
        console.print(f"[dim]skill → /{skill.name}[/]")

    messages = None
    session_id = getattr(args, "session", None)
    if getattr(args, "continue_session", False) and not session_id:
        session_id = latest_session_id()
        if not session_id:
            console.print("[yellow]No previous session found; starting new.[/]")
    if session_id:
        try:
            messages = load_session(session_id)
            console.print(f"[dim]resumed session {session_id} ({len(messages)} msgs)[/]")
        except FileNotFoundError as e:
            raise SystemExit(str(e)) from e
    else:
        session_id = new_session_id()

    agent = Agent(
        cfg,
        skill=skill,
        agent_name=getattr(args, "agent", None),
        console=console,
        on_event=_event_handler(console, getattr(args, "quiet", False)),
        messages=messages,
        session_id=session_id,
        persist=True,
    )
    console.print(
        Panel(
            f"[bold]xp[/] {__version__} · model [cyan]{cfg.model}[/] · [dim]{cfg.base_url}[/]\n"
            f"cwd [dim]{cfg.cwd}[/] · session [dim]{session_id}[/]\n"
            "Commands: [cyan]/skills[/] [cyan]/commit[/]… [cyan]/agent name[/] "
            "[cyan]/quit[/]",
            border_style="cyan",
        )
    )
    try:
        while True:
            try:
                line = console.input("[bold green]you>[/] ").strip()
            except (EOFError, KeyboardInterrupt):
                console.print(f"\nbye · session {session_id}")
                break
            if not line:
                continue
            if line in ("/quit", "/exit", ":q"):
                console.print(f"bye · session {session_id}")
                break
            if line in ("/skills", "/skill"):
                for s in load_skills(extra_paths=cfg.skills_paths):
                    console.print(f"  [cyan]/{s.name}[/] — {s.description}")
                continue
            if line.startswith("/") and not line.startswith("/skill ") and not line.startswith(
                "/agent "
            ):
                parts = line[1:].split(maxsplit=1)
                sk_name = parts[0]
                rest = parts[1] if len(parts) > 1 else f"Execute the /{sk_name} skill."
                sk = get_skill(sk_name, extra_paths=cfg.skills_paths)
                if sk:
                    agent.skill = sk
                    agent.messages[0] = {
                        "role": "system",
                        "content": build_system_prompt(
                            skill=sk,
                            agent=agent.agent_name,
                            system_extra=cfg.system_extra,
                            cwd=cfg.cwd,
                            enable_web=cfg.enable_web,
                            enable_spawn=cfg.enable_spawn,
                        ),
                    }
                    console.print(f"[dim]skill → /{sk.name}[/]")
                    line = rest
            if line.startswith("/skill "):
                name = line.split(maxsplit=1)[1].strip()
                sk = get_skill(name, extra_paths=cfg.skills_paths)
                if not sk:
                    console.print(f"[red]unknown skill {name}[/]")
                    continue
                agent.skill = sk
                agent.messages[0] = {
                    "role": "system",
                    "content": build_system_prompt(
                        skill=sk,
                        agent=agent.agent_name,
                        system_extra=cfg.system_extra,
                        cwd=cfg.cwd,
                        enable_web=cfg.enable_web,
                        enable_spawn=cfg.enable_spawn,
                    ),
                }
                console.print(f"[dim]skill → /{sk.name}[/]")
                continue
            if line.startswith("/agent "):
                agent.agent_name = line.split(maxsplit=1)[1].strip()
                agent.messages[0] = {
                    "role": "system",
                    "content": build_system_prompt(
                        skill=agent.skill,
                        agent=agent.agent_name,
                        system_extra=cfg.system_extra,
                        cwd=cfg.cwd,
                        enable_web=cfg.enable_web,
                        enable_spawn=cfg.enable_spawn,
                    ),
                }
                console.print(f"[dim]agent → {agent.agent_name}[/]")
                continue
            if cfg.auto_skill and not getattr(args, "skill", None):
                hit = match_skill(line, extra_paths=cfg.skills_paths)
                if hit and (agent.skill is None or agent.skill.name != hit[0].name):
                    agent.skill = hit[0]
                    agent.messages[0] = {
                        "role": "system",
                        "content": build_system_prompt(
                            skill=hit[0],
                            agent=agent.agent_name,
                            system_extra=cfg.system_extra,
                            cwd=cfg.cwd,
                            enable_web=cfg.enable_web,
                            enable_spawn=cfg.enable_spawn,
                        ),
                    }
                    console.print(f"[dim]auto skill → /{hit[0].name} ({hit[1]:.1f})[/]")

            result = agent.run(line)
            if result and not cfg.stream:
                console.print(Panel(Markdown(result), title="xp", border_style="cyan"))
            elif result and cfg.stream:
                console.print()
    finally:
        agent.close()


def _cmd_config(console: Console, *, as_json: bool) -> None:
    cfg = load_config()
    data = {
        "version": __version__,
        "config_file": str(user_config_path()),
        "model": cfg.model,
        "base_url": cfg.base_url,
        "api_backend": cfg.api_backend,
        "api_key_set": bool(cfg.api_key),
        "cwd": str(cfg.cwd),
        "sandbox": cfg.sandbox,
        "yolo": cfg.yolo,
        "stream": cfg.stream,
        "auto_skill": cfg.auto_skill,
        "enable_web": cfg.enable_web,
        "enable_spawn": cfg.enable_spawn,
        "enable_mcp": cfg.enable_mcp,
        "mcp_servers": [s.get("name") for s in cfg.mcp_servers],
        "skills_paths": cfg.skills_paths,
        "max_turns": cfg.max_turns,
        "max_retries": cfg.max_retries,
    }
    if as_json:
        print(json.dumps(data, indent=2, ensure_ascii=False))
        return
    console.print(Panel("[bold]xp config[/]", border_style="cyan"))
    for k, v in data.items():
        console.print(f"{k:16} {v}")


def _cmd_skills(console: Console, as_json: bool) -> None:
    skills = load_skills()
    if as_json:
        print(
            json.dumps(
                [{"name": s.name, "description": s.description} for s in skills],
                indent=2,
                ensure_ascii=False,
            )
        )
        return
    table = Table(title="xp skills")
    table.add_column("Name", style="cyan")
    table.add_column("Description")
    for s in skills:
        table.add_row(f"/{s.name}", s.description)
    console.print(table)
    console.print(f"[dim]dir: {skills_dir()}[/]")


def _cmd_sessions(console: Console, *, as_json: bool, limit: int) -> None:
    items = list_sessions(limit)
    if as_json:
        print(json.dumps(items, indent=2, ensure_ascii=False))
        return
    if not items:
        console.print("[dim]No sessions yet. Start with: xp chat[/]")
        return
    table = Table(title="xp sessions")
    table.add_column("ID", style="cyan")
    table.add_column("Model")
    table.add_column("Msgs")
    table.add_column("When")
    for it in items:
        when = time.strftime("%Y-%m-%d %H:%M", time.localtime(it["mtime"]))
        table.add_row(it["id"], it.get("model") or "-", str(it.get("messages", 0)), when)
    console.print(table)
    console.print("[dim]Resume: xp chat --continue   or   xp chat --session <id>[/]")


def _cmd_doctor(console: Console, args: argparse.Namespace) -> None:
    cfg = load_config(
        model=args.model,
        base_url=args.base_url,
        api_key=args.api_key,
    )
    console.print(Panel("[bold]xp doctor[/]", border_style="cyan"))
    console.print(f"version:     {__version__}")
    cfg_path = user_config_path()
    console.print(
        f"config file: {cfg_path} ({'exists' if cfg_path.is_file() else 'missing'})"
    )
    if cfg.api_key:
        console.print(f"api_key:     set ({cfg.api_key[:4]}…)")
        if cfg_path.is_file() and "api_key" in cfg_path.read_text(encoding="utf-8"):
            console.print(
                "[yellow]warning:[/] api_key stored in plaintext config; prefer env XP_API_KEY"
            )
    else:
        console.print("api_key:     [red]NOT SET[/]")
    console.print(f"base_url:    {cfg.base_url}")
    console.print(f"model:       {cfg.model}")
    console.print(
        f"sandbox:     {cfg.sandbox}  yolo={cfg.yolo}  stream={cfg.stream}  "
        f"web={cfg.enable_web}  spawn={cfg.enable_spawn}"
    )
    console.print(f"api_backend: {cfg.api_backend}")
    amd = agents_md_path()
    console.print(f"AGENTS.md:   {amd} ({'ok' if amd.is_file() else 'missing'})")
    console.print(f"skills:      {skills_dir()} ({len(load_skills())} found)")
    console.print()
    console.print(
        "[dim]Env: XP_API_KEY | OPENAI_API_KEY | XAI_API_KEY, XP_BASE_URL, XP_MODEL[/]"
    )
    if not cfg.api_key:
        console.print(
            "\n[yellow]Tip:[/] run [cyan]xp init[/] then edit the config, or export XP_API_KEY."
        )
        return

    if args.probe or True:
        # lightweight probe when key present
        try:
            from openai import OpenAI

            client = OpenAI(api_key=cfg.api_key, base_url=cfg.base_url, timeout=30)
            # Prefer models.list; fall back to tiny completion
            try:
                models = client.models.list()
                ids = [m.id for m in getattr(models, "data", [])[:8]]
                console.print(f"probe:       [green]ok[/] models.list → {ids or '(empty list)'}")
            except Exception:
                resp = client.chat.completions.create(
                    model=cfg.model,
                    messages=[{"role": "user", "content": "ping"}],
                    max_tokens=5,
                )
                text = (resp.choices[0].message.content or "")[:40]
                console.print(f"probe:       [green]ok[/] completion → {text!r}")
        except Exception as e:  # noqa: BLE001
            console.print(f"probe:       [red]fail[/] {e}")


def _cmd_init(console: Console, *, force: bool) -> None:
    path = user_config_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.is_file() and not force:
        console.print(f"[yellow]Already exists:[/] {path} (use --force to overwrite)")
        return
    sample = """# xp standalone runtime config
# https://github.com/245678000000/xp

# Prefer env vars for secrets:
#   export XP_API_KEY=sk-...
# api_key = "sk-..."

base_url = "https://api.openai.com/v1"
model = "gpt-4o"
# max_turns = 40
# temperature = 0.2
# stream = true
# sandbox = true          # file tools limited to cwd
# confirm_risky = true    # ask before rm/sudo/git push
# yolo = false            # disables sandbox + confirms + blocklist
# max_messages = 80
# max_retries = 4
# auto_skill = true       # match /commit /fix … from natural language
# enable_web = false      # fetch_url + web_search (or XP_WEB=1 / --web)
# enable_spawn = true     # spawn_task read-only sub-agents
# enable_mcp = true
# api_backend = "chat_completions"  # or "messages" for Anthropic
# skills_paths = ["~/my-skills"]

# xAI:
# base_url = "https://api.x.ai/v1"
# model = "grok-3-mini"
# (set XAI_API_KEY)

# Anthropic (streaming supported):
# api_backend = "messages"
# base_url = "https://api.anthropic.com"
# model = "claude-sonnet-4-20250514"
# (set ANTHROPIC_API_KEY)

# MCP servers (stdio JSON-RPC):
# [[mcp_servers]]
# name = "filesystem"
# command = "npx"
# args = ["-y", "@modelcontextprotocol/server-filesystem", "/tmp"]

# OpenAI-compatible proxy:
# base_url = "https://your-proxy.example/v1"
# model = "your-model-id"
"""
    path.write_text(sample, encoding="utf-8")
    console.print(f"[green]Wrote[/] {path}")
    console.print("Edit model / set XP_API_KEY, then: [cyan]xp doctor[/] && [cyan]xp chat[/]")


if __name__ == "__main__":
    main()
