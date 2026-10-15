"""Placement runs: one row per placement round a player starts.

``state`` holds the round's anchors, its first probe and every probe issued so far (its
problem id, skill, tier, seed, variant and template, free retries used and whether it
was answered correctly), so the round can be replayed. Placement problems live only
here, never in problem_instances, so they cannot count as solved problems, change
ratings or appear in a session's history.
"""

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, ForeignKey, Text, func, select, update
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Mapped, mapped_column

from mathquest.entities.models import Player
from mathquest.shared.db import Base


class PlacementRun(Base):
    __tablename__ = "placement_runs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    player_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("players.id", ondelete="CASCADE"), index=True
    )
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    grade_hint: Mapped[str | None] = mapped_column(Text, nullable=True)
    state: Mapped[dict[str, Any]] = mapped_column(JSONB)
    result: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)


async def add_run(
    db: AsyncSession,
    *,
    player_id: uuid.UUID,
    started_at: datetime,
    grade_hint: str | None,
    state: dict[str, Any],
) -> PlacementRun:
    row = PlacementRun(
        player_id=player_id, started_at=started_at, grade_hint=grade_hint, state=state
    )
    db.add(row)
    await db.flush()
    return row


async def lock_player(db: AsyncSession, player_id: uuid.UUID) -> None:
    """Lock the player's row, so two rounds cannot start at once for one player."""
    await db.execute(select(Player.id).where(Player.id == player_id).with_for_update())


async def last_completed_at(db: AsyncSession, player_id: uuid.UUID) -> datetime | None:
    """When the player's newest completed round (one with an outcome) finished."""
    return await db.scalar(
        select(func.max(PlacementRun.finished_at)).where(
            PlacementRun.player_id == player_id, PlacementRun.result.is_not(None)
        )
    )


async def abandon_open(db: AsyncSession, player_id: uuid.UUID, at: datetime) -> None:
    """End the player's unfinished runs without a result. Call `lock_player` first in
    the same transaction, so a concurrent start waits and cannot leave two runs open."""
    await db.execute(
        update(PlacementRun)
        .where(PlacementRun.player_id == player_id, PlacementRun.finished_at.is_(None))
        .values(finished_at=at)
    )


async def get_run(db: AsyncSession, player_id: uuid.UUID, run_id: uuid.UUID) -> PlacementRun | None:
    result = await db.execute(
        select(PlacementRun).where(PlacementRun.id == run_id, PlacementRun.player_id == player_id)
    )
    return result.scalar_one_or_none()


async def lock_run(
    db: AsyncSession, player_id: uuid.UUID, run_id: uuid.UUID
) -> PlacementRun | None:
    result = await db.execute(
        select(PlacementRun)
        .where(PlacementRun.id == run_id, PlacementRun.player_id == player_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    return result.scalar_one_or_none()
