"""Настройки сервиса ingest (pydantic-settings).

Значения читаются из переменных окружения и (при наличии) из `.env`.
"""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

# Разделы-префиксы: берём страницу, если путь начинается с одного из них.
DEFAULT_INCLUDE_PREFIXES: list[str] = [
    "/tutorial/",
    "/advanced/",
    "/reference/",
    "/deployment/",
    "/how-to/",
    # ниже — одиночные top-level страницы (точное совпадение пути)
    "/features/",
    "/learn/",
    "/python-types/",
    "/async/",
    "/fastapi-cli/",
    "/editor-support/",
    "/project-generation/",
]


class Settings(BaseSettings):
    """Конфигурация запуска crawl."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    docs_base_url: str = "https://fastapi.tiangolo.com"
    data_dir: Path = Path("data")
    concurrency: int = 8
    request_timeout: float = 30.0
    user_agent: str = "rag-learning-bot/0.1"
    include_prefixes: Annotated[list[str], NoDecode] = Field(
        default_factory=lambda: list(DEFAULT_INCLUDE_PREFIXES)
    )

    @field_validator("include_prefixes", mode="before")
    @classmethod
    def _split_prefixes(cls, value: object) -> object:
        """INCLUDE_PREFIXES задаётся строкой через запятую."""
        if value is None or value == "":
            return list(DEFAULT_INCLUDE_PREFIXES)
        if isinstance(value, str):
            return [part.strip() for part in value.split(",") if part.strip()]
        return value

    def is_included(self, url_path: str) -> bool:
        """Входит ли путь в allowlist разделов."""
        return any(url_path.startswith(prefix) for prefix in self.include_prefixes)
