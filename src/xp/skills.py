"""Discover and load SKILL.md packages."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List, Optional, Sequence

from xp.paths import skills_dir

FRONTMATTER_RE = re.compile(r"\A---\s*\n(.*?)\n---\s*\n(.*)\Z", re.DOTALL)


@dataclass
class Skill:
    name: str
    description: str
    body: str
    path: Path

    def full_text(self) -> str:
        return f"# Skill: {self.name}\n\n{self.description}\n\n{self.body}".strip()


def _parse_frontmatter(text: str) -> tuple[dict[str, str], str]:
    m = FRONTMATTER_RE.match(text)
    if not m:
        return {}, text
    raw, body = m.group(1), m.group(2)
    meta: dict[str, str] = {}
    key: str | None = None
    buf: list[str] = []
    for line in raw.splitlines():
        if re.match(r"^[A-Za-z0-9_-]+:\s*", line) and not line.startswith(" "):
            if key is not None:
                meta[key] = "\n".join(buf).strip().strip("\"'")
            key, _, rest = line.partition(":")
            key = key.strip()
            rest = rest.strip()
            if rest == ">" or rest == "|":
                buf = []
            else:
                buf = [rest] if rest else []
        else:
            buf.append(line.strip())
    if key is not None:
        meta[key] = "\n".join(buf).strip().strip("\"'")
    return meta, body.strip()


def _load_from_dir(root: Path) -> List[Skill]:
    if not root.is_dir():
        return []
    skills: List[Skill] = []
    for skill_md in sorted(root.glob("*/SKILL.md")):
        text = skill_md.read_text(encoding="utf-8")
        meta, body = _parse_frontmatter(text)
        name = meta.get("name") or skill_md.parent.name
        description = meta.get("description") or body.split("\n\n", 1)[0][:200]
        description = re.sub(r"\s+", " ", description).strip()
        skills.append(Skill(name=name, description=description, body=body, path=skill_md))
    return skills


def skill_search_dirs(extra: Sequence[str] | None = None) -> List[Path]:
    """Ordered dirs: extras first (higher priority), then bundled skills_dir."""
    dirs: List[Path] = []
    seen = set()
    for raw in list(extra or []) + [str(skills_dir())]:
        p = Path(raw).expanduser().resolve()
        key = str(p)
        if key in seen:
            continue
        seen.add(key)
        dirs.append(p)
    return dirs


def load_skills(
    directory: Path | None = None,
    extra_paths: Sequence[str] | None = None,
) -> list[Skill]:
    if directory is not None:
        return _load_from_dir(directory)
    by_name: dict[str, Skill] = {}
    # later dirs are lower priority — load low priority first, then override
    for d in reversed(skill_search_dirs(extra_paths)):
        for s in _load_from_dir(d):
            by_name[s.name.lower()] = s
    return sorted(by_name.values(), key=lambda s: s.name)


def get_skill(
    name: str,
    directory: Path | None = None,
    extra_paths: Sequence[str] | None = None,
) -> Skill | None:
    name = name.lstrip("/").lower()
    for s in load_skills(directory, extra_paths=extra_paths):
        if s.name.lower() == name:
            return s
    return None


def skills_catalog(
    skills: list[Skill] | None = None,
    extra_paths: Sequence[str] | None = None,
) -> str:
    items = skills if skills is not None else load_skills(extra_paths=extra_paths)
    if not items:
        return "(no skills installed)"
    lines = ["Available skills (invoke by name when relevant):"]
    for s in items:
        lines.append(f"- /{s.name}: {s.description}")
    return "\n".join(lines)
