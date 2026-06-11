"""Load and validate project configuration."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml
from pydantic import ValidationError

from src.config.exceptions import ConfigurationError
from src.config.settings import AppSettings


DEFAULT_CONFIG_PATH = Path("config.yaml")


def load_config(path: str | Path = DEFAULT_CONFIG_PATH) -> AppSettings:
    """Load root ``config.yaml`` and return typed settings."""
    config_path = Path(path)
    if not config_path.exists():
        raise ConfigurationError(f"Configuration file not found: {config_path}")

    with config_path.open("r", encoding="utf-8") as file_obj:
        raw = yaml.safe_load(file_obj) or {}

    try:
        return AppSettings.model_validate(raw)
    except ValidationError as exc:
        raise ConfigurationError(str(exc)) from exc


def get_exchange_credentials(settings: AppSettings) -> tuple[str | None, str | None]:
    """Resolve exchange credentials from environment variables."""
    return (
        os.getenv(settings.exchange.api_key_env),
        os.getenv(settings.exchange.api_secret_env),
    )


def dump_config_snapshot(settings: AppSettings) -> dict[str, Any]:
    """Return a JSON-serializable snapshot of settings for run artifacts."""
    return settings.model_dump(mode="json")
