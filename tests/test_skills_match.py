from __future__ import annotations

from xp.skills import match_skill, score_skill, get_skill, load_skills


def test_match_commit():
    hit = match_skill("please create a git commit for my changes")
    assert hit is not None
    skill, score = hit
    assert skill.name == "commit"
    assert score >= 4


def test_match_fix_stacktrace():
    hit = match_skill("bug: stack trace AssertionError in test_login")
    assert hit is not None
    assert hit[0].name == "fix"


def test_match_explicit_slash():
    hit = match_skill("run /ship for this feature")
    assert hit is not None
    assert hit[0].name == "ship"


def test_no_match_generic():
    hit = match_skill("what is 2+2?")
    assert hit is None


def test_score_name_beats_noise():
    commit = get_skill("commit")
    fix = get_skill("fix")
    assert commit and fix
    q = "I want to commit"
    assert score_skill(q, commit) > score_skill(q, fix)
