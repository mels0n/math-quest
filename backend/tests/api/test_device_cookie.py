import re

import httpx

from tests.conftest import ApiFactory

_KEY = re.compile(r"[A-Za-z0-9_-]{16,64}")


def _set_device(r: httpx.Response) -> str | None:
    for header in r.headers.get_list("set-cookie"):
        if header.startswith("mq_device="):
            return header.split(";", 1)[0].split("=", 1)[1]
    return None


async def test_device_key_is_set_once_and_kept(api: ApiFactory) -> None:
    c = (await api()).client
    first = await c.get("/api/health")
    key = _set_device(first)
    assert key is not None
    assert _KEY.fullmatch(key)
    assert len(key) == 32
    second = await c.get("/api/health")
    assert _set_device(second) is None
    assert c.cookies.get("mq_device") == key


async def test_invalid_device_values_are_replaced(api: ApiFactory) -> None:
    c = (await api()).client
    for bad in ("*", "short", "x" * 65, "has space in it!!!!!", "a" * 15):
        c.cookies.clear()
        c.cookies.set("mq_device", bad)
        r = await c.get("/api/health")
        key = _set_device(r)
        assert key is not None, bad
        assert key != bad
        assert _KEY.fullmatch(key)


async def test_valid_client_chosen_device_value_is_kept(api: ApiFactory) -> None:
    c = (await api()).client
    c.cookies.set("mq_device", "A" * 16)
    r = await c.get("/api/health")
    assert _set_device(r) is None
