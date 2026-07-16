# xp

**中文** | [English](README.en.md)

**xp** 是面向 [Grok Build](https://github.com/xai-org/grok-build) 的个人编程 harness 定制层：skills、agents、personas 与全局规则，用来让日常写代码更稳定、一致。

它**不会** fork Grok 的 Rust TUI / 运行时，而是挂在官方扩展点上：

| Grok Build | xp |
|------------|-----|
| 全局规则 | `AGENTS.md` |
| Skills | `skills/*` |
| Agents | `agents/*` |
| Personas | `personas/*` |
| Roles | `roles/*` |

灵感来自 [xai-org/grok-build](https://github.com/xai-org/grok-build)。

## 安装

需要已安装 [Grok Build](https://x.ai/cli)（`grok` 命令）。

```bash
git clone https://github.com/245678000000/xp.git
cd xp
./install.sh          # 复制到 ~/.grok
# 或
./install.sh --link   # 用符号链接（改本仓库即生效）
```

然后**新开一个** Grok 会话。技能会出现在 `/` 命令列表里。

### 手动安装

```bash
# 只挂 skills 路径时，可在 ~/.grok/config.toml 写：
# [skills]
# paths = ["~/xp/skills"]
```

或自行拷贝到 `~/.grok/`：

```text
~/.grok/AGENTS.md
~/.grok/agents/
~/.grok/skills/
~/.grok/personas/
~/.grok/roles/
```

## 包含内容

### Skills（斜杠命令）

| 命令 | 用途 |
|------|------|
| `/commit` | 按 conventional commits 提交当前改动（不 push） |
| `/pr` | 推送分支并创建 / 更新 GitHub PR |
| `/fix` | 复现 → 定位 → 修复 → 验证 |
| `/ship` | 实现 → 验证 → 提交（全流程） |

### Agents

| Agent | 用途 |
|-------|------|
| `ship` | 端到端交付：实现并验证 |
| `debug` | 根因调试 |

在 TUI 里用 `/config-agents`（或 `/agents`）切换。

### Personas

| Persona | 风格 |
|---------|------|
| `concise` | 短、密、少废话 |
| `thorough` | 深挖、引用路径、证据优先 |

### 全局规则

`AGENTS.md` 为所有项目设定默认习惯：先理解再改、最小改动、要验证、Git 安全、不碰密钥。

具体仓库里的 `AGENTS.md` / `.grok/rules/` 冲突时优先。

## 目录结构

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
├── README.md          # 中文（本文件）
└── README.en.md       # English
```

## 设计原则

1. **不重写 harness 运行时** — 复用 Grok Build 的 tool loop、权限、会话、MCP。
2. **流程写进 skill，默认习惯写进 AGENTS.md。**
3. **默认安全** — 不擅自 force-push、不用 `--no-verify`、不提交密钥。
4. **可演进** — 新工作流 = 新的 `skills/<name>/SKILL.md`。

## 如何验证已加载

安装后新开 `grok` 会话：

1. 输入 `/` → 应看到 `commit` / `pr` / `fix` / `ship`
2. `/config-agents` → 应看到 `ship` / `debug`
3. `/personas` → 应看到 `concise` / `thorough`
4. 可选：`grok inspect`

## 如何扩展

```bash
mkdir -p skills/my-flow
# 编写 SKILL.md：YAML frontmatter（name、description）+ 步骤说明
./install.sh   # 再同步到 ~/.grok
```

`description` 要写清触发场景，模型才会在合适的时候自动选用。

## 许可

Apache-2.0 — 见 [LICENSE](LICENSE)。
