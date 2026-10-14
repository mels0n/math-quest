import hashlib
import logging
from datetime import UTC, datetime, timedelta
from pathlib import Path

import httpx
import pytest
from sqlalchemy import select, text

from mathquest.entities.admin import AdminAudit, AdminSession
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


async def test_off_lan_gets_404_on_every_admin_route(api: ApiFactory, password_file: Path) -> None:
    h = await api(peer="203.0.113.50", admin_password_file=password_file)
    unknown = await h.client.get("/api/nope")
    assert unknown.status_code == 404
    for method, path in (
        ("POST", "/api/admin/login"),
        ("POST", "/api/admin/logout"),
        ("GET", "/api/admin/me"),
        ("GET", "/api/admin/anything-else"),
    ):
        for headers in (CSRF, {}):
            r = await h.client.request(method, path, json={"password": PASSWORD}, headers=headers)
            assert r.status_code == 404, (method, path, headers)
            assert r.json() == NOT_FOUND
            assert r.text == unknown.text
            assert "mq_admin" not in r.headers.get("set-cookie", "")


async def test_spoofed_forwarded_for_from_untrusted_peer_is_404(
    api: ApiFactory, password_file: Path
) -> None:
    h = await api(peer="203.0.113.50", admin_password_file=password_file)
    spoof = {**CSRF, "X-Forwarded-For": LAN}
    for r in (
        await _login(h.client, headers=spoof),
        await h.client.get("/api/admin/me", headers=spoof),
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
    boot = logging.getLogger("mathquest.app.main")
    records: list[logging.LogRecord] = []
    handler = logging.Handler()
    handler.emit = records.append  # type: ignore[method-assign]
    boot.addHandler(handler)
    try:
        h = await api(peer=LAN)
    finally:
        boot.removeHandler(handler)
    warnings = [r for r in records if r.levelno == logging.WARNING and "admin" in r.getMessage()]
    assert len(warnings) == 1
    assert (await h.client.get("/api/health")).status_code == 200
    for r in (
        await _login(h.client),
        await h.client.get("/api/admin/me"),
        await h.client.post("/api/admin/logout", headers=CSRF),
    ):
        assert r.status_code == 404
        assert r.json() == NOT_FOUND


async def test_plaintext_password_is_not_kept(
    api: ApiFactory, password_file: Path, caplog: pytest.LogCaptureFixture
) -> None:
    with caplog.at_level(logging.DEBUG):
        h = await _admin(api, password_file)
        await _login(h.client, "wrong-guess")
    assert h.app.state.admin_password_hash.startswith("$argon2id$")
    assert h.app.state.settings.admin_password is None
    assert PASSWORD not in caplog.text
    assert "wrong-guess" not in caplog.text
