# xp

**中文** | [English](README.en.md)

**xp** 是一套可独立运行的编程 agent harness：内置 tool loop、skills、全局规则，对接 **任何 OpenAI 兼容 API**。

- **可以不装 Grok** — `pip install` 后配置 API Key 即可用  
- **也可以继续挂 Grok Build** — 同一套 skills / AGENTS.md 仍可用 `install.sh` 装进 `~/.grok`

灵感与扩展点对齐 [xai-org/grok-build](https://github.com/xai-org/grok-build)，但运行时是自包含的 Python CLI。

---

## 快速开始（独立运行，不依赖 Grok）

### 1. 安装

需要 **Python 3.9+**。

```bash
git clone https://github.com/245678000000/xp.git
cd xp

# 方式 A：开发安装（推荐）
python3 -m pip install -e .

# 方式 B：仅依赖 + PYTHONPATH
python3 -m pip install -r requirements.txt
export PYTHONPATH="$PWD/src${PYTHONPATH:+:$PYTHONPATH}"
```

安装成功后应有 `xp` 命令（若提示找不到，用 `python3 -m xp`）。

### 2. 配置 API 与模型

```bash
xp init
# 编辑 ~/.config/xp/config.toml
```

示例 `~/.config/xp/config.toml`：

```toml
# OpenAI
api_key = "sk-..."
base_url = "https://api.openai.com/v1"
model = "gpt-4o"

# 或 xAI
# api_key = "xai-..."
# base_url = "https://api.x.ai/v1"
# model = "grok-3-mini"

# 或任意 OpenAI 兼容代理
# base_url = "https://your-proxy.example/v1"
# model = "your-model-id"
```

也可用环境变量（优先于配置文件）：

| 变量 | 含义 |
|------|------|
| `XP_API_KEY` / `OPENAI_API_KEY` / `XAI_API_KEY` | API Key |
| `XP_BASE_URL` / `OPENAI_BASE_URL` | 接口地址（需含 `/v1`） |
| `XP_MODEL` / `OPENAI_MODEL` | 模型 id |
| `XP_CONFIG` | 自定义配置文件路径 |
| `XP_YOLO=1` | 关闭 bash 危险命令拦截 |

仅设置 `XAI_API_KEY` 时，会自动把 `base_url` 指到 `https://api.x.ai/v1`。

检查配置：

```bash
xp doctor
```

### 3. 使用

```bash
# 一次性任务
xp "解释当前目录是什么项目，并列出主要入口文件"

# 交互对话
xp chat

# 强制使用 skill
xp /commit
xp /fix 测试失败：AssertionError in test_foo
xp run --skill ship "实现用户登录 API"

# 指定模型 / 端点
xp -m gpt-4o --base-url https://api.openai.com/v1 "写一个 hello world"

# 查看 skills
xp skills
```

内置工具：`bash`、`read_file`、`write_file`、`str_replace`、`list_dir`、`grep`。

---

## 可选：挂到 Grok Build

若你本机有 [Grok Build](https://x.ai/cli)，同一仓库仍可当 Grok 定制层：

```bash
./install.sh          # 复制到 ~/.grok
# 或
./install.sh --link   # 符号链接
```

| 模式 | 命令 | 需要 |
|------|------|------|
| **独立 runtime** | `xp "..."` | Python + API Key |
| **Grok 定制层** | `grok` + `/commit` 等 | Grok Build |

---

## 仓库结构

```text
xp/
├── AGENTS.md              # 全局规则
├── skills/                # /commit /pr /fix /ship
├── agents/                # ship / debug 配置
├── personas/ roles/       # Grok 侧 personas/roles
├── src/xp/                # ★ 独立 Python runtime
│   ├── cli.py
│   ├── agent.py           # tool loop
│   ├── tools.py
│   ├── config.py
│   └── skills.py
├── install.sh             # 安装到 ~/.grok
├── pyproject.toml
└── requirements.txt
```

---

## Skills

| 命令 | 用途 |
|------|------|
| `/commit` | conventional commits 提交（不 push） |
| `/pr` | 创建 / 更新 GitHub PR |
| `/fix` | 复现 → 定位 → 修复 → 验证 |
| `/ship` | 实现 → 验证 → 提交 |

```bash
xp skills
xp /fix "……"
```

---

## 设计原则

1. **规则与流程可移植** — AGENTS.md / skills 纯 Markdown，Grok 与 xp runtime 共用。  
2. **运行时最小可用** — OpenAI 兼容 Chat Completions + function calling。  
3. **默认安全** — bash 拦截部分破坏性命令；`--yolo` 可关闭。  
4. **密钥不进仓库** — 只用本地 config / 环境变量。

---

## 常见问题

**Q: 和 Grok 功能一样吗？**  
A: 独立 runtime 是精简版（工具更少、无 TUI/MCP/子 agent）。skills 与规则一致；复杂场景仍可用 Grok。

**Q: 支持 Claude / 本地 Ollama 吗？**  
A: 只要提供 **OpenAI 兼容** 的 `/v1/chat/completions` + tools 即可。Claude 官方 Messages API 需兼容层/代理。

**Q: `xp` 命令找不到？**  
A: `python3 -m pip install -e .` 后把 pip 的 script 目录加入 PATH，或始终用 `python3 -m xp`。

---

## 许可

Apache-2.0 — 见 [LICENSE](LICENSE)。
