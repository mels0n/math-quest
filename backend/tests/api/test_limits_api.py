import asyncio

import httpx

from tests.conftest import SIGNUP_WORD, ApiFactory

CSRF = {"X-Requested-With": "mathquest"}


async def _signup(client: httpx.AsyncClient, n: int, **extra: str) -> httpx.Response:
    return await client.post(
        "/api/auth/signup",
        json={"signup_word": SIGNUP_WORD, "nickname": f"Kid{n:03d}", "pin": "1234"},
        headers={**CSRF, **extra},
    )


async def _login(client: httpx.AsyncClient, **extra: str) -> httpx.Response:
    return await client.post(
        "/api/auth/login", json={"nickname": "Nobody", "pin": "1234"}, headers={**CSRF, **extra}
    )


async def test_signup_is_limited_to_10_per_ip_per_hour(api: ApiFactory) -> None:
    h = await api()
    for n in range(10):
        assert (await _signup(h.client, n)).status_code == 200
    r = await _signup(h.client, 99)
    assert r.status_code == 429
    assert r.json() == {"error": "rate_limited"}
    assert int(r.headers["retry-after"]) > 0
    h.clock.advance(3601)
    assert (await _signup(h.client, 99)).status_code == 200


async def test_forwarded_for_is_ignored_from_untrusted_peer(api: ApiFactory) -> None:
    h = await api()
    for n in range(10):
        r = await _signup(h.client, n, **{"X-Forwarded-For": f"198.51.100.{n}"})
        assert r.status_code == 200
    r = await _signup(h.client, 99, **{"X-Forwarded-For": "198.51.100.200"})
    assert r.status_code == 429


async def test_forwarded_for_is_used_from_trusted_proxy(api: ApiFactory) -> None:
    h = await api(peer="10.0.0.5", trusted_proxies=["10.0.0.0/24"])
    for n in range(10):
        r = await _signup(h.client, n, **{"X-Forwarded-For": "198.51.100.1"})
        assert r.status_code == 200
    blocked = await _signup(h.client, 98, **{"X-Forwarded-For": "198.51.100.1"})
    assert blocked.status_code == 429
    other = await _signup(h.client, 99, **{"X-Forwarded-For": "198.51.100.2"})
    assert other.status_code == 200


async def test_login_and_recover_share_30_per_10_minutes(api: ApiFactory) -> None:
    h = await api()
    for _ in range(20):
        assert (await _login(h.client)).status_code == 401
    for _ in range(10):
        r = await h.client.post(
            "/api/auth/recover",
            json={"nickname": "Nobody", "recovery_word": "x", "new_pin": "1234"},
            headers=CSRF,
        )
        assert r.status_code == 401
    r = await _login(h.client)
    assert r.status_code == 429
    assert int(r.headers["retry-after"]) > 0
    h.clock.advance(601)
    assert (await _login(h.client)).status_code == 401


async def test_signup_and_login_counters_are_separate(api: ApiFactory) -> None:
    h = await api()
    for n in range(10):
        assert (await _signup(h.client, n)).status_code == 200
    assert (await _login(h.client)).status_code == 401


async def test_concurrent_signups_cannot_exceed_the_limit(api: ApiFactory) -> None:
    h = await api()
    results = await asyncio.gather(*(_signup(h.client, n) for n in range(40)))
    codes = [r.status_code for r in results]
    assert codes.count(200) == 10
    assert codes.count(429) == 30


async def test_concurrent_logins_cannot_exceed_the_limit(api: ApiFactory) -> None:
    h = await api()
    results = await asyncio.gather(*(_login(h.client) for _ in range(40)))
    codes = [r.status_code for r in results]
    assert codes.count(401) == 30
    assert codes.count(429) == 10
