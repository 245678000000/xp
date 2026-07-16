"""Load runtime config from env + optional TOML."""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List

if sys.version_info >= (3, 11):
    import tomllib
else:
    try:
        import tomli as tomllib  # type: ignore
    except ImportError as e:  # pragma: no cover
        raise SystemExit(
            "Python < 3.11 needs the 'tomli' package. Try: pip install tomli"
        ) from e

from xp.paths import user_config_path


@dataclass
class RuntimeConfig:
    api_key: str = ""
    base_url: str = "https://api.openai.com/v1"
    model: str = "gpt-4o-mini"
    max_turns: int = 40
    temperature: float = 0.2
    timeout: float = 120.0
    cwd: Path = field(default_factory=Path.cwd)
    # When True: skip blocklist + path sandbox + confirm prompts
    yolo: bool = False
    # Restrict file tools to cwd tree
    sandbox: bool = True
    # Ask before risky bash (rm, push, sudo, ...)
    confirm_risky: bool = True
    # Stream assistant tokens
    stream: bool = True
    # Keep last N non-system messages after compaction (approx)
    max_messages: int = 80
    max_retries: int = 4
    system_extra: str = ""
    skills_paths: List[str] = field(default_factory=list)
    allow_outside: bool = False
    # Auto-attach best matching skill from user message
    auto_skill: bool = True
    # Optional web tools (fetch_url, web_search)
    enable_web: bool = False
    # spawn_task sub-investigation
    enable_spawn: bool = True
    # chat_completions (OpenAI) | messages (Anthropic)
    api_backend: str = "chat_completions"
    # MCP server specs (parsed from config.toml)
    mcp_servers: List[Dict[str, Any]] = field(default_factory=list)
    enable_mcp: bool = True
    # Local-only tool audit log (never uploaded)
    enable_audit: bool = False
    # Truncate huge tool results before sending back to the model
    max_tool_result_chars: int = 60_000
    # Opt-in telemetry (default OFF). Local JSONL; optional webhook endpoint.
    enable_telemetry: bool = False
    telemetry_endpoint: str = ""
    # Prefer prompt_toolkit TUI for chat when available
    enable_tui: bool = False

    def require_api_key(self) -> None:
        if not self.api_key:
            raise SystemExit(
                "No API key found.\n\n"
                "Set one of:\n"
                "  export XP_API_KEY=...          # preferred\n"
                "  export OPENAI_API_KEY=...\n"
                "  export XAI_API_KEY=...         # for api.x.ai\n"
                "  export ANTHROPIC_API_KEY=...  # with api_backend=messages\n"
                "Or write api_key in ~/.config/xp/config.toml\n\n"
                "  xp init\n"
            )


def _first_env(*names: str) -> str:
    for name in names:
        val = os.environ.get(name, "").strip()
        if val:
            return val
    return ""


def _truthy(val: str) -> bool:
    return val.lower() in ("1", "true", "yes", "on")


def load_config(
    *,
    model: str | None = None,
    base_url: str | None = None,
    api_key: str | None = None,
    max_turns: int | None = None,
    yolo: bool | None = None,
    cwd: Path | None = None,
    stream: bool | None = None,
    allow_outside: bool | None = None,
    sandbox: bool | None = None,
    auto_skill: bool | None = None,
    enable_web: bool | None = None,
    enable_spawn: bool | None = None,
    api_backend: str | None = None,
) -> RuntimeConfig:
    cfg = RuntimeConfig(cwd=(cwd or Path.cwd()).resolve())

    path = user_config_path()
    file_data: Dict[str, Any] = {}
    if path.is_file():
        file_data = tomllib.loads(path.read_text(encoding="utf-8"))
        data = file_data
        cfg.api_key = str(data.get("api_key") or data.get("apiKey") or "")
        cfg.base_url = str(data.get("base_url") or data.get("baseUrl") or cfg.base_url)
        cfg.model = str(data.get("model") or cfg.model)
        for key, cast in (
            ("max_turns", int),
            ("temperature", float),
            ("timeout", float),
            ("max_messages", int),
            ("max_retries", int),
            ("max_tool_result_chars", int),
        ):
            if key in data:
                setattr(cfg, key, cast(data[key]))
        for key in (
            "yolo",
            "sandbox",
            "confirm_risky",
            "stream",
            "allow_outside",
            "auto_skill",
            "enable_web",
            "enable_spawn",
            "enable_mcp",
            "enable_audit",
            "enable_telemetry",
            "enable_tui",
        ):
            if key in data:
                setattr(cfg, key, bool(data[key]))
        if "system_extra" in data:
            cfg.system_extra = str(data["system_extra"])
        if "skills_paths" in data and isinstance(data["skills_paths"], list):
            cfg.skills_paths = [str(x) for x in data["skills_paths"]]
        if "api_backend" in data:
            cfg.api_backend = str(data["api_backend"])
        if "telemetry_endpoint" in data:
            cfg.telemetry_endpoint = str(data["telemetry_endpoint"])
        # Preserve raw mcp block for McpRegistry
        if "mcp_servers" in data:
            # normalize to list of dicts for RuntimeConfig
            from xp.mcp_client import parse_mcp_config

            specs = parse_mcp_config(data)
            cfg.mcp_servers = [
                {
                    "name": s.name,
                    "command": s.command,
                    "args": s.args,
                    "env": s.env,
                }
                for s in specs
            ]

    env_key = _first_env(
        "XP_API_KEY", "OPENAI_API_KEY", "XAI_API_KEY", "ANTHROPIC_API_KEY"
    )
    if env_key:
        cfg.api_key = env_key
    if env_url := _first_env("XP_BASE_URL", "OPENAI_BASE_URL"):
        cfg.base_url = env_url
    if env_model := _first_env("XP_MODEL", "OPENAI_MODEL"):
        cfg.model = env_model
    if env_backend := _first_env("XP_API_BACKEND"):
        cfg.api_backend = env_backend
    if os.environ.get("XP_YOLO") and _truthy(os.environ["XP_YOLO"]):
        cfg.yolo = True
    if os.environ.get("XP_NO_STREAM") and _truthy(os.environ["XP_NO_STREAM"]):
        cfg.stream = False
    if os.environ.get("XP_ALLOW_OUTSIDE") and _truthy(os.environ["XP_ALLOW_OUTSIDE"]):
        cfg.allow_outside = True
        cfg.sandbox = False
    if os.environ.get("XP_WEB") and _truthy(os.environ["XP_WEB"]):
        cfg.enable_web = True
    if os.environ.get("XP_AUDIT") and _truthy(os.environ["XP_AUDIT"]):
        cfg.enable_audit = True
    if os.environ.get("XP_TELEMETRY") and _truthy(os.environ["XP_TELEMETRY"]):
        cfg.enable_telemetry = True
    if env_te := _first_env("XP_TELEMETRY_ENDPOINT"):
        cfg.telemetry_endpoint = env_te
    if os.environ.get("XP_TUI") and _truthy(os.environ["XP_TUI"]):
        cfg.enable_tui = True

    # Only XAI_API_KEY → default to xAI endpoint
    if (
        not _first_env("XP_BASE_URL", "OPENAI_BASE_URL")
        and cfg.base_url.rstrip("/") == "https://api.openai.com/v1"
        and os.environ.get("XAI_API_KEY")
        and not os.environ.get("OPENAI_API_KEY")
        and not os.environ.get("XP_API_KEY")
        and not os.environ.get("ANTHROPIC_API_KEY")
    ):
        cfg.base_url = "https://api.x.ai/v1"
        if cfg.model == "gpt-4o-mini":
            cfg.model = "grok-3-mini"

    # Only ANTHROPIC_API_KEY → Anthropic messages
    if (
        not _first_env("XP_BASE_URL", "OPENAI_BASE_URL")
        and os.environ.get("ANTHROPIC_API_KEY")
        and not os.environ.get("OPENAI_API_KEY")
        and not os.environ.get("XP_API_KEY")
        and not os.environ.get("XAI_API_KEY")
        and cfg.api_backend == "chat_completions"
        and cfg.base_url.rstrip("/") == "https://api.openai.com/v1"
    ):
        cfg.api_backend = "messages"
        cfg.base_url = "https://api.anthropic.com"
        if cfg.model in ("gpt-4o-mini", "gpt-4o"):
            cfg.model = "claude-sonnet-4-20250514"

    if api_key:
        cfg.api_key = api_key
    if base_url:
        cfg.base_url = base_url
    if model:
        cfg.model = model
    if max_turns is not None:
        cfg.max_turns = max_turns
    if yolo is not None:
        cfg.yolo = yolo
    if stream is not None:
        cfg.stream = stream
    if allow_outside is not None:
        cfg.allow_outside = allow_outside
        if allow_outside:
            cfg.sandbox = False
    if sandbox is not None:
        cfg.sandbox = sandbox
    if auto_skill is not None:
        cfg.auto_skill = auto_skill
    if enable_web is not None:
        cfg.enable_web = enable_web
    if enable_spawn is not None:
        cfg.enable_spawn = enable_spawn
    if api_backend is not None:
        cfg.api_backend = api_backend

    if cfg.yolo:
        cfg.confirm_risky = False
        cfg.sandbox = False

    cfg.base_url = cfg.base_url.rstrip("/")
    cfg.api_backend = (cfg.api_backend or "chat_completions").lower()
    return cfg
