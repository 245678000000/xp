# xp examples

## Config samples

| File | Use |
|------|-----|
| `config.openai.toml` | OpenAI Chat Completions |
| `config.anthropic.toml` | Anthropic Messages (+ SSE stream) |
| `config.mcp.toml` | MCP stdio server example |

```bash
mkdir -p ~/.config/xp
cp examples/config.openai.toml ~/.config/xp/config.toml
export XP_API_KEY=sk-...
xp doctor
xp "list files in this repo"
```

## Quick flows

```bash
# Auto skill
xp "帮我提交当前改动"

# Web
xp --web "fetch https://example.com and summarize"

# Review current diff
xp /review

# Resume chat
xp chat --continue
```

## MCP

Tools appear as `mcp__<server>__<tool>`. See `config.mcp.toml`.
