"""
vera.config — Application settings.

Loads configuration from environment variables and .env file.
Uses pydantic-settings v2 BaseSettings for automatic env var binding.
Call get_settings() to obtain the singleton instance.
Call load_yaml(path) to load any YAML file as a plain dict.
"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    All application configuration.

    Fields are populated from (highest priority first):
      1. Explicit environment variables
      2. .env file  (if present in cwd)
      3. Pydantic default values below
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── Identity ──────────────────────────────────────────────────────────────
    app_name: str = Field("vera-engine", description="Application name")
    app_version: str = Field("3.0.0", description="Semantic version")
    team_name: str = Field("Team Vera", description="Challenge team name")
    contact_email: str = Field("", description="Contact email")
    env: str = Field("development", description="Runtime environment: development | production")

    # ── Server ────────────────────────────────────────────────────────────────
    host: str = Field("0.0.0.0", description="Bind host")
    port: int = Field(8080, description="Bind port", ge=1, le=65535)
    reload: bool = Field(False, description="Enable uvicorn hot-reload (dev only)")

    # ── Redis ─────────────────────────────────────────────────────────────────
    redis_url: str = Field("redis://localhost:6379/0", description="Redis connection URL")
    redis_fallback_to_memory: bool = Field(
        True, description="Fall back to in-memory store if Redis is unreachable"
    )
    redis_connect_timeout: int = Field(3, description="Redis connection timeout in seconds", ge=1)

    # ── LLM (future; judge_simulator.py uses this, Vera itself does not) ──────
    llm_provider: str = Field("anthropic", description="LLM provider name")
    llm_api_key: str = Field("", description="LLM API key — never logged")
    llm_model: str = Field("", description="LLM model identifier")

    # ── Logging ───────────────────────────────────────────────────────────────
    log_level: str = Field("INFO", description="Logging level: DEBUG | INFO | WARNING | ERROR")
    log_format: str = Field(
        "json", description="Log output format: json | console"
    )

    # ── Weights file ──────────────────────────────────────────────────────────
    weights_file: str = Field(
        "config/weights.yaml", description="Path to scoring weights YAML"
    )

    # ── Startup validation ────────────────────────────────────────────────────
    startup_validation_enabled: bool = Field(
        True, description="Run StartupValidator before accepting requests"
    )
    startup_validation_fail_fast: bool = Field(
        True, description="Exit with code 1 if any validation error is found"
    )

    # ── Composer limits ───────────────────────────────────────────────────────
    max_candidates_per_trigger: int = Field(
        5, description="Maximum candidates generated per trigger"
    )
    max_actions_per_tick: int = Field(
        20, description="Maximum ActionItems returned in one tick response"
    )
    max_actions_per_merchant_per_tick: int = Field(
        1, description="Maximum ActionItems per merchant per tick"
    )

    @field_validator("log_level")
    @classmethod
    def _validate_log_level(cls, v: str) -> str:
        allowed = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
        upper = v.upper()
        if upper not in allowed:
            raise ValueError(f"log_level must be one of {allowed}, got {v!r}")
        return upper

    @field_validator("log_format")
    @classmethod
    def _validate_log_format(cls, v: str) -> str:
        allowed = {"json", "console"}
        lower = v.lower()
        if lower not in allowed:
            raise ValueError(f"log_format must be one of {allowed}, got {v!r}")
        return lower

    @field_validator("env")
    @classmethod
    def _validate_env(cls, v: str) -> str:
        allowed = {"development", "production", "test"}
        lower = v.lower()
        if lower not in allowed:
            raise ValueError(f"env must be one of {allowed}, got {v!r}")
        return lower

    @property
    def is_production(self) -> bool:
        return self.env == "production"

    @property
    def is_development(self) -> bool:
        return self.env == "development"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return the application settings singleton. Cached after first call."""
    return Settings()


def load_yaml(path: str | Path) -> dict[str, Any]:
    """
    Load a YAML file and return its contents as a plain dict.

    Returns an empty dict if the file does not exist.
    Raises yaml.YAMLError on parse failure.
    """
    p = Path(path)
    if not p.exists():
        return {}
    with p.open(encoding="utf-8") as fh:
        return yaml.safe_load(fh) or {}
