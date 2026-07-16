from __future__ import annotations

from xp.skills import get_skill, load_skills, _parse_frontmatter


def test_load_bundled_skills():
    skills = load_skills()
    names = {s.name for s in skills}
    assert {"commit", "pr", "fix", "ship"} <= names


def test_get_skill_commit():
    s = get_skill("commit")
    assert s is not None
    assert "conventional" in s.description.lower() or "commit" in s.description.lower()
    assert "git" in s.body.lower()


def test_parse_frontmatter_folded():
    text = """---
name: demo
description: >
  multi
  line
---

# Body

hello
"""
    meta, body = _parse_frontmatter(text)
    assert meta["name"] == "demo"
    assert "multi" in meta["description"]
    assert "Body" in body
