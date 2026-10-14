import hashlib
import logging
import re
from collections.abc import Generator
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from pathlib import Path

import httpx
import pytest
from pydantic import SecretStr
from sqlalchemy import select, text

from mathquest.app.main import create_app
from mathquest.engine.checker.bounded import CheckerPool
from mathquest.entities.admin import AdminAudit, AdminSession
from mathquest.shared.config import Settings
from tests.conftest import Api, ApiFactory

CSRF = {"X-Requested-With": "mathquest"}
PASSWORD = "correct horse battery staple"
LAN = "192.168.1.20"
NOT_FOUND = {"error": "not_found"}


@pytest.fixture
def password_file(tmp_path: Path) -> Path:
    path = tmp_path / "admin_password"
    path.write_text(PASSWORD + "\n", encoding="utf-8")
    return path


async def _login(
    client: httpx.AsyncClient, password: str = PASSWORD, headers: dict[str, str] = CSRF
) -> httpx.Response:
    return await client.post("/api/admin/login", json={"password": password}, headers=headers)


async def _admin(api: ApiFactory, password_file: Path, **overrides: object) -> Api:
    return await api(peer=LAN, admin_password_file=password_file, **overrides)


METHODS = ("GET", "HEAD", "POST", "PUT", "DELETE", "OPTIONS")
ADMIN_PATHS = (
    "/api/admin/login",
    "/api/admin/logout",
    "/api/admin/me",
    "/api/admin/me/",
    "/api/admin/x",
    "/api/admin",
    "/api/admin/",
    "/api/Admin/me",
    "/api//admin/me",
    "/api/./admin/me",
    "/api/other/../admin/me",
    "/api/%61dmin/me",
    "/api/admin%2Fme",
    "/api%2Fadmin/me",
    "/api/%2561dmin/me",
)


@pytest.fixture(params=[False, True], ids=["no-static", "with-static"])
def static_overrides(request: pytest.FixtureRequest, tmp_path: Path) -> dict[str, object]:
    if not request.param:
        return {}
    static = tmp_path / "static"
    static.mkdir()
    (static / "index.html").write_text("<html>SPA</html>", encoding="utf-8")
    return {"static_dir": static}


def _shape(r: httpx.Response) -> tuple[object, ...]:
    return (
        r.status_code,
        r.text,
        r.headers.get("content-type"),
        r.headers.get("content-length"),
        sorted(h.split("=", 1)[0] for h in r.headers.get_list("set-cookie")),
    )


async def test_off_lan_admin_is_indistinguishable_from_an_unknown_api_path(
    api: ApiFactory, password_file: Path, static_overrides: dict[str, object]
) -> None:
    h = await api(peer="203.0.113.50", admin_password_file=password_file, **static_overrides)
    bodies: tuple[bytes | None, ...] = (None, b"{", b'{"password": "x"}')
    for method in METHODS:
        for content in bodies:
            for headers in (
                {"Content-Type": "application/json", **CSRF},
                {"Content-Type": "application/json"},
            ):
                h.client.cookies.clear()
                unknown = await h.client.request(
                    method, "/api/nope", content=content, headers=headers
                )
                assert unknown.status_code == 404
                if method != "HEAD":
                    assert unknown.json() == NOT_FOUND
                for path in ADMIN_PATHS:
                    h.client.cookies.clear()
                    r = await h.client.request(method, path, content=content, headers=headers)
                    assert _shape(r) == _shape(unknown), (method, path, content)
                    assert "mq_admin" not in r.headers.get("set-cookie", "")


CASE_AND_ENCODING_VARIANTS = (
    "/API/admin/me",
    "/Api/Admin",
    "/%2561pi/admin/me",
    "/x/%252e%252e/api/admin/me",
    "/%41pi/admin/me",
    "/api/%2e%2e/api/admin/me",
)


def _control(path: str) -> str:
    return re.sub(r"(?i)%(?:25)?61dmin|admin", "nope", path)


async def test_off_lan_admin_variants_match_a_non_admin_control_with_static(
    api: ApiFactory, password_file: Path, tmp_path: Path
) -> None:
    static = tmp_path / "static"
    static.mkdir()
    (static / "index.html").write_text("<html>SPA</html>", encoding="utf-8")
    h = await api(peer="203.0.113.50", admin_password_file=password_file, static_dir=static)
    for method in ("GET", "HEAD", "POST", "OPTIONS"):
        for path in (*ADMIN_PATHS, *CASE_AND_ENCODING_VARIANTS):
            h.client.cookies.clear()
            admin = await h.client.request(method, path, headers=CSRF)
            h.client.cookies.clear()
            control = await h.client.request(method, _control(path), headers=CSRF)
            assert control.status_code == 404, (method, _control(path))
            assert _shape(admin) == _shape(control), (method, path)


async def test_trusted_proxy_must_name_an_untrusted_client(
    api: ApiFactory, password_file: Path
) -> None:
    h = await api(peer="10.0.0.2", trusted_proxies="10.0.0.2", admin_password_file=password_file)
    for extra in (
        {},
        {"Forwarded": "for=192.168.1.77"},
        {"X-Forwarded-For": "10.0.0.2"},
        {"X-Forwarded-For": "garbage"},
        {"X-Forwarded-For": "192.168.1.77, garbage"},
    ):
        r = await _login(h.client, headers={**CSRF, **extra})
        assert r.status_code == 404, extra
        assert r.json() == NOT_FOUND


async def test_every_api_path_without_a_route_is_404_for_any_method(
    api: ApiFactory, password_file: Path, static_overrides: dict[str, object]
) -> None:
    h = await api(peer=LAN, admin_password_file=password_file, **static_overrides)
    for method in METHODS:
        for path in ("/api/nope", "/api/auth/signup/extra", "/api"):
            r = await h.client.request(method, path, headers=CSRF)
            assert r.status_code == 404, (method, path)
    wrong_method = await h.client.post("/api/health", headers=CSRF)
    assert wrong_method.status_code == (404 if static_overrides else 405)


async def test_forwarding_headers_from_an_untrusted_peer_are_404(
    api: ApiFactory, password_file: Path
) -> None:
    for peer in ("203.0.113.50", LAN):
        h = await api(peer=peer, admin_password_file=password_file)
        for extra in ({"X-Forwarded-For": LAN}, {"Forwarded": f"for={LAN}"}):
            headers = {**CSRF, **extra}
            for r in (
                await _login(h.client, headers=headers),
                await h.client.get("/api/admin/me", headers=headers),
            ):
                assert r.status_code == 404
                assert r.json() == NOT_FOUND


async def test_trusted_proxy_uses_the_forwarded_client(
    api: ApiFactory, password_file: Path
) -> None:
    h = await api(peer="10.0.0.2", trusted_proxies="10.0.0.2", admin_password_file=password_file)
    outside = await _login(h.client, headers={**CSRF, "X-Forwarded-For": "198.51.100.9"})
    assert outside.status_code == 404
    inside = await _login(h.client, headers={**CSRF, "X-Forwarded-For": "192.168.1.77"})
    assert inside.status_code == 200


async def test_custom_allowed_cidrs(api: ApiFactory, password_file: Path) -> None:
    h = await api(peer=LAN, admin_password_file=password_file, admin_allowed_cidrs="10.9.0.0/16")
    assert (await _login(h.client)).status_code == 404


async def test_wrong_password_is_generic_401(api: ApiFactory, password_file: Path) -> None:
    c = (await _admin(api, password_file)).client
    r = await _login(c, "nope")
    assert r.status_code == 401
    assert r.json() == {"error": "unauthorized"}
    assert "mq_admin" not in r.headers.get("set-cookie", "")
    assert (await _login(c, "")).status_code == 401


async def test_login_requires_csrf_header_on_lan(api: ApiFactory, password_file: Path) -> None:
    c = (await _admin(api, password_file)).client
    assert (await _login(c, headers={})).status_code == 403


async def test_eleventh_login_in_ten_minutes_is_429(api: ApiFactory, password_file: Path) -> None:
    h = await _admin(api, password_file)
    for _ in range(10):
        assert (await _login(h.client, "nope")).status_code == 401
    blocked = await _login(h.client)
    assert blocked.status_code == 429
    assert blocked.json() == {"error": "rate_limited"}
    assert int(blocked.headers["retry-after"]) > 0
    h.clock.advance(601)
    assert (await _login(h.client)).status_code == 200


async def test_login_sets_strict_cookie_and_me_works(api: ApiFactory, password_file: Path) -> None:
    h = await _admin(api, password_file)
    r = await _login(h.client)
    assert r.status_code == 200
    assert r.json() == {"ok": True}
    cookie = next(c for c in r.headers.get_list("set-cookie") if c.startswith("mq_admin="))
    attrs = cookie.lower()
    assert "httponly" in attrs
    assert "samesite=strict" in attrs
    assert "max-age=28800" in attrs
    assert "path=/api/admin" in attrs
    assert "secure" not in attrs
    me = await h.client.get("/api/admin/me")
    assert me.status_code == 200
    assert me.json() == {"ok": True}


async def test_cookie_is_secure_when_configured(api: ApiFactory, password_file: Path) -> None:
    h = await _admin(api, password_file, cookie_secure=True)
    r = await _login(h.client)
    cookie = next(c for c in r.headers.get_list("set-cookie") if c.startswith("mq_admin="))
    assert "secure" in cookie.lower()


async def test_me_without_session_is_401(api: ApiFactory, password_file: Path) -> None:
    c = (await _admin(api, password_file)).client
    r = await c.get("/api/admin/me")
    assert r.status_code == 401
    assert r.json() == {"error": "unauthorized"}
    c.cookies.set("mq_admin", "x" * 43, path="/api/admin")
    assert (await c.get("/api/admin/me")).status_code == 401


async def test_only_the_token_hash_is_stored(api: ApiFactory, password_file: Path) -> None:
    h = await _admin(api, password_file)
    await _login(h.client)
    token = h.client.cookies.get("mq_admin")
    assert token
    async with h.app.state.session_factory() as session:
        row = (await session.execute(select(AdminSession))).scalar_one()
        assert row.token_hash == hashlib.sha256(token.encode()).hexdigest()
        assert row.expires_at - row.created_at == timedelta(hours=8)


async def test_expired_session_is_401(api: ApiFactory, password_file: Path) -> None:
    h = await _admin(api, password_file)
    await _login(h.client)
    async with h.app.state.session_factory() as session:
        await session.execute(
            text("UPDATE admin_sessions SET expires_at = :t"),
            {"t": datetime.now(UTC) - timedelta(seconds=1)},
        )
        await session.commit()
    assert (await h.client.get("/api/admin/me")).status_code == 401


async def test_logout_revokes_and_audits(api: ApiFactory, password_file: Path) -> None:
    h = await _admin(api, password_file)
    await _login(h.client)
    token = h.client.cookies.get("mq_admin")
    out = await h.client.post("/api/admin/logout", headers=CSRF)
    assert out.status_code == 200
    assert out.json() == {"ok": True}
    cleared = next(c for c in out.headers.get_list("set-cookie") if c.startswith("mq_admin="))
    assert "path=/api/admin" in cleared.lower()
    h.client.cookies.set("mq_admin", token or "", path="/api/admin")
    assert (await h.client.get("/api/admin/me")).status_code == 401
    async with h.app.state.session_factory() as session:
        assert (await session.execute(select(AdminSession))).first() is None
        rows = (await session.execute(select(AdminAudit).order_by(AdminAudit.id))).scalars().all()
        assert [r.action for r in rows] == ["login", "logout"]
        assert rows[0].admin_session_id is not None
        assert rows[0].admin_session_id == rows[1].admin_session_id
        assert all(r.player_id is None for r in rows)


async def test_not_configured_means_every_admin_route_is_404(api: ApiFactory) -> None:
    with captured_logs() as records:
        h = await api(peer=LAN)
    warnings = [r for r in records if r.levelno == logging.WARNING]
    assert [r.getMessage() for r in warnings] == [
        "admin password is not configured; /api/admin is disabled"
    ]
    assert (await h.client.get("/api/health")).status_code == 200
    for r in (
        await _login(h.client),
        await h.client.get("/api/admin/me"),
        await h.client.post("/api/admin/logout", headers=CSRF),
    ):
        assert r.status_code == 404
        assert r.json() == NOT_FOUND


class _NoWarmPool(CheckerPool):
    async def warm(self) -> None:
        return None


@contextmanager
def captured_logs() -> Generator[list[logging.LogRecord]]:
    """Records from the `mathquest` logger; unlike caplog it survives configure_logging()."""
    logger = logging.getLogger("mathquest")
    records: list[logging.LogRecord] = []
    handler = logging.Handler(logging.DEBUG)
    handler.emit = records.append  # type: ignore[method-assign]
    previous = logger.level
    logger.setLevel(logging.DEBUG)
    logger.addHandler(handler)
    try:
        yield records
    finally:
        logger.removeHandler(handler)
        logger.setLevel(previous)


async def test_plaintext_password_is_not_kept_or_logged(
    api: ApiFactory, password_file: Path
) -> None:
    with captured_logs() as records:
        logging.getLogger("mathquest.canary").info("canary")
        h = await _admin(api, password_file)
        await _login(h.client, "wrong-guess")
        await _login(h.client)
    assert [r.getMessage() for r in records if r.name == "mathquest.canary"] == ["canary"]
    text_logged = " ".join(r.getMessage() for r in records)
    assert PASSWORD not in text_logged
    assert "wrong-guess" not in text_logged
    assert h.app.state.admin_password_hash.startswith("$argon2id$")
    private: dict[str, object] = h.app.state.settings.__pydantic_private__ or {}
    for value in private.values():
        if isinstance(value, SecretStr):
            assert value.get_secret_value() != PASSWORD


async def test_global_login_cap_across_addresses(api: ApiFactory, password_file: Path) -> None:
    h = await api(peer="10.0.0.2", trusted_proxies="10.0.0.2", admin_password_file=password_file)
    for n in range(30):
        r = await _login(h.client, "nope", {**CSRF, "X-Forwarded-For": f"192.168.1.{n + 1}"})
        assert r.status_code == 401, n
    over = await _login(h.client, PASSWORD, {**CSRF, "X-Forwarded-For": "192.168.1.200"})
    assert over.status_code == 429
    assert over.json() == {"error": "rate_limited"}


async def test_logout_requires_csrf_header_on_lan(api: ApiFactory, password_file: Path) -> None:
    h = await _admin(api, password_file)
    await _login(h.client)
    assert (await h.client.post("/api/admin/logout")).status_code == 403
    assert (await h.client.get("/api/admin/me")).status_code == 200


async def test_two_boots_on_one_settings_both_enable_admin(
    api: ApiFactory, password_file: Path, tmp_path: Path
) -> None:
    first = await _admin(api, password_file)
    settings = first.app.state.settings
    assert isinstance(settings, Settings)
    bind = first.app.state.session_factory.kw["bind"]
    for _ in range(2):
        app = create_app(settings, engine=bind, checker_pool=_NoWarmPool())
        async with app.router.lifespan_context(app):
            assert app.state.admin_password_hash.startswith("$argon2id$")
