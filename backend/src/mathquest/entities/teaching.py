"""Explanations shown on play problems, and problems a learner stayed stuck on."""

import uuid
from collections.abc import Sequence
from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, Integer, Text, func, select
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Mapped, mapped_column

from mathquest.shared.db import Base


class ExplanationView(Base):
    """One "explain it another way" shown on a play problem: which approach (its index
    in the skill's explanations file) and in which session."""

    __tablename__ = "explanation_views"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    player_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("players.id", ondelete="CASCADE"), index=True
    )
    session_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("play_sessions.id", ondelete="CASCADE"), index=True
    )
    problem_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("problem_instances.id", ondelete="CASCADE")
    )
    skill_id: Mapped[str] = mapped_column(Text)
    approach: Mapped[int] = mapped_column(Integer)
    shown_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class StuckEvent(Base):
    """A problem scored wrong after every explanation of its skill was shown in the
    session. ``player_id`` is kept for the warm-up rule and for deleting a player's data;
    it is never exported."""

    __tablename__ = "stuck_events"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    player_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("players.id", ondelete="CASCADE"), index=True
    )
    problem_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("problem_instances.id", ondelete="CASCADE"),
        unique=True,
    )
    skill_id: Mapped[str] = mapped_column(Text)
    generator: Mapped[str] = mapped_column(Text)
    tier: Mapped[int] = mapped_column(Integer)
    seed: Mapped[int] = mapped_column(BigInteger)
    wrong_answers: Mapped[list[str]] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)


async def add_view(
    db: AsyncSession,
    *,
    player_id: uuid.UUID,
    session_id: uuid.UUID,
    problem_id: uuid.UUID,
    skill_id: str,
    approach: int,
    shown_at: datetime,
) -> None:
    db.add(
        ExplanationView(
            player_id=player_id,
            session_id=session_id,
            problem_id=problem_id,
            skill_id=skill_id,
            approach=approach,
            shown_at=shown_at,
        )
    )
    await db.flush()


async def count_views(db: AsyncSession, player_id: uuid.UUID, skill_id: str) -> int:
    """How many explanations of the skill the player has been shown, ever."""
    total = await db.scalar(
        select(func.count())
        .select_from(ExplanationView)
        .where(ExplanationView.player_id == player_id, ExplanationView.skill_id == skill_id)
    )
    return int(total or 0)


async def approaches_shown(db: AsyncSession, session_id: uuid.UUID, skill_id: str) -> set[int]:
    """The approaches of the skill shown in the session."""
    result = await db.execute(
        select(ExplanationView.approach)
        .where(ExplanationView.session_id == session_id, ExplanationView.skill_id == skill_id)
        .distinct()
    )
    return set(result.scalars().all())


async def add_stuck(
    db: AsyncSession,
    *,
    player_id: uuid.UUID,
    problem_id: uuid.UUID,
    skill_id: str,
    generator: str,
    tier: int,
    seed: int,
    wrong_answers: list[str],
    created_at: datetime,
) -> None:
    db.add(
        StuckEvent(
            player_id=player_id,
            problem_id=problem_id,
            skill_id=skill_id,
            generator=generator,
            tier=tier,
            seed=seed,
            wrong_answers=wrong_answers,
            created_at=created_at,
        )
    )
    await db.flush()


async def stuck_since(db: AsyncSession, since: datetime | None) -> Sequence[StuckEvent]:
    """Stuck events, oldest first; only those at or after ``since`` when given."""
    query = select(StuckEvent).order_by(StuckEvent.created_at, StuckEvent.id)
    if since is not None:
        query = query.where(StuckEvent.created_at >= since)
    result = await db.execute(query)
    return result.scalars().all()
