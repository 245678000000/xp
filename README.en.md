# xp

[中文](README.md) | **English**

**xp** is a **standalone** coding agent harness: tool loop, skills, global rules, OpenAI-compatible APIs.

- **No Grok required** — set an API key and run  
- **Optional Grok Build layer** — same skills via `./install.sh` → `~/.grok`

**v0.8:** P3 remainder — opt-in telemetry (default off), light TUI (`chat --tui`), privacy docs.

## Install

```bash
pip install "git+https://github.com/245678000000/xp.git"
# after PyPI: pip install xp-harness
# or: git clone … && pip install -e ".[dev]"
```

Publish guide: [docs/PUBLISH.md](docs/PUBLISH.md).

## Configure

```bash
xp init
export XP_API_KEY=sk-...
# edit ~/.config/xp/config.toml  (model, base_url, sandbox, …)
xp doctor
```

Env: `XP_API_KEY` / `OPENAI_API_KEY` / `XAI_API_KEY`, `XP_BASE_URL`, `XP_MODEL`, `XP_YOLO`, `XP_NO_STREAM`, `XP_ALLOW_OUTSIDE`.

## Usage

```bash
xp "What is this repo?"
xp -p "list entrypoints"
xp chat --continue
xp sessions
xp /commit
xp "please commit my changes"   # auto → /commit
xp /fix "…"
xp run --json "list 3 files"
xp run --no-auto-skill "…"
xp skills
```

Tools: `bash`, files, `apply_patch`, `spawn_task`, optional web + **MCP** (`mcp__server__tool`).  
Skills: commit, pr, fix, ship, review, test, refactor, release.  
Anthropic streaming: `api_backend=messages` + `ANTHROPIC_API_KEY`.  
See `examples/`, `xp config`, `xp telemetry`, `docs/PRIVACY.md`.  
TUI: `pip install 'xp-harness[tui]'` then `xp chat --tui`.

## Dev

```bash
bash scripts/sync_data.sh && pytest -q
```

## License

Apache-2.0 — see [LICENSE](LICENSE).
