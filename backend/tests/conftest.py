"""Shared fixtures. DB tests run in a uniquely named Postgres schema built by Alembic."""

import asyncio
import os
import uuid
from collections.abc import AsyncIterator, Awaitable, Callable, Iterator
from contextlib import AsyncExitStack
from dataclasses import dataclass
from pathlib import Path

import httpx
import pytest
from alembic import command
from alembic.config import Config
from fastapi import FastAPI
from pydantic import SecretStr
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, create_async_engine
from sqlalchemy.pool import NullPool

from mathquest.app.main import create_app
from mathquest.engine.checker.bounded import CheckerPool
from mathquest.shared.config import Settings

BACKEND_DIR = Path(__file__).resolve().parents[1]


def _database_url() -> str:
    url = os.environ.get("TEST_DATABASE_URL")
    if not url:
        pytest.fail("TEST_DATABASE_URL is not set (asyncpg URL of a throwaway Postgres)")
    return url


def _schema_engine(url: str, schema: str | None) -> AsyncEngine:
    connect_args: dict[str, object] = {}
    if schema is not None:
        connect_args["server_settings"] = {"search_path": schema}
    return create_async_engine(url, poolclass=NullPool, connect_args=connect_args)


async def _exec(url: str, statement: str) -> None:
    engine = _schema_engine(url, None)
    try:
        async with engine.begin() as conn:
            await conn.execute(text(statement))
    finally:
        await engine.dispose()


@pytest.fixture(scope="session")
def db_schema() -> Iterator[str]:
    url = _database_url()
    schema = f"mq_test_{uuid.uuid4().hex[:12]}"
    asyncio.run(_exec(url, f'CREATE SCHEMA "{schema}"'))
    try:
        cfg = Config(str(BACKEND_DIR / "alembic.ini"))
        cfg.set_main_option("script_location", str(BACKEND_DIR / "migrations"))
        cfg.attributes["url"] = url
        cfg.attributes["search_path"] = schema
        command.upgrade(cfg, "head")
        yield schema
    finally:
        asyncio.run(_exec(url, f'DROP SCHEMA IF EXISTS "{schema}" CASCADE'))


@pytest.fixture
async def db(db_schema: str) -> AsyncIterator[AsyncSession]:
    """A session whose work is rolled back at the end of the test."""
    engine = _schema_engine(_database_url(), db_schema)
    try:
        async with engine.connect() as conn:
            outer = await conn.begin()
            session = AsyncSession(
                bind=conn, join_transaction_mode="create_savepoint", expire_on_commit=False
            )
            try:
                yield session
            finally:
                await session.close()
                await outer.rollback()
    finally:
        await engine.dispose()


SIGNUP_WORD = "rainbow"


class FakeClock:
    """A float clock the tests advance by hand."""

    def __init__(self) -> None:
        self.t = 1_000.0

    def __call__(self) -> float:
        return self.t

    def advance(self, seconds: float) -> None:
        self.t += seconds


class _ColdPool(CheckerPool):
    """A checker pool that skips spawning workers on warm-up."""

    async def warm(self) -> None:
        return None


@dataclass
class Api:
    client: httpx.AsyncClient
    app: FastAPI
    clock: FakeClock


ApiFactory = Callable[..., Awaitable[Api]]


@pytest.fixture
async def api(db_schema: str, tmp_path: Path) -> AsyncIterator[ApiFactory]:
    """Build apps against the test schema; the factory takes Settings overrides."""
    stack = AsyncExitStack()
    engine = _schema_engine(_database_url(), db_schema)
    word_file = tmp_path / "signup_word"
    word_file.write_text(SIGNUP_WORD, encoding="utf-8")

    async def factory(
        *,
        peer: str = "203.0.113.7",
        real_pool: bool = False,
        raise_app_exceptions: bool = True,
        **overrides: object,
    ) -> Api:
        values: dict[str, object] = {
            "database_url": SecretStr("postgresql+asyncpg://unused/unused"),
            "initial_signup_word_file": word_file,
            "cookie_secure": False,
        }
        values.update(overrides)
        clock = FakeClock()
        app = create_app(
            Settings(**values),  # pyright: ignore[reportArgumentType]
            engine=engine,
            clock=clock,
            checker_pool=None if real_pool else _ColdPool(),
        )
        transport = httpx.ASGITransport(
            app=app, client=(peer, 50000), raise_app_exceptions=raise_app_exceptions
        )
        client = httpx.AsyncClient(transport=transport, base_url="http://test")
        await stack.enter_async_context(client)
        await stack.enter_async_context(app.router.lifespan_context(app))
        return Api(client=client, app=app, clock=clock)

    try:
        yield factory
    finally:
        await stack.aclose()
        async with engine.begin() as conn:
            await conn.execute(
                text("TRUNCATE players, app_settings, admin_sessions, admin_audit CASCADE")
            )
        await engine.dispose()
