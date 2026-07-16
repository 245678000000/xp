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


_TOKEN_RE = re.compile(r"[a-z0-9_\u4e00-\u9fff]{2,}", re.I)

# Extra trigger phrases beyond description text
_ALIASES: dict[str, tuple[str, ...]] = {
    "commit": ("commit", "提交", "git commit", "conventional commit", "save to git"),
    "pr": ("pull request", "开 pr", "创建 pr", "github pr", "合并请求"),
    "fix": ("bug", "fix", "修复", "stack trace", "报错", "failure", "crash", "flaky"),
    "ship": ("ship", "交付", "implement and commit", "做完并提交", "end-to-end"),
}


def _tokens(text: str) -> set[str]:
    return {t.lower() for t in _TOKEN_RE.findall(text.lower())}


def score_skill(query: str, skill: Skill) -> float:
    """Heuristic relevance score (higher = better)."""
    q = query.strip().lower()
    if not q:
        return 0.0
    score = 0.0
    name = skill.name.lower()
    # Explicit /name or bare name as a word
    if re.search(rf"(^|[^\w])/{re.escape(name)}([^\w]|$)", q):
        score += 10
    if re.search(rf"(^|[^\w]){re.escape(name)}([^\w]|$)", q):
        score += 6
    for phrase in _ALIASES.get(name, ()):
        if phrase.lower() in q:
            score += 5
    q_toks = _tokens(q)
    d_toks = _tokens(skill.description + " " + skill.name)
    # Drop ultra-common words
    stop = {
        "the",
        "and",
        "for",
        "with",
        "from",
        "this",
        "that",
        "when",
        "user",
        "wants",
        "use",
        "says",
        "or",
        "a",
        "to",
        "of",
        "in",
        "on",
    }
    q_toks -= stop
    d_toks -= stop
    if not q_toks or not d_toks:
        return score
    overlap = q_toks & d_toks
    score += 1.5 * len(overlap)
    # Prefer denser overlap relative to query
    score += 2.0 * (len(overlap) / max(1, len(q_toks)))
    return score


def match_skill(
    query: str,
    *,
    extra_paths: Sequence[str] | None = None,
    min_score: float = 4.0,
    skills: list[Skill] | None = None,
) -> Optional[tuple[Skill, float]]:
    """
    Pick the best skill for a user message, or None if confidence is low.
    Returns (skill, score).
    """
    items = skills if skills is not None else load_skills(extra_paths=extra_paths)
    if not items:
        return None
    ranked = sorted(
        ((s, score_skill(query, s)) for s in items),
        key=lambda x: x[1],
        reverse=True,
    )
    best, best_score = ranked[0]
    if best_score < min_score:
        return None
    # Require clear winner when two skills are close
    if len(ranked) > 1 and best_score - ranked[1][1] < 1.0 and best_score < min_score + 3:
        return None
    return best, best_score
