"""xp CLI — standalone coding agent."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.table import Table

from xp import __version__
from xp.agent import Agent
from xp.config import load_config
from xp.paths import agents_md_path, skills_dir, user_config_path
from xp.prompts import build_system_prompt
from xp.skills import get_skill, load_skills


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

    chat = sub.add_parser("chat", help="Interactive multi-turn chat")
    _add_common(chat)

    skills = sub.add_parser("skills", help="List skills")
    skills.add_argument("--json", action="store_true")

    doctor = sub.add_parser("doctor", help="Show config / paths / connectivity hints")
    doctor.add_argument("--model", default=None)
    doctor.add_argument("--base-url", default=None)
    doctor.add_argument("--api-key", default=None)

    init = sub.add_parser("init", help="Write a sample ~/.config/xp/config.toml")
    init.add_argument("--force", action="store_true", help="Overwrite existing config")

    return p


def _add_common(p: argparse.ArgumentParser) -> None:
    p.add_argument("-m", "--model", default=None, help="Model id")
    p.add_argument("--base-url", default=None, help="OpenAI-compatible base URL")
    p.add_argument("--api-key", default=None, help="API key (prefer env XP_API_KEY)")
    p.add_argument("-s", "--skill", default=None, help="Force a skill (commit|pr|fix|ship)")
    p.add_argument("-a", "--agent", default=None, help="Agent profile (ship|debug)")
    p.add_argument("--max-turns", type=int, default=None)
    p.add_argument("--yolo", action="store_true", help="Disable bash safety blocklist")
    p.add_argument("-C", "--cwd", default=None, help="Working directory")
    p.add_argument("-q", "--quiet", action="store_true", help="Less tool logging")


def main(argv: list[str] | None = None) -> None:
    argv = list(sys.argv[1:] if argv is None else argv)
    console = Console()

    # Bare prompt / skill shorthand
    if argv and not argv[0].startswith("-") and argv[0] not in {
        "run",
        "chat",
        "skills",
        "doctor",
        "init",
        "help",
    }:
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
    if args.cmd == "doctor":
        _cmd_doctor(console, args)
        return
    if args.cmd == "init":
        _cmd_init(console, force=args.force)
        return
    if args.cmd == "chat":
        _cmd_chat(console, args)
        return
    if args.cmd == "run":
        prompt = " ".join(args.prompt).strip()
        if not prompt and not sys.stdin.isatty():
            prompt = sys.stdin.read().strip()
        if not prompt:
            parser.error("run requires a prompt (or pipe stdin)")
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
        cwd=cwd,
    )


def _resolve_skill(args: argparse.Namespace):
    name = getattr(args, "skill", None)
    if not name:
        return None
    skill = get_skill(name)
    if not skill:
        raise SystemExit(f"Unknown skill: {name}. Try: xp skills")
    return skill


def _cmd_run(console: Console, args: argparse.Namespace, prompt: str) -> None:
    cfg = _make_config(args)
    cfg.require_api_key()
    skill = _resolve_skill(args)
    quiet = getattr(args, "quiet", False)

    def on_event(kind: str, text: str) -> None:
        if quiet and kind in ("tool_result", "status"):
            return
        if kind == "assistant":
            console.print(Panel(Markdown(text), title="xp", border_style="cyan"))
        elif kind == "tool_call":
            console.print(f"[yellow]→[/] {text}")
        elif kind == "tool_result":
            preview = text if len(text) <= 800 else text[:800] + "\n…"
            console.print(f"[dim]{preview}[/]")
        elif kind == "status":
            console.print(f"[dim]{text}[/]")

    agent = Agent(
        cfg,
        skill=skill,
        agent_name=getattr(args, "agent", None),
        console=console,
        on_event=on_event,
    )
    result = agent.run(prompt)
    if result:
        console.print()
        console.print(Panel(Markdown(result), title="result", border_style="green"))


def _cmd_chat(console: Console, args: argparse.Namespace) -> None:
    cfg = _make_config(args)
    cfg.require_api_key()
    skill = _resolve_skill(args)
    agent = Agent(cfg, skill=skill, agent_name=getattr(args, "agent", None), console=console)
    console.print(
        Panel(
            f"[bold]xp[/] {__version__} · model [cyan]{cfg.model}[/] · [dim]{cfg.base_url}[/]\n"
            f"cwd [dim]{cfg.cwd}[/]\n"
            "Commands: [cyan]/skill name[/], [cyan]/agent name[/], [cyan]/quit[/]",
            border_style="cyan",
        )
    )
    while True:
        try:
            line = console.input("[bold green]you>[/] ").strip()
        except (EOFError, KeyboardInterrupt):
            console.print("\nbye")
            break
        if not line:
            continue
        if line in ("/quit", "/exit", ":q"):
            console.print("bye")
            break
        if line.startswith("/skill "):
            name = line.split(maxsplit=1)[1].strip()
            sk = get_skill(name)
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
                ),
            }
            console.print(f"[dim]agent → {agent.agent_name}[/]")
            continue
        result = agent.run(line)
        if result:
            console.print(Panel(Markdown(result), title="xp", border_style="cyan"))


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
    else:
        console.print("api_key:     [red]NOT SET[/]")
    console.print(f"base_url:    {cfg.base_url}")
    console.print(f"model:       {cfg.model}")
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


def _cmd_init(console: Console, *, force: bool) -> None:
    path = user_config_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.is_file() and not force:
        console.print(f"[yellow]Already exists:[/] {path} (use --force to overwrite)")
        return
    sample = """# xp standalone runtime config
# https://github.com/245678000000/xp

# api_key = "sk-..."          # or set XP_API_KEY / OPENAI_API_KEY / XAI_API_KEY
base_url = "https://api.openai.com/v1"
model = "gpt-4o"
# max_turns = 40
# temperature = 0.2
# yolo = false

# xAI example:
# base_url = "https://api.x.ai/v1"
# model = "grok-3-mini"
# api_key from env XAI_API_KEY

# OpenAI-compatible proxy example:
# base_url = "https://your-proxy.example/v1"
# model = "your-model-id"
"""
    path.write_text(sample, encoding="utf-8")
    console.print(f"[green]Wrote[/] {path}")
    console.print("Edit api_key / model, then: [cyan]xp doctor[/] && [cyan]xp \"hello\"[/]")


if __name__ == "__main__":
    main()
