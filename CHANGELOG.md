# Changelog

## 0.7.0

- Optional **local audit log** for tool calls (`enable_audit` / `XP_AUDIT=1`)
- Truncate oversized tool results before model context (`max_tool_result_chars`)
- PyPI packaging polish: dynamic version from `__init__.py`, Trusted Publisher workflow
- `docs/PUBLISH.md` + `CONTRIBUTING.md`
- Doctor shows update install lines and MCP/audit flags

## 0.6.0

- Anthropic Messages **SSE streaming** (text + tool_use)
- Optional **MCP stdio** bridge (`[[mcp_servers]]` in config)
- `xp config` shows effective runtime settings
- `examples/` sample configs (OpenAI / Anthropic / MCP)
- GitHub Actions release workflow on `v*` tags

## 0.5.0

- Optional web tools: `fetch_url`, `web_search` (`enable_web` / `--web` / `XP_WEB=1`)
- `spawn_task` read-only sub-investigation (fresh context, summary back)
- Anthropic Messages backend (`api_backend = "messages"`, `ANTHROPIC_API_KEY`)
- New skills: `/review`, `/test`, `/refactor`, `/release`
- Dual-mode docs: standalone vs Grok layer

## 0.4.0

- `apply_patch` tool (freeform *** Patch and unified diffs)
- Colored unified-diff previews on write / str_replace / apply_patch
- Auto skill matching from natural language (`auto_skill`, `--no-auto-skill`)
- `-p` / `--prompt-text` for run prompts
- Chat per-message auto skill attach

## 0.3.0

- Streaming assistant output (`stream`, `--no-stream`)
- Session persistence: `xp chat --continue`, `xp sessions`
- Path sandbox for file tools; `--allow-outside` / `yolo` to disable
- Risky bash confirmation (`rm`, `sudo`, `git push`, …)
- API retries with backoff; token usage reporting
- Context compaction via `max_messages`
- `xp run --json` machine output
- `xp doctor` API probe when key is set
- Extra `skills_paths` in config
- pytest suite + GitHub Actions CI
- Data sync check (`scripts/sync_data.sh`)

## 0.2.0

- Standalone Python runtime (no Grok required)
- OpenAI-compatible tool loop
- Skills: commit / pr / fix / ship
- Optional Grok `install.sh` layer
