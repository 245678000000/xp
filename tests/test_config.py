from __future__ import annotations

import os
from pathlib import Path

from xp.config import load_config


def test_defaults(monkeypatch):
    monkeypatch.delenv("XP_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("XAI_API_KEY", raising=False)
    monkeypatch.delenv("XP_BASE_URL", raising=False)
    monkeypatch.delenv("OPENAI_BASE_URL", raising=False)
    monkeypatch.delenv("XP_MODEL", raising=False)
    monkeypatch.setenv("XP_CONFIG", str(Path("/nonexistent/xp-config.toml")))
    cfg = load_config()
    assert cfg.base_url.endswith("/v1") or "openai" in cfg.base_url
    assert cfg.sandbox is True


def test_env_api_key(monkeypatch, tmp_path: Path):
    monkeypatch.setenv("XP_CONFIG", str(tmp_path / "missing.toml"))
    monkeypatch.setenv("XP_API_KEY", "sk-test-123")
    monkeypatch.setenv("XP_MODEL", "my-model")
    monkeypatch.setenv("XP_BASE_URL", "https://example.com/v1")
    cfg = load_config()
    assert cfg.api_key == "sk-test-123"
    assert cfg.model == "my-model"
    assert cfg.base_url == "https://example.com/v1"


def test_xai_auto_base(monkeypatch, tmp_path: Path):
    monkeypatch.setenv("XP_CONFIG", str(tmp_path / "missing.toml"))
    monkeypatch.delenv("XP_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("XP_BASE_URL", raising=False)
    monkeypatch.delenv("OPENAI_BASE_URL", raising=False)
    monkeypatch.setenv("XAI_API_KEY", "xai-test")
    cfg = load_config()
    assert cfg.api_key == "xai-test"
    assert "x.ai" in cfg.base_url


def test_yolo_disables_sandbox(monkeypatch, tmp_path: Path):
    monkeypatch.setenv("XP_CONFIG", str(tmp_path / "missing.toml"))
    cfg = load_config(yolo=True)
    assert cfg.yolo is True
    assert cfg.sandbox is False
    assert cfg.confirm_risky is False
