"""Build system prompts from AGENTS.md, skills, agent profiles."""

from __future__ import annotations

from pathlib import Path

from xp.paths import agents_dir, agents_md_path, project_agents_md
from xp.skills import Skill, skills_catalog


def _read(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8").strip()
    except OSError:
        return ""


def load_agent_profile(name: str) -> str:
    """Load agents/<name>.md body if present."""
    p = agents_dir() / f"{name}.md"
    if not p.is_file():
        return ""
    text = _read(p)
    if text.startswith("---"):
        parts = text.split("---", 2)
        if len(parts) >= 3:
            return parts[2].strip()
    return text


def build_system_prompt(
    *,
    skill: Skill | None = None,
    agent: str | None = None,
    system_extra: str = "",
    cwd: Path | None = None,
) -> str:
    parts: list[str] = []

    parts.append(
        "You are **xp**, a terminal coding agent with tools "
        "(bash, read_file, write_file, str_replace, list_dir, grep).\n"
        "Work carefully. Prefer evidence over guessing. "
        "Use tools when you need filesystem or shell access.\n"
        "When the task is done, give a concise final answer without more tool calls."
    )

    global_md = agents_md_path()
    if global_md.is_file():
        parts.append("## Global harness rules (AGENTS.md)\n\n" + _read(global_md))

    proj = project_agents_md(cwd)
    if proj and proj.resolve() != global_md.resolve():
        parts.append(f"## Project rules ({proj})\n\n" + _read(proj))

    if agent:
        profile = load_agent_profile(agent)
        if profile:
            parts.append(f"## Active agent: {agent}\n\n{profile}")

    parts.append("## Skills catalog\n\n" + skills_catalog())

    if skill:
        parts.append(
            f"## Active skill: /{skill.name}\n\n"
            f"Follow this skill for the current task.\n\n{skill.full_text()}"
        )

    if system_extra:
        parts.append("## Extra instructions\n\n" + system_extra.strip())

    cwd_s = str((cwd or Path.cwd()).resolve())
    parts.append(f"## Workspace\n\nCurrent working directory: `{cwd_s}`")

    return "\n\n---\n\n".join(parts)
