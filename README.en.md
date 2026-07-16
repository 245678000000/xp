# xp

[中文](README.md) | **English**

**xp** is a **standalone** coding agent harness: tool loop, skills, global rules, and any **OpenAI-compatible** API.

- **No Grok required** — install with pip, set an API key, run  
- **Optional Grok Build layer** — same skills / `AGENTS.md` can still be installed into `~/.grok`

Inspired by [xai-org/grok-build](https://github.com/xai-org/grok-build), with a self-contained Python CLI runtime.

---

## Quick start (standalone)

### 1. Install

Python **3.9+**.

```bash
git clone https://github.com/245678000000/xp.git
cd xp
python3 -m pip install -e .
# or: pip install -r requirements.txt && export PYTHONPATH=$PWD/src
```

### 2. Configure API & model

```bash
xp init
# edit ~/.config/xp/config.toml
```

```toml
api_key = "sk-..."
base_url = "https://api.openai.com/v1"
model = "gpt-4o"
```

Env vars: `XP_API_KEY` / `OPENAI_API_KEY` / `XAI_API_KEY`, `XP_BASE_URL`, `XP_MODEL`.

```bash
xp doctor
```

### 3. Run

```bash
xp "What is this repo?"
xp chat
xp /commit
xp /fix "failing test ..."
xp -m gpt-4o "..."
xp skills
```

Tools: `bash`, `read_file`, `write_file`, `str_replace`, `list_dir`, `grep`.

---

## Optional: Grok Build

```bash
./install.sh        # or ./install.sh --link
```

| Mode | Command | Needs |
|------|---------|--------|
| Standalone | `xp "..."` | Python + API key |
| Grok layer | `grok` | [Grok Build](https://x.ai/cli) |

---

## Layout

```text
src/xp/     # Python runtime (CLI + tool loop)
skills/     # /commit /pr /fix /ship
AGENTS.md   # global rules
install.sh  # install into ~/.grok
```

## License

Apache-2.0 — see [LICENSE](LICENSE).
