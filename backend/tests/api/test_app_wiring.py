import types
from pathlib import Path
from typing import cast

from fastapi import Request
from sqlalchemy import select, text

from mathquest.api.deps import get_db
from mathquest.engine.checker.bounded import CheckerPool
from tests.conftest import ApiFactory


async def test_spa_fallback_and_assets(api: ApiFactory, tmp_path: Path) -> None:
    static = tmp_path / "static"
    static.mkdir()
    (static / "index.html").write_text("<html>SPA</html>", encoding="utf-8")
    (static / "app.js").write_text("console.log(1)", encoding="utf-8")
    h = await api(static_dir=static)
    root = await h.client.get("/")
    assert root.status_code == 200
    assert "SPA" in root.text
    deep = await h.client.get("/play/some/route")
    assert deep.status_code == 200
    assert "SPA" in deep.text
    assert (await h.client.get("/app.js")).text == "console.log(1)"
    assert (await h.client.get("/api/health")).json() == {"ok": True}
    missing = await h.client.get("/api/nope")
    assert missing.status_code == 404
    assert "SPA" not in missing.text


async def test_no_static_mount_without_static_dir(api: ApiFactory) -> None:
    assert (await (await api()).client.get("/")).status_code == 404


async def test_lifespan_builds_and_closes_the_checker_pool(api: ApiFactory) -> None:
    h = await api(real_pool=True)
    pool = h.app.state.checker_pool
    assert isinstance(pool, CheckerPool)
    assert pool._pool is not None  # pyright: ignore[reportPrivateUsage]


async def test_get_db_rolls_back_and_closes(api: ApiFactory) -> None:
    h = await api()
    request = cast(Request, types.SimpleNamespace(app=h.app))
    gen = get_db(request)
    session = await anext(gen)
    await session.execute(select(text("1")))
    assert session.in_transaction()
    await gen.aclose()
    assert not session.in_transaction()
