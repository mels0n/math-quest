"""Repository for auth failures and lockouts, keyed by (player, device key, ip)."""

import uuid
from datetime import datetime

from sqlalchemy import delete, func, select, text
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncSession

from mathquest.entities.models import AuthFailure, Lockout, Player, RecoveryFailure
from mathquest.shared.errors import Locked

ANY_DEVICE = "*"
LOCK_NOT_AVAILABLE = "55P03"
LOCK_TIMEOUT = "3s"
LOCK_RETRY_AFTER_S = 5


async def lock_player(db: AsyncSession, player_id: uuid.UUID) -> None:
    """Serialize auth attempts for one player until the transaction ends.

    Takes a non-key row lock so inserts into child tables are not blocked. Waiting
    longer than the lock timeout raises Locked.
    """
    await db.execute(text(f"SET LOCAL lock_timeout = '{LOCK_TIMEOUT}'"))
    try:
        await db.execute(
            select(Player.id).where(Player.id == player_id).with_for_update(key_share=True)
        )
    except DBAPIError as exc:
        if getattr(exc.orig, "sqlstate", None) != LOCK_NOT_AVAILABLE:
            raise
        await db.rollback()
        raise Locked(LOCK_RETRY_AFTER_S) from None


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


async def record_recovery_failure(db: AsyncSession, player_id: uuid.UUID, at: datetime) -> None:
    db.add(RecoveryFailure(player_id=player_id, at=at))
    await db.flush()


async def count_recovery_failures_since(
    db: AsyncSession, player_id: uuid.UUID, since: datetime
) -> int:
    """Failed recovery guesses for the player from any address since a moment."""
    result = await db.execute(
        select(func.count())
        .select_from(RecoveryFailure)
        .where(RecoveryFailure.player_id == player_id, RecoveryFailure.at > since)
    )
    return result.scalar_one()


async def clear_recovery_failures(
    db: AsyncSession, player_id: uuid.UUID, before: datetime | None = None
) -> None:
    """Drop the player's recovery failures, or only those older than `before`."""
    query = delete(RecoveryFailure).where(RecoveryFailure.player_id == player_id)
    if before is not None:
        query = query.where(RecoveryFailure.at < before)
    await db.execute(query)
