from pathlib import Path

import pytest
from pydantic import ValidationError

from mathquest.shared.config import Settings


def _clear(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in ("DATABASE_URL", "DATABASE_URL_FILE", "INITIAL_SIGNUP_WORD_FILE"):
        monkeypatch.delenv(name, raising=False)


def test_database_url_file_strips_bom_and_whitespace(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _clear(monkeypatch)
    secret = tmp_path / "db"
    secret.write_bytes(b"\xef\xbb\xbfpostgresql+asyncpg://u:p@h/db \r\n")
    monkeypatch.setenv("DATABASE_URL_FILE", str(secret))
    assert Settings().database_url == "postgresql+asyncpg://u:p@h/db"


def test_missing_database_config_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    _clear(monkeypatch)
    with pytest.raises(ValidationError):
        Settings()


def test_unreadable_secret_error_does_not_echo_contents(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _clear(monkeypatch)
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://user:hunter2@h/db")
    monkeypatch.setenv("INITIAL_SIGNUP_WORD_FILE", str(tmp_path / "missing"))
    with pytest.raises(ValidationError) as err:
        Settings()
    assert "hunter2" not in str(err.value)


def test_initial_signup_word_is_read_from_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _clear(monkeypatch)
    word = tmp_path / "word"
    word.write_text("﻿rainbow\n", encoding="utf-8")
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://u:p@h/db")
    monkeypatch.setenv("INITIAL_SIGNUP_WORD_FILE", str(word))
    assert Settings().initial_signup_word == "rainbow"
