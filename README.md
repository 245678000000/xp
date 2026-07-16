# xp

**中文** | [English](README.en.md)

**xp** 是一套可独立运行的编程 agent harness：tool loop、skills、全局规则，对接 **任何 OpenAI 兼容 API**。

- **可以不装 Grok** — 配置 API Key 即可  
- **也可以挂 Grok Build** — 同一套 skills / AGENTS.md 用 `install.sh` 装进 `~/.grok`

当前版本 **0.7**：可选 **审计日志**、工具结果截断、**PyPI 发布就绪**（`xp-harness`）、贡献与发版文档。

---

## 快速开始（独立运行）

### 1. 安装

Python **3.9+**。

```bash
# 从 Git 安装（推荐）
pip install "git+https://github.com/245678000000/xp.git"

# PyPI（配置 Trusted Publisher 并打 tag 发版后）
# pip install xp-harness

# 或克隆开发
git clone https://github.com/245678000000/xp.git
cd xp
python3 -m pip install -e ".[dev]"
# 或: pip install -r requirements.txt && export PYTHONPATH=$PWD/src
```

命令：`xp` 或 `python3 -m xp`。发版见 [docs/PUBLISH.md](docs/PUBLISH.md)。

### 2. 配置 API / 模型

```bash
xp init
export XP_API_KEY=sk-...    # 推荐用环境变量，不要把 key 提交到 git
# 编辑 ~/.config/xp/config.toml 里的 model / base_url
xp doctor                   # 含 API 探活（有 key 时）
```

```toml
# ~/.config/xp/config.toml
base_url = "https://api.openai.com/v1"
model = "gpt-4o"
# api_key = "sk-..."     # 不如用 XP_API_KEY
# stream = true
# sandbox = true         # 文件工具限制在 cwd 内
# confirm_risky = true   # rm / sudo / git push 前询问
# yolo = false
# max_retries = 4
# max_messages = 80
# skills_paths = ["~/my-skills"]
```

| 环境变量 | 含义 |
|----------|------|
| `XP_API_KEY` / `OPENAI_API_KEY` / `XAI_API_KEY` | API Key |
| `XP_BASE_URL` / `OPENAI_BASE_URL` | 接口（含 `/v1`） |
| `XP_MODEL` | 模型 id |
| `XP_CONFIG` | 配置文件路径 |
| `XP_YOLO=1` | 关闭沙箱 / 拦截 / 确认 |
| `XP_NO_STREAM=1` | 关闭流式 |
| `XP_ALLOW_OUTSIDE=1` | 允许写 cwd 外 |
| `XP_WEB=1` | 启用 web 工具 |
| `XP_AUDIT=1` | 本地工具审计日志 |
| `XP_API_BACKEND` | `chat_completions` 或 `messages` |
| `ANTHROPIC_API_KEY` | Anthropic（自动切 messages 后端） |
| `XP_SESSIONS_DIR` | 会话存储目录 |
| `XP_AUDIT_DIR` | 审计日志目录 |

仅设 `XAI_API_KEY` 时自动使用 `https://api.x.ai/v1`。

### 3. 使用

```bash
xp "这个仓库是干什么的？"
xp -p "列出入口文件"            # -p 传 prompt
xp chat
xp chat --continue              # 恢复最近会话
xp chat --session <id>
xp sessions                     # 列出会话

xp /commit
xp "帮我提交当前改动"           # 自动匹配 → /commit
xp /fix "测试失败 …"
xp run --skill ship "实现登录"
xp run --no-auto-skill "…"      # 关闭自动 skill
xp run --json "列出 3 个文件"    # 机器可读

xp -m gpt-4o --no-stream "…"
xp --web "查一下官方文档并总结"  # 启用 fetch_url / web_search
xp --yolo "…"                   # 危险模式
xp skills
```

**内置工具：**  
`bash` · `read_file` · `write_file` · `str_replace` · `apply_patch` · `list_dir` · `grep` · **`spawn_task`**  
可选 web：`fetch_url` · `web_search`（`--web` / `enable_web=true`）  

写文件时打印 **彩色 unified diff**。`spawn_task` 会在只读子上下文里调查后回传摘要。

**安全默认：**

- 文件读写限制在当前工作目录（`--allow-outside` / `yolo` 解除）
- 硬拦截：`rm -rf /`、`git reset --hard`、curl\|sh 等
- 风险命令（`rm`、`sudo`、`git push`…）会询问确认（非 yolo）

---

## 可选：挂到 Grok Build

```bash
./install.sh          # 或 ./install.sh --link
```

| 模式 | 入口 | 需要 |
|------|------|------|
| 独立 runtime | `xp …` | Python + API Key |
| Grok 定制层 | `grok` + `/commit` | [Grok Build](https://x.ai/cli) |

---

## Skills

| 命令 | 用途 |
|------|------|
| `/commit` | conventional commits（不 push） |
| `/pr` | 创建/更新 GitHub PR |
| `/fix` | 复现 → 定位 → 修复 → 验证 |
| `/ship` | 实现 → 验证 → 提交 |
| `/review` | 代码审查 |
| `/test` | 补测试 |
| `/refactor` | 行为不变的重构 |
| `/release` | 发版准备（changelog / 版本） |

chat 里可直接输入 `/commit`、`/skills`。自然语言也会 **自动匹配** skill。

### Anthropic（支持 SSE 流式）

```toml
api_backend = "messages"
base_url = "https://api.anthropic.com"
model = "claude-sonnet-4-20250514"
stream = true
```

```bash
export ANTHROPIC_API_KEY=sk-ant-...
xp -m claude-sonnet-4-20250514 --api-backend messages "…"
```

### MCP（stdio）

在 `~/.config/xp/config.toml`：

```toml
enable_mcp = true

[[mcp_servers]]
name = "filesystem"
command = "npx"
args = ["-y", "@modelcontextprotocol/server-filesystem", "."]
```

工具名形式：`mcp__filesystem__…`。示例见 `examples/config.mcp.toml`。

```bash
xp config          # 查看生效配置
xp config --json
```

---

## 开发

```bash
bash scripts/sync_data.sh   # 同步 skills → src/xp/data
pytest -q
python -m xp doctor
```

CI：`.github/workflows/ci.yml`（Python 3.9 / 3.11 / 3.12）。

---

## 与 Grok 的差距（有意保持轻量）

无完整 TUI、MCP、子 agent、OS 级沙箱。需要那些能力请用 Grok Build；xp 负责 **可移植 skills + 最小可运行 runtime**。

---

## 许可

Apache-2.0 — 见 [LICENSE](LICENSE)。
