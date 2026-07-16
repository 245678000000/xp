"""Load runtime config from env + optional TOML."""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass, field
from pathlib import Path

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
    # When False, refuse a small set of clearly destructive bash patterns
    yolo: bool = False
    # Extra system text
    system_extra: str = ""

    def require_api_key(self) -> None:
        if not self.api_key:
            raise SystemExit(
                "No API key found.\n\n"
                "Set one of:\n"
                "  export XP_API_KEY=...          # preferred\n"
                "  export OPENAI_API_KEY=...\n"
                "  export XAI_API_KEY=...         # for api.x.ai\n"
                "Or write api_key in ~/.config/xp/config.toml\n\n"
                "Example config:\n"
                "  mkdir -p ~/.config/xp\n"
                "  cat > ~/.config/xp/config.toml <<'EOF'\n"
                "  api_key = \"sk-...\"\n"
                "  base_url = \"https://api.openai.com/v1\"\n"
                "  model = \"gpt-4o\"\n"
                "  EOF\n"
            )


def _first_env(*names: str) -> str:
    for name in names:
        val = os.environ.get(name, "").strip()
        if val:
            return val
    return ""


def load_config(
    *,
    model: str | None = None,
    base_url: str | None = None,
    api_key: str | None = None,
    max_turns: int | None = None,
    yolo: bool | None = None,
    cwd: Path | None = None,
) -> RuntimeConfig:
    cfg = RuntimeConfig(cwd=(cwd or Path.cwd()).resolve())

    path = user_config_path()
    if path.is_file():
        data = tomllib.loads(path.read_text(encoding="utf-8"))
        cfg.api_key = str(data.get("api_key") or data.get("apiKey") or "")
        cfg.base_url = str(data.get("base_url") or data.get("baseUrl") or cfg.base_url)
        cfg.model = str(data.get("model") or cfg.model)
        if "max_turns" in data:
            cfg.max_turns = int(data["max_turns"])
        if "temperature" in data:
            cfg.temperature = float(data["temperature"])
        if "timeout" in data:
            cfg.timeout = float(data["timeout"])
        if "yolo" in data:
            cfg.yolo = bool(data["yolo"])
        if "system_extra" in data:
            cfg.system_extra = str(data["system_extra"])

    # Env overrides file
    env_key = _first_env("XP_API_KEY", "OPENAI_API_KEY", "XAI_API_KEY")
    if env_key:
        cfg.api_key = env_key
    if env_url := _first_env("XP_BASE_URL", "OPENAI_BASE_URL"):
        cfg.base_url = env_url
    if env_model := _first_env("XP_MODEL", "OPENAI_MODEL"):
        cfg.model = env_model
    if os.environ.get("XP_YOLO", "").lower() in ("1", "true", "yes"):
        cfg.yolo = True

    # If only XAI_API_KEY is set and base_url still default OpenAI, point at xAI
    if (
        not _first_env("XP_BASE_URL", "OPENAI_BASE_URL")
        and cfg.base_url.rstrip("/") == "https://api.openai.com/v1"
        and os.environ.get("XAI_API_KEY")
        and not os.environ.get("OPENAI_API_KEY")
        and not os.environ.get("XP_API_KEY")
    ):
        cfg.base_url = "https://api.x.ai/v1"
        if cfg.model == "gpt-4o-mini":
            cfg.model = "grok-3-mini"

    # CLI flags win
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

    cfg.base_url = cfg.base_url.rstrip("/")
    return cfg
