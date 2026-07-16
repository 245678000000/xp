# Privacy

xp is designed to run **locally** with your API keys and files.

## Default (safe)

With no special flags:

- No telemetry is collected or sent.
- No analytics network calls.
- Sessions stay under `~/.local/share/xp/sessions/` on your machine.
- Skills and rules are local Markdown.

## Opt-in audit (`enable_audit` / `XP_AUDIT=1`)

- Writes tool call **arguments and results** to local JSONL under  
  `~/.local/share/xp/audit/`.
- **Never uploaded** by xp.
- Use when debugging agent behavior; disable for sensitive workspaces.

## Opt-in telemetry (`enable_telemetry` / `XP_TELEMETRY=1`)

**Default: OFF.**

When enabled:

| Logged | Not logged |
|--------|------------|
| Event type (`session_start`, `tool`, `turn`, …) | User prompts |
| Tool **name** only (`bash`, `read_file`, `mcp`, …) | Tool arguments / outputs |
| Model id, backend, xp version | API keys |
| Anonymized `cwd_hash` (SHA-256 prefix) | Real filesystem paths |
| Token **counts** if available | File contents |

Local files: `~/.local/share/xp/telemetry/`.

Optional `telemetry_endpoint`: if set to an `http(s)` URL, the same **anonymous**
JSON events may be POSTed. xp never attaches prompts or secrets.

```bash
xp telemetry status
xp telemetry clear
xp telemetry path
```

## Network

Only when you use:

- Your configured LLM `base_url`
- Optional web tools (`--web`)
- Optional MCP servers you configure
- Optional telemetry webhook you configure

## Grok mode

`./install.sh` only copies skills/rules into `~/.grok`.  
Grok Build’s own privacy/network policy applies to that product separately.
