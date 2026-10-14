"""Per-player skill mastery rows."""

import uuid
from collections.abc import Sequence
from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Index, Integer, Text, func, select
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


async def list_for_player(db: AsyncSession, player_id: uuid.UUID) -> Sequence[SkillMastery]:
    result = await db.execute(select(SkillMastery).where(SkillMastery.player_id == player_id))
    return result.scalars().all()


async def due_reviews(db: AsyncSession, player_id: uuid.UUID, now: datetime) -> Sequence[str]:
    """Mastered skills whose review date has passed, oldest review first."""
    result = await db.execute(
        select(SkillMastery.skill_id)
        .where(
            SkillMastery.player_id == player_id,
            SkillMastery.state == "mastered",
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
