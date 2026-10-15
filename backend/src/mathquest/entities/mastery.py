"""Per-player skill mastery rows."""

import uuid
from collections.abc import Mapping, Sequence
from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    Text,
    delete,
    func,
    select,
    update,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Mapped, mapped_column

from mathquest.shared.db import Base


class SkillMastery(Base):
    __tablename__ = "skill_mastery"
    __table_args__ = (
        Index("ix_skill_mastery_player_id_review_due_at", "player_id", "review_due_at"),
    )

    player_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("players.id", ondelete="CASCADE"), primary_key=True
    )
    skill_id: Mapped[str] = mapped_column(Text, primary_key=True)
    rating: Mapped[float] = mapped_column(Float, server_default="0")
    attempts: Mapped[int] = mapped_column(Integer, server_default="0")
    recent: Mapped[list[list[int]]] = mapped_column(JSONB, server_default="[]")
    state: Mapped[str] = mapped_column(Text, server_default="learning")
    review_interval_days: Mapped[int | None] = mapped_column(Integer, nullable=True)
    review_due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    placed: Mapped[bool] = mapped_column(Boolean, server_default="false")
    """Mastered because placement marked it and its first review confirmed it, not yet
    by the rating rule; a correct answer keeps it mastered until the rating catches up."""


PROVISIONAL = "provisional"
MASTERED = "mastered"
LEARNING = "learning"
COUNTS_AS_MASTERED = (MASTERED, PROVISIONAL)


async def list_for_player(db: AsyncSession, player_id: uuid.UUID) -> Sequence[SkillMastery]:
    result = await db.execute(select(SkillMastery).where(SkillMastery.player_id == player_id))
    return result.scalars().all()


async def due_reviews(db: AsyncSession, player_id: uuid.UUID, now: datetime) -> Sequence[str]:
    """Mastered and provisional skills whose review date has passed, oldest review first."""
    result = await db.execute(
        select(SkillMastery.skill_id)
        .where(
            SkillMastery.player_id == player_id,
            SkillMastery.state.in_(COUNTS_AS_MASTERED),
            SkillMastery.review_due_at <= now,
        )
        .order_by(SkillMastery.review_due_at, SkillMastery.skill_id)
    )
    return result.scalars().all()


async def get(db: AsyncSession, player_id: uuid.UUID, skill_id: str) -> SkillMastery | None:
    return await db.get(SkillMastery, (player_id, skill_id))


async def lock(
    db: AsyncSession, player_id: uuid.UUID, skill_id: str, initial_rating: float
) -> SkillMastery:
    """Create the row (at `initial_rating`) if absent, then return it locked for update."""
    await db.execute(
        pg_insert(SkillMastery)
        .values(player_id=player_id, skill_id=skill_id, rating=initial_rating)
        .on_conflict_do_nothing(index_elements=["player_id", "skill_id"])
    )
    result = await db.execute(
        select(SkillMastery)
        .where(SkillMastery.player_id == player_id, SkillMastery.skill_id == skill_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    return result.scalar_one()


async def mark_provisional(
    db: AsyncSession,
    player_id: uuid.UUID,
    initial_ratings: Mapping[str, float],
    review_due_at: datetime,
    now: datetime,
) -> list[str]:
    """Mark each skill provisionally mastered, due for review at ``review_due_at``.

    A missing row is created at its initial rating. A mastered skill is left alone, so
    real mastery is never replaced; a learning one keeps its rating and attempts.
    Returns the skills that were marked."""
    marked: list[str] = []
    for skill_id, rating in initial_ratings.items():
        row = await lock(db, player_id, skill_id, rating)
        if row.state == MASTERED:
            continue
        row.state = PROVISIONAL
        row.placed = False
        row.review_interval_days = None
        row.review_due_at = review_due_at
        row.updated_at = now
        marked.append(skill_id)
    await db.flush()
    return marked


async def revert_provisional(db: AsyncSession, player_id: uuid.UUID) -> None:
    """Undo provisional marks that no review has confirmed: a never-played skill loses
    its row, one played before placement goes back to learning."""
    await db.execute(
        delete(SkillMastery).where(
            SkillMastery.player_id == player_id,
            SkillMastery.state == PROVISIONAL,
            SkillMastery.attempts == 0,
        )
    )
    await db.execute(
        update(SkillMastery)
        .where(SkillMastery.player_id == player_id, SkillMastery.state == PROVISIONAL)
        .values(state=LEARNING, review_interval_days=None, review_due_at=None)
    )
