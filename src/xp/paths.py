"""Resolve package data and user config locations."""

from __future__ import annotations

import os
from pathlib import Path


def _package_data() -> Path:
    return Path(__file__).resolve().parent / "data"


def repo_or_data_root() -> Path:
    """
    Prefer git checkout root (AGENTS.md + skills/ next to pyproject).
    Fall back to packaged data under src/xp/data (installed wheel).
    """
    here = Path(__file__).resolve()
    # src/xp/paths.py → parents[2] == repo root when developing
    for candidate in (here.parents[2], here.parents[1], Path.cwd()):
        if (candidate / "AGENTS.md").is_file() and (candidate / "skills").is_dir():
            return candidate
    data = _package_data()
    if (data / "AGENTS.md").is_file() or (data / "skills").is_dir():
        return data
    return here.parents[2]


def agents_md_path() -> Path:
    root = repo_or_data_root()
    p = root / "AGENTS.md"
    if p.is_file():
        return p
    packaged = _package_data() / "AGENTS.md"
    return packaged if packaged.is_file() else p


def skills_dir() -> Path:
    root = repo_or_data_root()
    p = root / "skills"
    if p.is_dir():
        return p
    packaged = _package_data() / "skills"
    return packaged if packaged.is_dir() else p


def agents_dir() -> Path:
    root = repo_or_data_root()
    p = root / "agents"
    if p.is_dir():
        return p
    packaged = _package_data() / "agents"
    return packaged if packaged.is_dir() else p


def user_config_path() -> Path:
    if env := os.environ.get("XP_CONFIG"):
        return Path(env).expanduser()
    xdg = os.environ.get("XDG_CONFIG_HOME")
    if xdg:
        return Path(xdg) / "xp" / "config.toml"
    return Path.home() / ".config" / "xp" / "config.toml"


def project_agents_md(cwd: Path | None = None) -> Path | None:
    """Walk from cwd up looking for AGENTS.md."""
    cur = (cwd or Path.cwd()).resolve()
    for directory in [cur, *cur.parents]:
        for name in ("AGENTS.md", "AGENT.md", "Agents.md"):
            p = directory / name
            if p.is_file():
                return p
        if directory.parent == directory:
            break
    return None
