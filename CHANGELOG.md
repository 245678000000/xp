# Changelog

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
