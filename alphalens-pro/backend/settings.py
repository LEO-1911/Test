"""Zentrale Konfiguration: .env (Secrets) + config/*.yaml (alles Fachliche)."""

from __future__ import annotations

from functools import cache
from pathlib import Path
from typing import Any

import yaml
from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parent.parent
CONFIG_DIR = PROJECT_ROOT / "config"
DATA_DIR = PROJECT_ROOT / "data"


class Secrets(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=PROJECT_ROOT / ".env", env_file_encoding="utf-8", extra="ignore"
    )

    anthropic_api_key: str = ""
    finnhub_api_key: str = ""
    alphavantage_api_key: str = ""


@cache
def secrets() -> Secrets:
    return Secrets()


@cache
def load_config(name: str) -> dict[str, Any]:
    """Lädt config/<name>.yaml. Fehlende Datei ist ein Programmierfehler, kein Laufzeitfall."""
    path = CONFIG_DIR / f"{name}.yaml"
    with path.open(encoding="utf-8") as fh:
        data = yaml.safe_load(fh)
    if not isinstance(data, dict):
        raise ValueError(f"Config {path} muss ein Mapping sein")
    return data


def db_path() -> Path:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    return DATA_DIR / "alphalens.db"
