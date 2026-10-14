"""Repository for players."""

import uuid
from datetime import datetime

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from mathquest.entities.models import Device, Player


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


def _like_escape(text: str) -> str:
    return text.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


async def list_page(
    db: AsyncSession, *, query: str | None, offset: int, limit: int
) -> list[tuple[Player, datetime | None]]:
    """Players newest first, hidden ones included, with the latest device activity.

    `query` matches anywhere in the lowercase nickname; LIKE wildcards in it are literal.
    """
    last_seen = (
        select(func.max(Device.last_seen))
        .where(Device.player_id == Player.id)
        .correlate(Player)
        .scalar_subquery()
    )
    stmt = select(Player, last_seen)
    if query:
        pattern = f"%{_like_escape(query.lower())}%"
        stmt = stmt.where(Player.nickname_key.like(pattern, escape="\\"))
    stmt = stmt.order_by(Player.created_at.desc(), Player.id).offset(offset).limit(limit)
    result = await db.execute(stmt)
    return [(player, seen) for player, seen in result.all()]


async def set_hidden(db: AsyncSession, player: Player, hidden: bool) -> None:
    player.hidden = hidden
    await db.flush()


async def rename(db: AsyncSession, player: Player, nickname: str) -> None:
    player.nickname = nickname
    player.nickname_key = nickname_key(nickname)
    await db.flush()


async def delete_player(db: AsyncSession, player_id: uuid.UUID) -> None:
    """Remove the player; every dependent table cascades from the foreign key."""
    await db.execute(delete(Player).where(Player.id == player_id))
