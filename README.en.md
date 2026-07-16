# xp

[中文](README.md) | **English**

**xp** is a personal coding harness layer for [Grok Build](https://github.com/xai-org/grok-build) — skills, agents, personas, and global rules that make day-to-day engineering more consistent.

It does **not** fork the Rust TUI/runtime. It sits on Grok Build's official extension points:

| Grok Build | xp |
|------------|-----|
| Global rules | `AGENTS.md` |
| Skills | `skills/*` |
| Agents | `agents/*` |
| Personas | `personas/*` |
| Roles | `roles/*` |

Inspired by [xai-org/grok-build](https://github.com/xai-org/grok-build).

## Install

Requires [Grok Build](https://x.ai/cli) (`grok`).

```bash
git clone https://github.com/245678000000/xp.git
cd xp
./install.sh          # copy into ~/.grok
# or
./install.sh --link   # symlink (edits track this repo)
```

Then start a new Grok session. Skills show up under `/`.

### Manual install

```bash
# Skills only (config path)
# In ~/.grok/config.toml:
# [skills]
# paths = ["~/xp/skills"]
```

Or copy pieces into `~/.grok/` yourself:

```text
~/.grok/AGENTS.md
~/.grok/agents/
~/.grok/skills/
~/.grok/personas/
~/.grok/roles/
```

## What's inside

### Skills (slash commands)

| Command | Purpose |
|---------|---------|
| `/commit` | Conventional commit from current changes (no push) |
| `/pr` | Push branch + create/update a GitHub PR |
| `/fix` | Reproduce → localize → fix → prove |
| `/ship` | Implement → verify → commit |

### Agents

| Agent | Purpose |
|-------|---------|
| `ship` | End-to-end delivery: implement + verify |
| `debug` | Root-cause debugging |

Open `/config-agents` (or `/agents`) in the TUI to switch.

### Personas

| Persona | Style |
|---------|--------|
| `concise` | Short, high-signal |
| `thorough` | Deep, path/evidence-heavy |

### Global rules

`AGENTS.md` sets defaults for all projects: understand before editing, smallest change, verify, safe git, no secrets.

Project-level `AGENTS.md` / `.grok/rules/` still win on conflict.

## Layout

```text
xp/
├── AGENTS.md
├── agents/
│   ├── ship.md
│   └── debug.md
├── skills/
│   ├── commit/SKILL.md
│   ├── pr/SKILL.md
│   ├── fix/SKILL.md
│   └── ship/SKILL.md
├── personas/
│   ├── concise.toml
│   └── thorough.toml
├── roles/
│   └── reviewer.toml
├── install.sh
├── README.md          # 中文
└── README.en.md       # English
```

## Design principles

1. **Don't rewrite the harness runtime** — reuse Grok Build's tool loop, permissions, sessions, MCP.
2. **Workflows live in skills; defaults live in AGENTS.md.**
3. **Safe by default** — no force-push, no `--no-verify`, no secret commits.
4. **Evolvable** — new workflow = new `skills/<name>/SKILL.md`.

## Verify

After install, in a fresh `grok` session:

1. `/` → see `commit` / `pr` / `fix` / `ship`
2. `/config-agents` → see `ship` / `debug`
3. `/personas` → see `concise` / `thorough`
4. Optional: `grok inspect`

## Extend

```bash
mkdir -p skills/my-flow
# Add SKILL.md with name + description frontmatter + steps
./install.sh   # re-sync to ~/.grok
```

## License

Apache-2.0 — see [LICENSE](LICENSE).
