from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from pathlib import Path

import httpx
import pytest
from sqlalchemy import select

from mathquest.entities.admin import AdminAudit
from tests.conftest import SIGNUP_WORD, Api, ApiFactory

CSRF = {"X-Requested-With": "mathquest"}
PASSWORD = "correct horse battery staple"
LAN = "192.168.1.20"
GHOST = "00000000-0000-0000-0000-000000000001"


@pytest.fixture
def password_file(tmp_path: Path) -> Path:
    path = tmp_path / "admin_password"
    path.write_text(PASSWORD + "\n", encoding="utf-8")
    return path


async def _admin(api: ApiFactory, password_file: Path) -> Api:
    h = await api(peer=LAN, admin_password_file=password_file)
    r = await h.client.post("/api/admin/login", json={"password": PASSWORD}, headers=CSRF)
    assert r.status_code == 200
    return h


@asynccontextmanager
async def _kid_client(h: Api) -> AsyncGenerator[httpx.AsyncClient]:
    """A client with its own cookie jar, so kid and admin cookies never mix."""
    transport = httpx.ASGITransport(app=h.app, client=("10.1.1.1", 50000))
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as kid:
        yield kid


async def _signup(
    client: httpx.AsyncClient, nickname: str, word: str = SIGNUP_WORD
) -> httpx.Response:
    return await client.post(
        "/api/auth/signup",
        json={"signup_word": word, "nickname": nickname, "pin": "1234"},
        headers=CSRF,
    )


async def _kid(h: Api, nickname: str) -> tuple[str, str]:
    async with _kid_client(h) as kid:
        r = await _signup(kid, nickname)
    assert r.status_code == 200
    return r.json()["player"]["id"], r.json()["recovery_word"]


async def _login_status(h: Api, nickname: str, pin: str) -> int:
    async with _kid_client(h) as kid:
        r = await kid.post("/api/auth/login", json={"nickname": nickname, "pin": pin}, headers=CSRF)
    return r.status_code


async def test_list_shape_and_search(api: ApiFactory, password_file: Path) -> None:
    h = await _admin(api, password_file)
    pid, _ = await _kid(h, "SwiftOtter")
    await _kid(h, "Zebra")
    r = await h.client.get("/api/admin/players", params={"query": "otter"})
    assert r.status_code == 200
    (row,) = r.json()
    assert set(row) == {"id", "nickname", "hidden", "created_at", "last_seen"}
    assert row["id"] == pid
    assert row["hidden"] is False
    assert len((await h.client.get("/api/admin/players")).json()) == 2
    assert len((await h.client.get("/api/admin/players", params={"limit": 1})).json()) == 1


@pytest.mark.parametrize("params", [{"limit": 101}, {"limit": 0}, {"offset": -1}])
async def test_list_rejects_out_of_range_paging(
    api: ApiFactory, password_file: Path, params: dict[str, int]
) -> None:
    h = await _admin(api, password_file)
    assert (await h.client.get("/api/admin/players", params=params)).status_code == 422


async def test_routes_need_an_admin_session(api: ApiFactory, password_file: Path) -> None:
    h = await api(peer=LAN, admin_password_file=password_file)
    calls = [
        ("GET", "/api/admin/players", None),
        ("POST", f"/api/admin/players/{GHOST}/hide", None),
        ("POST", f"/api/admin/players/{GHOST}/unhide", None),
        ("POST", f"/api/admin/players/{GHOST}/rename", {"nickname": "Whoever"}),
        ("POST", f"/api/admin/players/{GHOST}/reset-pin", {"pin": "1234"}),
        ("DELETE", f"/api/admin/players/{GHOST}", None),
        ("GET", "/api/admin/signup-word", None),
        ("PUT", "/api/admin/signup-word", {"word": "abc"}),
    ]
    for method, path, body in calls:
        r = await h.client.request(method, path, json=body, headers=CSRF)
        assert r.status_code == 401, (method, path)


async def test_off_lan_new_routes_are_404(api: ApiFactory, password_file: Path) -> None:
    h = await api(peer="203.0.113.50", admin_password_file=password_file)
    for method, path in (
        ("GET", "/api/admin/players"),
        ("DELETE", f"/api/admin/players/{GHOST}"),
        ("PUT", "/api/admin/signup-word"),
        ("POST", f"/api/admin/players/{GHOST}/reset-pin"),
    ):
        r = await h.client.request(method, path, headers=CSRF)
        assert r.status_code == 404, (method, path)


async def test_state_changing_routes_require_csrf(api: ApiFactory, password_file: Path) -> None:
    h = await _admin(api, password_file)
    pid, _ = await _kid(h, "Alpha")
    for method, path, body in (
        ("POST", f"/api/admin/players/{pid}/hide", None),
        ("POST", f"/api/admin/players/{pid}/unhide", None),
        ("POST", f"/api/admin/players/{pid}/rename", {"nickname": "Beta"}),
        ("POST", f"/api/admin/players/{pid}/reset-pin", {"pin": "4321"}),
        ("DELETE", f"/api/admin/players/{pid}", None),
        ("PUT", "/api/admin/signup-word", {"word": "abc"}),
    ):
        r = await h.client.request(method, path, json=body)
        assert r.status_code == 403, (method, path)
        assert r.json() == {"error": "csrf"}
    assert await _login_status(h, "Alpha", "1234") == 200


async def test_hide_makes_login_look_like_an_unknown_nickname(
    api: ApiFactory, password_file: Path
) -> None:
    h = await _admin(api, password_file)
    pid, _ = await _kid(h, "Alpha")
    assert (await h.client.post(f"/api/admin/players/{pid}/hide", headers=CSRF)).status_code == 200
    assert await _login_status(h, "Alpha", "1234") == await _login_status(h, "Nobody", "1234")
    (row,) = (await h.client.get("/api/admin/players")).json()
    assert row["hidden"] is True
    await h.client.post(f"/api/admin/players/{pid}/unhide", headers=CSRF)
    assert await _login_status(h, "Alpha", "1234") == 200


async def test_rename_conflicts_and_blocked_names(api: ApiFactory, password_file: Path) -> None:
    h = await _admin(api, password_file)
    pid, _ = await _kid(h, "Alpha")
    await _kid(h, "Bravo")
    url = f"/api/admin/players/{pid}/rename"
    ok = await h.client.post(url, json={"nickname": "Delta"}, headers=CSRF)
    assert ok.status_code == 200
    taken = await h.client.post(url, json={"nickname": "bravo"}, headers=CSRF)
    assert (taken.status_code, taken.json()) == (409, {"error": "nickname_taken"})
    bad = await h.client.post(url, json={"nickname": "no!"}, headers=CSRF)
    assert (bad.status_code, bad.json()) == (422, {"error": "nickname"})
    ghost = await h.client.post(
        f"/api/admin/players/{GHOST}/rename", json={"nickname": "Echo"}, headers=CSRF
    )
    assert ghost.status_code == 404
    junk = await h.client.post(
        "/api/admin/players/not-a-uuid/rename", json={"nickname": "Echo"}, headers=CSRF
    )
    assert junk.status_code == 422


async def test_reset_pin_returns_a_new_word_and_signs_devices_out(
    api: ApiFactory, password_file: Path
) -> None:
    h = await _admin(api, password_file)
    pid, word = await _kid(h, "Alpha")
    url = f"/api/admin/players/{pid}/reset-pin"
    r = await h.client.post(url, json={"pin": "4321"}, headers=CSRF)
    assert r.status_code == 200
    assert set(r.json()) == {"recovery_word"}
    assert r.json()["recovery_word"] != word
    assert await _login_status(h, "Alpha", "1234") == 401
    assert await _login_status(h, "Alpha", "4321") == 200
    for pin in ("123", "12345", "abcd"):
        bad = await h.client.post(url, json={"pin": pin}, headers=CSRF)
        assert bad.status_code == 422


async def test_delete_player(api: ApiFactory, password_file: Path) -> None:
    h = await _admin(api, password_file)
    pid, _ = await _kid(h, "Alpha")
    await _kid(h, "Bravo")
    r = await h.client.delete(f"/api/admin/players/{pid}", headers=CSRF)
    assert r.status_code == 200
    assert [p["nickname"] for p in (await h.client.get("/api/admin/players")).json()] == ["Bravo"]
    assert await _login_status(h, "Alpha", "1234") == 401
    assert await _login_status(h, "Bravo", "1234") == 200
    again = await h.client.delete(f"/api/admin/players/{pid}", headers=CSRF)
    assert again.status_code == 404


async def test_signup_word_state_never_returns_the_word(
    api: ApiFactory, password_file: Path
) -> None:
    h = await _admin(api, password_file)
    assert (await h.client.get("/api/admin/signup-word")).json() == {"set": True}
    put = await h.client.put("/api/admin/signup-word", json={"word": "Sunshine"}, headers=CSRF)
    assert (put.status_code, put.json()) == (200, {"ok": True})
    state = await h.client.get("/api/admin/signup-word")
    assert state.json() == {"set": True}
    assert "Sunshine" not in state.text + put.text
    bad = await h.client.put("/api/admin/signup-word", json={"word": "no"}, headers=CSRF)
    assert bad.status_code == 422
    async with _kid_client(h) as kid:
        assert (await _signup(kid, "Alpha")).status_code == 422
        assert (await _signup(kid, "Alpha", "Sunshine")).status_code == 200


async def test_audit_rows_carry_session_and_nickname_but_no_secrets(
    api: ApiFactory, password_file: Path
) -> None:
    h = await _admin(api, password_file)
    pid, word = await _kid(h, "Alpha")
    await h.client.post(f"/api/admin/players/{pid}/reset-pin", json={"pin": "4321"}, headers=CSRF)
    await h.client.put("/api/admin/signup-word", json={"word": "Sunshine"}, headers=CSRF)
    await h.client.delete(f"/api/admin/players/{pid}", headers=CSRF)
    async with h.app.state.session_factory() as session:
        rows = (await session.execute(select(AdminAudit).order_by(AdminAudit.id))).scalars().all()
    assert [r.action for r in rows] == ["login", "reset_pin", "signup_word", "delete"]
    assert all(r.admin_session_id == rows[0].admin_session_id for r in rows)
    assert [r.target_nickname for r in rows] == [None, "Alpha", None, "Alpha"]
    dumped = repr([(r.action, r.target_nickname) for r in rows])
    for secret in ("4321", "Sunshine", word):
        assert secret not in dumped
