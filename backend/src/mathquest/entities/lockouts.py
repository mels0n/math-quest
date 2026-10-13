"""Repository for auth failures and lockouts, keyed by (player, device key, ip)."""

import uuid
from datetime import datetime

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from mathquest.entities.models import AuthFailure, Lockout


async def active_lockout_until(
    db: AsyncSession, player_id: uuid.UUID, device_key: str, ip: str, now: datetime
) -> datetime | None:
    result = await db.execute(
        select(Lockout.until).where(
            Lockout.player_id == player_id,
            Lockout.device_key == device_key,
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
    db: AsyncSession, player_id: uuid.UUID, device_key: str, ip: str, since: datetime
) -> int:
    result = await db.execute(
        select(func.count())
        .select_from(AuthFailure)
        .where(
            AuthFailure.player_id == player_id,
            AuthFailure.device_key == device_key,
            AuthFailure.ip == ip,
            AuthFailure.at > since,
        )
    )
    return result.scalar_one()


async def clear_lockout(db: AsyncSession, player_id: uuid.UUID, device_key: str, ip: str) -> None:
    await db.execute(
        delete(Lockout).where(
            Lockout.player_id == player_id, Lockout.device_key == device_key, Lockout.ip == ip
        )
    )


async def set_lockout(
    db: AsyncSession, player_id: uuid.UUID, device_key: str, ip: str, until: datetime
) -> None:
    await clear_lockout(db, player_id, device_key, ip)
    db.add(Lockout(player_id=player_id, device_key=device_key, ip=ip, until=until))
    await db.flush()


async def clear_failures(db: AsyncSession, player_id: uuid.UUID, device_key: str, ip: str) -> None:
    await db.execute(
        delete(AuthFailure).where(
            AuthFailure.player_id == player_id,
            AuthFailure.device_key == device_key,
            AuthFailure.ip == ip,
        )
    )
