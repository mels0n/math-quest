"""E2E backend control: prepare/drop an isolated Postgres schema and serve the API against it.

usage: backend_ctl.py prepare|serve|drop <schema>
Reads TEST_DATABASE_URL (asyncpg URL). `serve` also reads E2E_WORD_FILE.
"""

import asyncio
import os
import sys
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine
from sqlalchemy.pool import NullPool

BACKEND_DIR = Path(__file__).resolve().parents[2] / "backend"


def _engine(url: str, schema: str | None, *, pooled: bool = False) -> AsyncEngine:
    connect_args: dict[str, object] = {}
    if schema is not None:
        connect_args["server_settings"] = {"search_path": schema}
    kwargs: dict[str, object] = {} if pooled else {"poolclass": NullPool}
    return create_async_engine(url, connect_args=connect_args, hide_parameters=True, **kwargs)  # pyright: ignore[reportArgumentType]


async def _exec(url: str, statement: str) -> None:
    engine = _engine(url, None)
    try:
        async with engine.begin() as conn:
            await conn.execute(text(statement))
    finally:
        await engine.dispose()


def prepare(url: str, schema: str) -> None:
    asyncio.run(_exec(url, f'CREATE SCHEMA "{schema}"'))
    cfg = Config(str(BACKEND_DIR / "alembic.ini"))
    cfg.set_main_option("script_location", str(BACKEND_DIR / "migrations"))
    cfg.attributes["url"] = url
    cfg.attributes["search_path"] = schema
    command.upgrade(cfg, "head")


def drop(url: str, schema: str) -> None:
    asyncio.run(_exec(url, f'DROP SCHEMA IF EXISTS "{schema}" CASCADE'))


def serve(url: str, schema: str) -> None:
    import uvicorn
    from pydantic import SecretStr

    from mathquest.app.main import create_app
    from mathquest.shared.config import Settings

    settings = Settings(
        database_url=SecretStr(url),
        initial_signup_word_file=Path(os.environ["E2E_WORD_FILE"]),
        cookie_secure=False,
        dev_expose_answers=True,
    )
    app = create_app(settings, engine=_engine(url, schema, pooled=True))
    uvicorn.run(app, host="127.0.0.1", port=8000, log_level="warning")


def main() -> None:
    action, schema = sys.argv[1], sys.argv[2]
    if not schema.startswith("e2e_"):
        raise SystemExit("schema name must start with e2e_")
    url = os.environ.get("TEST_DATABASE_URL")
    if not url:
        raise SystemExit("TEST_DATABASE_URL is not set")
    {"prepare": prepare, "drop": drop, "serve": serve}[action](url, schema)


if __name__ == "__main__":
    main()
