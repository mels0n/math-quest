"""Boot-validated settings. The only module that reads environment variables or secret files."""

from functools import lru_cache
from pathlib import Path
from typing import Self

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


def default_content_dir() -> Path:
    """The `content/` directory next to `src/` in the backend project."""
    return Path(__file__).resolve().parents[3] / "content"


def _read_secret_file(path: Path, what: str) -> str:
    """Read a one-line secret file; strips a BOM and surrounding whitespace.

    Failures never echo the file or the underlying exception text.
    """
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeError):
        raise ValueError(f"{what} file could not be read") from None
    value = text.lstrip("﻿").strip()
    if not value:
        raise ValueError(f"{what} file is empty")
    return value


class Settings(BaseSettings):
    model_config = SettingsConfigDict(extra="ignore", hide_input_in_errors=True)

    database_url: str | None = None
    database_url_file: Path | None = None
    content_dir: Path = default_content_dir()
    static_dir: Path | None = None
    cookie_secure: bool = True
    initial_signup_word_file: Path | None = None
    dev_expose_answers: bool = False

    # Resolved at boot from the *_file settings; never set directly.
    initial_signup_word: str | None = None

    @model_validator(mode="after")
    def _resolve_secret_files(self) -> Self:
        if self.database_url is None:
            if self.database_url_file is None:
                raise ValueError("DATABASE_URL or DATABASE_URL_FILE is required")
            self.database_url = _read_secret_file(self.database_url_file, "database url")
        if self.initial_signup_word_file is not None and self.initial_signup_word is None:
            self.initial_signup_word = _read_secret_file(
                self.initial_signup_word_file, "initial signup word"
            )
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
