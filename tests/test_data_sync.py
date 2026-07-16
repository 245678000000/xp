"""Ensure packaged data matches repo harness sources."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _file_map(base: Path, pattern: str) -> dict[str, str]:
    out = {}
    for p in base.glob(pattern):
        rel = str(p.relative_to(base))
        out[rel] = p.read_text(encoding="utf-8")
    return out


def test_skills_synced():
    src = _file_map(ROOT / "skills", "*/SKILL.md")
    pkg = _file_map(ROOT / "src/xp/data/skills", "*/SKILL.md")
    assert src, "repo skills missing"
    assert src == pkg, "run scripts/sync_data.sh — skills/ and src/xp/data/skills/ differ"


def test_agents_md_synced():
    a = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    b = (ROOT / "src/xp/data/AGENTS.md").read_text(encoding="utf-8")
    assert a == b, "run scripts/sync_data.sh — AGENTS.md out of sync"
