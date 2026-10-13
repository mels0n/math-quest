"""Repository for device tokens. Only the SHA-256 of a token is ever stored."""

import hashlib
import uuid
from datetime import datetime

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from mathquest.entities.models import Device, Player


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


async def add(db: AsyncSession, *, player_id: uuid.UUID, token: str) -> Device:
    device = Device(player_id=player_id, token_hash=hash_token(token))
    db.add(device)
    await db.flush()
    return device


async def player_for_token(db: AsyncSession, token: str, now: datetime) -> Player | None:
    """The visible player owning an unrevoked device token; touches last_seen."""
    result = await db.execute(
        select(Device, Player)
        .join(Player, Player.id == Device.player_id)
        .where(Device.token_hash == hash_token(token), Device.revoked.is_(False))
    )
    row = result.first()
    if row is None:
        return None
    device, player = row
    if player.hidden:
        return None
    device.last_seen = now
    await db.flush()
    return player


async def revoke_all(db: AsyncSession, player_id: uuid.UUID) -> None:
    await db.execute(update(Device).where(Device.player_id == player_id).values(revoked=True))
