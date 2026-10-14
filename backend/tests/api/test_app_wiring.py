import types
from pathlib import Path
from typing import cast

import pytest
from fastapi import FastAPI, Request
from pydantic import SecretStr
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, create_async_engine

from mathquest.api.deps import get_db
from mathquest.app import main as app_main
from mathquest.app.main import create_app
from mathquest.engine.checker.bounded import CheckerPool
from mathquest.shared.config import Settings
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


async def test_lifespan_warms_the_checker_pool(api: ApiFactory) -> None:
    h = await api(real_pool=True)
    pool = h.app.state.checker_pool
    assert isinstance(pool, CheckerPool)
    assert pool._pool is not None  # pyright: ignore[reportPrivateUsage]


def _lifespan_app(
    monkeypatch: pytest.MonkeyPatch, *, inject_engine: bool
) -> tuple[FastAPI, AsyncEngine, list[str]]:
    """An app with no signup word (so startup touches no tables) and spies on shutdown."""
    calls: list[str] = []
    engine = create_async_engine("postgresql+asyncpg://u:p@127.0.0.1:1/none")

    async def dispose(_self: AsyncEngine, close: bool = True) -> None:
        calls.append("dispose")

    monkeypatch.setattr(AsyncEngine, "dispose", dispose)
    pool = CheckerPool()
    monkeypatch.setattr(pool, "warm", _noop)
    monkeypatch.setattr(pool, "close", lambda: calls.append("pool_close"))
    if not inject_engine:

        def make_engine(_url: str) -> AsyncEngine:
            return engine

        monkeypatch.setattr(app_main.database, "create_engine", make_engine)
    settings = Settings(database_url=SecretStr("postgresql+asyncpg://u:p@127.0.0.1:1/none"))
    app = create_app(settings, engine=engine if inject_engine else None, checker_pool=pool)
    return app, engine, calls


async def _noop() -> None:
    return None


async def test_shutdown_closes_pool_and_keeps_an_injected_engine(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    app, _, calls = _lifespan_app(monkeypatch, inject_engine=True)
    async with app.router.lifespan_context(app):
        assert calls == []
    assert calls == ["pool_close"]


async def test_shutdown_closes_pool_and_disposes_an_owned_engine(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    app, _, calls = _lifespan_app(monkeypatch, inject_engine=False)
    async with app.router.lifespan_context(app):
        assert calls == []
    assert calls == ["pool_close", "dispose"]


async def test_get_db_rolls_back_and_closes(api: ApiFactory) -> None:
    h = await api()
    real = h.app.state.session_factory
    closed: list[AsyncSession] = []

    def spying_factory() -> AsyncSession:
        session: AsyncSession = real()
        original = session.close

        async def close() -> None:
            closed.append(session)
            await original()

        session.close = close  # type: ignore[method-assign]  # pyright: ignore[reportAttributeAccessIssue]
        return session

    h.app.state.session_factory = spying_factory
    request = cast(Request, types.SimpleNamespace(app=h.app))
    gen = get_db(request)
    session = await anext(gen)
    await session.execute(select(text("1")))
    assert session.in_transaction()
    await gen.aclose()
    assert not session.in_transaction()
    assert closed == [session]
