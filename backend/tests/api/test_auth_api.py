import logging

import httpx
import pytest
from fastapi import FastAPI

from tests.conftest import SIGNUP_WORD, ApiFactory

CSRF = {"X-Requested-With": "mathquest"}
NICK = "SwiftOtter42"


async def _signup(
    client: httpx.AsyncClient, nickname: str = NICK, word: str = SIGNUP_WORD
) -> httpx.Response:
    return await client.post(
        "/api/auth/signup",
        json={"signup_word": word, "nickname": nickname, "pin": "1234"},
        headers=CSRF,
    )


async def _login(client: httpx.AsyncClient, nickname: str = NICK, pin: str = "1234"):
    return await client.post(
        "/api/auth/login", json={"nickname": nickname, "pin": pin}, headers=CSRF
    )


async def test_health(api: ApiFactory) -> None:
    r = await (await api()).client.get("/api/health")
    assert r.status_code == 200
    assert r.json() == {"ok": True}


async def test_signup_sets_cookies_and_me_returns_nickname(api: ApiFactory) -> None:
    c = (await api()).client
    r = await _signup(c)
    assert r.status_code == 200
    body = r.json()
    assert body["player"]["nickname"] == NICK
    assert isinstance(body["recovery_word"], str)
    assert body["recovery_word"]
    assert set(body) == {"player", "recovery_word"}
    assert c.cookies.get("mq_device")
    assert c.cookies.get("mq_session")

    me = await c.get("/api/me")
    assert me.status_code == 200
    assert me.json() == {"player": {"id": body["player"]["id"], "nickname": NICK}}
    assert "recovery_word" not in me.text


async def test_cookie_attributes(api: ApiFactory) -> None:
    c = (await api()).client
    r = await _signup(c)
    cookies = {h.split("=", 1)[0]: h.lower() for h in r.headers.get_list("set-cookie")}
    for name in ("mq_device", "mq_session"):
        attrs = cookies[name]
        assert "httponly" in attrs
        assert "max-age=34560000" in attrs
        assert "samesite=lax" in attrs
        assert "secure" not in attrs


async def test_cookies_are_secure_when_configured(api: ApiFactory) -> None:
    c = (await api(cookie_secure=True)).client
    r = await _signup(c)
    assert all("secure" in h.lower() for h in r.headers.get_list("set-cookie"))


async def test_wrong_signup_word_is_422(api: ApiFactory) -> None:
    r = await _signup((await api()).client, word="nope")
    assert r.status_code == 422
    assert r.json() == {"error": "signup_word"}


async def test_malformed_body_is_422_without_echo(api: ApiFactory) -> None:
    r = await (await api()).client.post(
        "/api/auth/signup", json={"nickname": "SECRETVALUE", "extra": 1}, headers=CSRF
    )
    assert r.status_code == 422
    assert r.json() == {"error": "invalid_request"}


async def test_duplicate_nickname_is_409(api: ApiFactory) -> None:
    c = (await api()).client
    assert (await _signup(c)).status_code == 200
    r = await _signup(c, nickname=NICK.lower())
    assert r.status_code == 409
    assert r.json() == {"error": "nickname_taken"}


async def test_missing_csrf_header_is_403(api: ApiFactory) -> None:
    c = (await api()).client
    for path, body in (
        ("/api/auth/signup", {"signup_word": SIGNUP_WORD, "nickname": NICK, "pin": "1234"}),
        ("/api/auth/login", {"nickname": NICK, "pin": "1234"}),
        ("/api/auth/recover", {"nickname": NICK, "recovery_word": "x", "new_pin": "1234"}),
        ("/api/auth/logout", None),
    ):
        r = await c.post(path, json=body)
        assert r.status_code == 403, path
        assert r.json() == {"error": "csrf"}
    wrong = await c.post("/api/auth/logout", headers={"X-Requested-With": "other"})
    assert wrong.status_code == 403
    assert (await c.get("/api/health")).status_code == 200


async def test_me_requires_a_valid_session(api: ApiFactory) -> None:
    c = (await api()).client
    r = await c.get("/api/me")
    assert r.status_code == 401
    assert r.json() == {"error": "unauthorized"}
    c.cookies.set("mq_session", "not-a-real-token")
    assert (await c.get("/api/me")).status_code == 401


async def test_login_success_and_failure(api: ApiFactory) -> None:
    owner = (await api()).client
    await _signup(owner)
    other = (await api()).client
    bad = await _login(other, pin="9999")
    assert bad.status_code == 401
    assert bad.json() == {"error": "unauthorized"}
    assert other.cookies.get("mq_session") is None
    ok = await _login(other)
    assert ok.status_code == 200
    assert ok.json()["player"]["nickname"] == NICK
    assert (await other.get("/api/me")).status_code == 200


async def test_login_with_picture(api: ApiFactory) -> None:
    c = (await api()).client
    r = await c.post(
        "/api/auth/signup",
        json={"signup_word": SIGNUP_WORD, "nickname": "PicKid", "picture": [1, 2, 3, 4]},
        headers=CSRF,
    )
    assert r.status_code == 200
    r = await c.post(
        "/api/auth/login", json={"nickname": "PicKid", "picture": [1, 2, 3, 4]}, headers=CSRF
    )
    assert r.status_code == 200


async def test_lockout_is_429_with_retry_after(api: ApiFactory) -> None:
    c = (await api()).client
    await _signup(c)
    for _ in range(5):
        assert (await _login(c, pin="0000")).status_code == 401
    r = await _login(c, pin="1234")
    assert r.status_code == 429
    assert r.json() == {"error": "locked"}
    assert int(r.headers["retry-after"]) > 0


async def test_logout_revokes_the_session(api: ApiFactory) -> None:
    c = (await api()).client
    await _signup(c)
    token = c.cookies.get("mq_session")
    assert token
    r = await c.post("/api/auth/logout", headers=CSRF)
    assert r.status_code == 200
    assert (await c.get("/api/me")).status_code == 401
    c.cookies.set("mq_session", token)
    assert (await c.get("/api/me")).status_code == 401


async def test_recover_replaces_credentials_and_revokes_old_sessions(api: ApiFactory) -> None:
    old = (await api()).client
    signup = (await _signup(old)).json()
    fresh = (await api()).client
    r = await fresh.post(
        "/api/auth/recover",
        json={"nickname": NICK, "recovery_word": signup["recovery_word"], "new_pin": "4321"},
        headers=CSRF,
    )
    assert r.status_code == 200
    body = r.json()
    assert body["player"]["nickname"] == NICK
    assert body["recovery_word"] != signup["recovery_word"]
    assert (await fresh.get("/api/me")).status_code == 200
    assert (await old.get("/api/me")).status_code == 401
    assert (await _login(fresh, pin="4321")).status_code == 200
    assert (await _login(fresh, pin="1234")).status_code == 401


async def test_recover_with_wrong_word_is_401(api: ApiFactory) -> None:
    c = (await api()).client
    await _signup(c)
    r = await c.post(
        "/api/auth/recover",
        json={"nickname": NICK, "recovery_word": "wrongword", "new_pin": "4321"},
        headers=CSRF,
    )
    assert r.status_code == 401


async def test_nickname_suggestion(api: ApiFactory) -> None:
    r = await (await api()).client.get("/api/auth/nickname-suggestion")
    assert r.status_code == 200
    nickname = r.json()["nickname"]
    assert 3 <= len(nickname) <= 16


async def test_unexpected_error_is_generic_500(
    api: ApiFactory, caplog: pytest.LogCaptureFixture
) -> None:
    harness = await api(raise_app_exceptions=False)
    app: FastAPI = harness.app

    @app.get("/api/boom")
    async def boom() -> None:  # pyright: ignore[reportUnusedFunction]
        raise RuntimeError("secret internal detail")

    # The lifespan reconfigures root logging, so attach the capture handler directly.
    logger = logging.getLogger("mathquest.api.errors")
    logger.addHandler(caplog.handler)
    try:
        r = await harness.client.get("/api/boom")
    finally:
        logger.removeHandler(caplog.handler)
    assert r.status_code == 500
    assert r.json() == {"error": "internal"}
    assert "secret internal detail" not in r.text
    assert "secret internal detail" in caplog.text


async def test_unknown_api_path_is_404(api: ApiFactory) -> None:
    c = (await api()).client
    r = await c.get("/api/nope")
    assert r.status_code == 404
    assert r.json() == {"error": "not_found"}
    wrong = await c.post("/api/health", headers=CSRF)
    assert wrong.status_code == 405
    assert wrong.json() == {"error": "method_not_allowed"}
