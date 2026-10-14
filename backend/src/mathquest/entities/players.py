"""Repository for players."""

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from mathquest.entities.models import Player


def nickname_key(nickname: str) -> str:
    return nickname.lower()


async def get_by_nickname(db: AsyncSession, nickname: str) -> Player | None:
    result = await db.execute(select(Player).where(Player.nickname_key == nickname_key(nickname)))
    return result.scalar_one_or_none()


async def get_by_id(db: AsyncSession, player_id: uuid.UUID) -> Player | None:
    return await db.get(Player, player_id)


async def add(
    db: AsyncSession,
    *,
    nickname: str,
    pin_hash: str | None,
    picture_hash: str | None,
    recovery_hash: str,
) -> Player:
    player = Player(
        nickname=nickname,
        nickname_key=nickname_key(nickname),
        pin_hash=pin_hash,
        picture_hash=picture_hash,
        recovery_hash=recovery_hash,
    )
    db.add(player)
    await db.flush()
    return player
