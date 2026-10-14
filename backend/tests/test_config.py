from pathlib import Path

import pytest
from pydantic import ValidationError

from mathquest.shared.config import Settings


def _clear(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in (
        "DATABASE_URL",
        "DATABASE_URL_FILE",
        "INITIAL_SIGNUP_WORD_FILE",
        "ADMIN_PASSWORD_FILE",
        "ADMIN_ALLOWED_CIDRS",
    ):
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


def test_exposed_answers_require_insecure_cookies(tmp_path: Path) -> None:
    secret = tmp_path / "db"
    secret.write_text("postgresql+asyncpg://u:p@h/db", encoding="utf-8")
    with pytest.raises(ValidationError, match="test-only"):
        Settings(database_url_file=secret, dev_expose_answers=True, cookie_secure=True)  # pyright: ignore[reportCallIssue]
    ok = Settings(database_url_file=secret, dev_expose_answers=True, cookie_secure=False)  # pyright: ignore[reportCallIssue]
    assert ok.dev_expose_answers is True


def test_admin_password_file_is_read_and_defaults_cover_private_ranges(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _clear(monkeypatch)
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://u:p@h/db")
    secret = tmp_path / "admin"
    secret.write_bytes(b"\xef\xbb\xbfs3cret-value \r\n")
    monkeypatch.setenv("ADMIN_PASSWORD_FILE", str(secret))
    settings = Settings()
    assert settings.admin_password is not None
    assert settings.admin_password.get_secret_value() == "s3cret-value"
    assert "s3cret-value" not in repr(settings)
    assert set(settings.admin_allowed_cidrs) == {
        "10.0.0.0/8",
        "172.16.0.0/12",
        "192.168.0.0/16",
        "127.0.0.1/32",
        "::1/128",
        "fc00::/7",
    }


def test_admin_allowed_cidrs_from_env_and_validation(monkeypatch: pytest.MonkeyPatch) -> None:
    _clear(monkeypatch)
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://u:p@h/db")
    monkeypatch.setenv("ADMIN_ALLOWED_CIDRS", "10.1.0.0/16, 192.168.5.0/24")
    assert Settings().admin_allowed_cidrs == ["10.1.0.0/16", "192.168.5.0/24"]
    monkeypatch.setenv("ADMIN_ALLOWED_CIDRS", "not-a-network")
    with pytest.raises(ValidationError):
        Settings()


def test_unreadable_admin_password_file_fails_without_echo(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _clear(monkeypatch)
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://u:p@h/db")
    monkeypatch.setenv("ADMIN_PASSWORD_FILE", str(tmp_path / "missing"))
    with pytest.raises(ValidationError):
        Settings()
