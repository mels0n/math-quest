"""Repository for auth failures and lockouts, keyed by (player, device key, ip)."""

import uuid
from datetime import datetime

from sqlalchemy import delete, func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from mathquest.entities.models import AuthFailure, Lockout, Player

ANY_DEVICE = "*"


async def lock_player(db: AsyncSession, player_id: uuid.UUID) -> None:
    """Serialize auth attempts for one player until the transaction ends."""
    await db.execute(select(Player.id).where(Player.id == player_id).with_for_update())


async def active_lockout_until(
    db: AsyncSession, player_id: uuid.UUID, device_key: str, ip: str, now: datetime
) -> datetime | None:
    """Latest end of any lock covering this device on this ip, or of the ip-wide lock."""
    result = await db.execute(
        select(func.max(Lockout.until)).where(
            Lockout.player_id == player_id,
            Lockout.device_key.in_((device_key, ANY_DEVICE)),
            Lockout.ip == ip,
            Lockout.until > now,
        )
    )
    return result.scalar_one_or_none()


async def record_failure(
    db: AsyncSession, player_id: uuid.UUID, device_key: str, ip: str, at: datetime
) -> None:
    db.add(AuthFailure(player_id=player_id, device_key=device_key, ip=ip, at=at))
    await db.flush()


async def count_failures_since(
    db: AsyncSession, player_id: uuid.UUID, device_key: str | None, ip: str, since: datetime
) -> int:
    """Failures for the (player, ip) since a moment; one device key, or all when None."""
    query = (
        select(func.count())
        .select_from(AuthFailure)
        .where(AuthFailure.player_id == player_id, AuthFailure.ip == ip, AuthFailure.at > since)
    )
    if device_key is not None:
        query = query.where(AuthFailure.device_key == device_key)
    return (await db.execute(query)).scalar_one()


async def delete_failures_before(db: AsyncSession, player_id: uuid.UUID, before: datetime) -> None:
    await db.execute(
        delete(AuthFailure).where(AuthFailure.player_id == player_id, AuthFailure.at < before)
    )


async def set_lockout(
    db: AsyncSession, player_id: uuid.UUID, device_key: str, ip: str, until: datetime
) -> None:
    stmt = insert(Lockout).values(player_id=player_id, device_key=device_key, ip=ip, until=until)
    await db.execute(
        stmt.on_conflict_do_update(
            index_elements=["player_id", "device_key", "ip"], set_={"until": stmt.excluded.until}
        )
    )


async def clear_failures(db: AsyncSession, player_id: uuid.UUID, device_key: str, ip: str) -> None:
    await db.execute(
        delete(AuthFailure).where(
            AuthFailure.player_id == player_id,
            AuthFailure.device_key == device_key,
            AuthFailure.ip == ip,
        )
    )
