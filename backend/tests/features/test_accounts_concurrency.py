"""Parallel attempts on real, committed connections (the rolled-back fixture cannot race)."""

import asyncio
import uuid

import pytest
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from mathquest.entities import lockouts, players
from mathquest.entities.models import Player
from mathquest.features.accounts import service
from mathquest.shared.errors import Locked, Unauthorized
from tests.conftest import _database_url  # pyright: ignore[reportPrivateUsage]


async def test_parallel_wrong_logins_lock_after_exactly_five(db_schema: str) -> None:
    engine = create_async_engine(
        _database_url(),
        pool_size=25,
        connect_args={"server_settings": {"search_path": db_schema}},
    )
    factory = async_sessionmaker(engine, expire_on_commit=False)
    nickname = f"Race{uuid.uuid4().hex[:8]}"
    try:
        async with factory() as setup:
            await players.add(
                setup,
                nickname=nickname,
                pin_hash=await service._hash("1234"),  # pyright: ignore[reportPrivateUsage]
                picture_hash=None,
                recovery_hash=await service._hash("apple"),  # pyright: ignore[reportPrivateUsage]
            )
            await setup.commit()

        async def attempt() -> BaseException | None:
            async with factory() as session:
                try:
                    await service.login(
                        session, nickname=nickname, pin="0000", device_key="d", ip="10.9.9.9"
                    )
                except (Unauthorized, Locked) as exc:
                    return exc
            return None

        outcomes = await asyncio.gather(*(attempt() for _ in range(20)), return_exceptions=True)
        assert all(isinstance(o, Unauthorized | Locked) for o in outcomes), outcomes
        assert sum(isinstance(o, Unauthorized) for o in outcomes) == 5
        assert sum(isinstance(o, Locked) for o in outcomes) == 15
    finally:
        async with factory() as cleanup:
            await cleanup.execute(delete(Player).where(Player.nickname == nickname))
            await cleanup.commit()
        await engine.dispose()


async def test_lock_wait_timeout_maps_to_locked(db_schema: str) -> None:
    engine = create_async_engine(
        _database_url(),
        pool_size=5,
        connect_args={"server_settings": {"search_path": db_schema}},
    )
    factory = async_sessionmaker(engine, expire_on_commit=False)
    nickname = f"Hold{uuid.uuid4().hex[:8]}"
    try:
        async with factory() as setup:
            player = await players.add(
                setup,
                nickname=nickname,
                pin_hash=await service._hash("1234"),  # pyright: ignore[reportPrivateUsage]
                picture_hash=None,
                recovery_hash=await service._hash("apple"),  # pyright: ignore[reportPrivateUsage]
            )
            await setup.commit()
        async with factory() as holder:
            await lockouts.lock_player(holder, player.id)
            async with factory() as waiter:
                with pytest.raises(Locked) as err:
                    await service.login(
                        waiter, nickname=nickname, pin="0000", device_key="d", ip="10.9.9.8"
                    )
            assert err.value.retry_after_s == 5
            await holder.rollback()
    finally:
        async with factory() as cleanup:
            await cleanup.execute(delete(Player).where(Player.nickname == nickname))
            await cleanup.commit()
        await engine.dispose()
