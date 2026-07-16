# Contributing to xp

## Dev setup

```bash
git clone https://github.com/245678000000/xp.git
cd xp
python3 -m pip install -e ".[dev]"
bash scripts/sync_data.sh
pytest -q
```

## Layout

| Path | Role |
|------|------|
| `src/xp/` | Standalone runtime (CLI, agent loop, tools) |
| `skills/`, `AGENTS.md`, `agents/` | Portable harness content (also used by Grok) |
| `src/xp/data/` | Packaged copy for wheel installs — keep in sync |
| `tests/` | pytest |
| `examples/` | Sample configs |

After editing `skills/` or `AGENTS.md`:

```bash
bash scripts/sync_data.sh
```

CI fails if package data drifts (`tests/test_data_sync.py`).

## Code style

- Python 3.9+ compatible (`from __future__ import annotations` is fine).
- Prefer small modules; keep tools in `tools.py` / `web.py` / `mcp_client.py`.
- No new hard dependencies without a clear need.
- Do not commit secrets or live API keys.

## Skills

Add `skills/<name>/SKILL.md` with YAML frontmatter (`name`, `description`) and steps.
Update aliases in `src/xp/skills.py` `_ALIASES` if you want auto-match.

## PRs

- Keep changes focused.
- Add/adjust tests when behavior changes.
- Update `CHANGELOG.md` under a new version heading when user-facing.

## Release

See [docs/PUBLISH.md](docs/PUBLISH.md).
