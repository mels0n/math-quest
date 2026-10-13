"""Shared fixtures. DB tests run in a uniquely named Postgres schema built by Alembic."""

import asyncio
import os
import uuid
from collections.abc import AsyncIterator, Iterator
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, create_async_engine
from sqlalchemy.pool import NullPool

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
