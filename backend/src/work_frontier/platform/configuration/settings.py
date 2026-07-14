"""Typed runtime settings for the setup composition root."""

from __future__ import annotations

from pathlib import Path  # noqa: TC003 - Pydantic resolves settings types at runtime
from typing import ClassVar

from pydantic import AnyHttpUrl, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class SetupRuntimeSettings(BaseSettings):
    """Environment-injected bootstrap settings with safe defaults."""

    model_config: ClassVar[SettingsConfigDict] = SettingsConfigDict(
        env_prefix="WF_SETUP_",
        extra="ignore",
        case_sensitive=False,
    )

    state_root: Path | None = None
    github_api_url: AnyHttpUrl = AnyHttpUrl("https://api.github.com/")
    github_timeout_seconds: float = Field(default=15.0, gt=0, le=120)
