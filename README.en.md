# xp

[中文](README.md) | **English**

**xp** is a **standalone** coding agent harness: tool loop, skills, global rules, OpenAI-compatible APIs.

- **No Grok required** — set an API key and run  
- **Optional Grok Build layer** — same skills via `./install.sh` → `~/.grok`

**v0.3:** streaming, session resume, path sandbox, API retries, pytest + CI.

## Install

```bash
pip install "git+https://github.com/245678000000/xp.git"
# or: git clone … && pip install -e ".[dev]"
```

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
xp chat
xp chat --continue
xp sessions
xp /commit
xp /fix "…"
xp run --json "list 3 files"
xp skills
```

Tools: `bash`, `read_file`, `write_file`, `str_replace`, `list_dir`, `grep`.  
Default sandbox: file tools stay under cwd; risky bash asks for confirm.

## Dev

```bash
bash scripts/sync_data.sh && pytest -q
```

## License

Apache-2.0 — see [LICENSE](LICENSE).
