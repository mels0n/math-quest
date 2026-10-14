"""Boot-validated settings. The only module that reads environment variables or secret files."""

import ipaddress
from functools import lru_cache
from pathlib import Path
from typing import Annotated, Self

from pydantic import PrivateAttr, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

ADMIN_PASSWORD_MIN_LENGTH = 16


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
    value = text.lstrip("\ufeff").strip()
    if not value:
        raise ValueError(f"{what} file is empty")
    return value


class Settings(BaseSettings):
    model_config = SettingsConfigDict(extra="ignore", hide_input_in_errors=True)

    database_url: SecretStr | None = None
    database_url_file: Path | None = None
    content_dir: Path = default_content_dir()
    static_dir: Path | None = None
    cookie_secure: bool = True
    initial_signup_word_file: Path | None = None
    dev_expose_answers: bool = False
    # IPs or CIDRs of reverse proxies whose X-Forwarded-For is believed; comma-separated in env.
    trusted_proxies: Annotated[list[str], NoDecode] = []
    admin_password_file: Path | None = None
    # Clients outside these IPs or CIDRs get 404 on every /api/admin route; comma-separated in env.
    admin_allowed_cidrs: Annotated[list[str], NoDecode] = [
        "192.168.0.0/16",
        "127.0.0.1/32",
        "::1/128",
    ]

    # Read only from `initial_signup_word_file`; deliberately not an env-settable field.
    _initial_signup_word: SecretStr | None = PrivateAttr(default=None)

    @property
    def initial_signup_word(self) -> SecretStr | None:
        return self._initial_signup_word

    def read_admin_password(self) -> SecretStr | None:
        """The admin password, read from its file on each call and never stored on the settings."""
        if self.admin_password_file is None:
            return None
        value = _read_secret_file(self.admin_password_file, "admin password")
        if len(value) < ADMIN_PASSWORD_MIN_LENGTH:
            raise ValueError(
                f"admin password must be at least {ADMIN_PASSWORD_MIN_LENGTH} characters"
            )
        return SecretStr(value)

    @field_validator("trusted_proxies", "admin_allowed_cidrs", mode="before")
    @classmethod
    def _split_networks(cls, value: object) -> object:
        if isinstance(value, str):
            return [part.strip() for part in value.split(",") if part.strip()]
        return value

    @field_validator("trusted_proxies", "admin_allowed_cidrs")
    @classmethod
    def _check_networks(cls, value: list[str]) -> list[str]:
        for entry in value:
            try:
                ipaddress.ip_network(entry, strict=False)
            except ValueError:
                raise ValueError("network list holds an invalid IP or CIDR") from None
        return value

    @model_validator(mode="after")
    def _answers_only_without_secure_cookies(self) -> Self:
        if self.dev_expose_answers and self.cookie_secure:
            raise ValueError(
                "dev_expose_answers is test-only and cannot be used with secure cookies"
            )
        return self

    @model_validator(mode="after")
    def _resolve_secret_files(self) -> Self:
        if self.database_url is None:
            if self.database_url_file is None:
                raise ValueError("DATABASE_URL or DATABASE_URL_FILE is required")
            self.database_url = SecretStr(_read_secret_file(self.database_url_file, "database url"))
        if self.initial_signup_word_file is not None:
            self._initial_signup_word = SecretStr(
                _read_secret_file(self.initial_signup_word_file, "initial signup word")
            )
        self.read_admin_password()
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
