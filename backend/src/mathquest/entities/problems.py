"""Play sessions, issued problem instances and answer attempts."""

import uuid
from datetime import datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    Text,
    func,
    select,
    update,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Mapped, mapped_column

from mathquest.shared.db import Base


class PlaySession(Base):
    __tablename__ = "play_sessions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    player_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("players.id", ondelete="CASCADE")
    )
    mode: Mapped[str] = mapped_column(Text)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    problem_count: Mapped[int] = mapped_column(Integer, default=0, server_default="0")


class ProblemInstance(Base):
    __tablename__ = "problem_instances"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    session_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("play_sessions.id", ondelete="CASCADE"), index=True
    )
    player_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("players.id", ondelete="CASCADE"), index=True
    )
    skill_id: Mapped[str] = mapped_column(Text)
    tier: Mapped[int] = mapped_column(Integer)
    seed: Mapped[int] = mapped_column(BigInteger)
    difficulty: Mapped[float] = mapped_column(Float)
    issued_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    answered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    correct: Mapped[bool | None] = mapped_column(Boolean, nullable=True)


class Attempt(Base):
    __tablename__ = "attempts"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    problem_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("problem_instances.id", ondelete="CASCADE"), index=True
    )
    player_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("players.id", ondelete="CASCADE"), index=True
    )
    latex: Mapped[str] = mapped_column(Text)
    verdict: Mapped[str] = mapped_column(Text)
    misconception: Mapped[str | None] = mapped_column(Text, nullable=True)
    seconds: Mapped[float] = mapped_column(Float)
    at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


async def add_session(
    db: AsyncSession, *, player_id: uuid.UUID, mode: str, started_at: datetime
) -> PlaySession:
    row = PlaySession(player_id=player_id, mode=mode, started_at=started_at)
    db.add(row)
    await db.flush()
    return row


async def lock_session(
    db: AsyncSession, player_id: uuid.UUID, session_id: uuid.UUID
) -> PlaySession | None:
    result = await db.execute(
        select(PlaySession)
        .where(PlaySession.id == session_id, PlaySession.player_id == player_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    return result.scalar_one_or_none()


async def add_problem(
    db: AsyncSession,
    *,
    session_id: uuid.UUID,
    player_id: uuid.UUID,
    skill_id: str,
    tier: int,
    seed: int,
    difficulty: float,
    issued_at: datetime,
) -> ProblemInstance:
    row = ProblemInstance(
        session_id=session_id,
        player_id=player_id,
        skill_id=skill_id,
        tier=tier,
        seed=seed,
        difficulty=difficulty,
        issued_at=issued_at,
    )
    db.add(row)
    await db.flush()
    return row


async def lock_problem(
    db: AsyncSession, player_id: uuid.UUID, problem_id: uuid.UUID
) -> ProblemInstance | None:
    result = await db.execute(
        select(ProblemInstance)
        .where(ProblemInstance.id == problem_id, ProblemInstance.player_id == player_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    return result.scalar_one_or_none()


async def add_attempt(
    db: AsyncSession,
    *,
    problem_id: uuid.UUID,
    player_id: uuid.UUID,
    latex: str,
    verdict: str,
    misconception: str | None,
    seconds: float,
    at: datetime,
) -> Attempt:
    row = Attempt(
        problem_id=problem_id,
        player_id=player_id,
        latex=latex,
        verdict=verdict,
        misconception=misconception,
        seconds=seconds,
        at=at,
    )
    db.add(row)
    await db.flush()
    return row


async def attempts_for(db: AsyncSession, problem_id: uuid.UUID) -> list[Attempt]:
    """Every attempt on the problem, oldest first."""
    result = await db.execute(
        select(Attempt).where(Attempt.problem_id == problem_id).order_by(Attempt.id)
    )
    return list(result.scalars().all())


async def close_open(db: AsyncSession, session_id: uuid.UUID, at: datetime) -> None:
    """Close the session's unanswered problems: answered_at set, correct left NULL."""
    await db.execute(
        update(ProblemInstance)
        .where(ProblemInstance.session_id == session_id, ProblemInstance.answered_at.is_(None))
        .values(answered_at=at)
    )


async def count_solved(db: AsyncSession, player_id: uuid.UUID) -> int:
    """How many problems the player has solved (correct is true), across all sessions."""
    total = await db.scalar(
        select(func.count())
        .select_from(ProblemInstance)
        .where(ProblemInstance.player_id == player_id, ProblemInstance.correct.is_(True))
    )
    return int(total or 0)
