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
    url = Settings().database_url
    assert url is not None
    assert url.get_secret_value() == "postgresql+asyncpg://u:p@h/db"


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
    word.write_text("\ufeffrainbow\n", encoding="utf-8")
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://u:p@h/db")
    monkeypatch.setenv("INITIAL_SIGNUP_WORD_FILE", str(word))
    word = Settings().initial_signup_word
    assert word is not None
    assert word.get_secret_value() == "rainbow"


def test_repr_hides_secrets(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _clear(monkeypatch)
    word = tmp_path / "word"
    word.write_text("rainbow", encoding="utf-8")
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://user:hunter2@h/db")
    monkeypatch.setenv("INITIAL_SIGNUP_WORD_FILE", str(word))
    text = repr(Settings()) + str(Settings())
    assert "hunter2" not in text
    assert "rainbow" not in text


def test_signup_word_not_settable_from_env(monkeypatch: pytest.MonkeyPatch) -> None:
    _clear(monkeypatch)
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://u:p@h/db")
    monkeypatch.setenv("INITIAL_SIGNUP_WORD", "rainbow")
    assert Settings().initial_signup_word is None


def test_trusted_proxies_split_from_env_and_validated(monkeypatch: pytest.MonkeyPatch) -> None:
    _clear(monkeypatch)
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://u:p@h/db")
    assert Settings().trusted_proxies == []
    monkeypatch.setenv("TRUSTED_PROXIES", "10.0.1.0/24, fd00::/8")
    assert Settings().trusted_proxies == ["10.0.1.0/24", "fd00::/8"]
    monkeypatch.setenv("TRUSTED_PROXIES", "nonsense")
    with pytest.raises(ValidationError):
        Settings()
