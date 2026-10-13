"""Alembic environment: async engine, URL from the caller or from boot settings."""

import asyncio

from alembic import context
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import create_async_engine

from mathquest.entities import models  # noqa: F401  (registers tables on the metadata)
from mathquest.shared.config import get_settings
from mathquest.shared.db import Base

config = context.config
target_metadata = Base.metadata


def _url() -> str:
    url = config.attributes.get("url")
    if isinstance(url, str):
        return url
    settings_url = get_settings().database_url
    if settings_url is None:
        raise RuntimeError("database url is not configured")
    return settings_url


def _do_run(connection: Connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()


async def _run_online() -> None:
    connect_args: dict[str, object] = {}
    search_path = config.attributes.get("search_path")
    if isinstance(search_path, str):
        connect_args["server_settings"] = {"search_path": search_path}
    engine = create_async_engine(_url(), connect_args=connect_args)
    try:
        async with engine.connect() as connection:
            await connection.run_sync(_do_run)
    finally:
        await engine.dispose()


asyncio.run(_run_online())
