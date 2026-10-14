"""The engine built by shared.db keeps bound parameters out of error text."""

import uuid

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from mathquest.entities import players
from mathquest.shared.db import create_engine, create_session_factory
from tests.conftest import _database_url  # pyright: ignore[reportPrivateUsage]


async def test_failed_statement_error_hides_parameters(db_schema: str) -> None:
    url = _database_url()
    engine = create_engine(url)
    secret_hash = f"$argon2id$secret-{uuid.uuid4().hex}"
    nickname = f"Dup{uuid.uuid4().hex[:8]}"
    factory = create_session_factory(engine)
    try:
        async with factory() as session:
            await session.connection()
            await session.execute(text(f'SET search_path TO "{db_schema}"'))
            await players.add(
                session, nickname=nickname, pin_hash=None, picture_hash=None, recovery_hash="x"
            )
            with pytest.raises(IntegrityError) as err:
                await players.add(
                    session,
                    nickname=nickname,
                    pin_hash=secret_hash,
                    picture_hash=None,
                    recovery_hash="x",
                )
            await session.rollback()
        message = str(err.value)
        assert "[parameters:" not in message
        assert secret_hash not in message
        assert secret_hash not in repr(err.value)
    finally:
        await engine.dispose()
