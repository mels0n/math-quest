"""Lessons a player has seen, and the practice problems ("try it") lessons hand out."""

import uuid
from datetime import datetime

from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, Integer, Text, select
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Mapped, mapped_column

from mathquest.shared.db import Base


class LessonSeen(Base):
    __tablename__ = "lessons_seen"

    player_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("players.id", ondelete="CASCADE"), primary_key=True
    )
    skill_id: Mapped[str] = mapped_column(Text, primary_key=True)
    seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class LessonTry(Base):
    """A lesson's practice problem: stored like an issued problem, but kept apart from
    problem_instances so it can never change mastery or the solved count."""

    __tablename__ = "lesson_tries"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    player_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("players.id", ondelete="CASCADE"), index=True
    )
    skill_id: Mapped[str] = mapped_column(Text)
    tier: Mapped[int] = mapped_column(Integer)
    seed: Mapped[int] = mapped_column(BigInteger)
    issued_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    misses: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    answered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    correct: Mapped[bool | None] = mapped_column(Boolean, nullable=True)


async def has_seen(db: AsyncSession, player_id: uuid.UUID, skill_id: str) -> bool:
    return await db.get(LessonSeen, (player_id, skill_id)) is not None


async def mark_seen(db: AsyncSession, player_id: uuid.UUID, skill_id: str, at: datetime) -> None:
    """Record the lesson as seen; a second call keeps the first time."""
    await db.execute(
        pg_insert(LessonSeen)
        .values(player_id=player_id, skill_id=skill_id, seen_at=at)
        .on_conflict_do_nothing(index_elements=["player_id", "skill_id"])
    )


async def add_try(
    db: AsyncSession,
    *,
    player_id: uuid.UUID,
    skill_id: str,
    tier: int,
    seed: int,
    issued_at: datetime,
) -> LessonTry:
    row = LessonTry(
        player_id=player_id, skill_id=skill_id, tier=tier, seed=seed, issued_at=issued_at
    )
    db.add(row)
    await db.flush()
    return row


async def get_try(db: AsyncSession, player_id: uuid.UUID, try_id: uuid.UUID) -> LessonTry | None:
    result = await db.execute(
        select(LessonTry).where(LessonTry.id == try_id, LessonTry.player_id == player_id)
    )
    return result.scalar_one_or_none()


async def lock_try(db: AsyncSession, player_id: uuid.UUID, try_id: uuid.UUID) -> LessonTry | None:
    result = await db.execute(
        select(LessonTry)
        .where(LessonTry.id == try_id, LessonTry.player_id == player_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    return result.scalar_one_or_none()
