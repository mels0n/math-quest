"""Play sessions, issued problem instances, answer attempts and revisits of mastered skills."""

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
    UniqueConstraint,
    func,
    select,
    update,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Mapped, mapped_column

from mathquest.entities.teaching import StuckEvent
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
    focus: Mapped[list[str] | None] = mapped_column(JSONB, nullable=True)
    """A practice session's skills, in the order chosen; None for an adventure."""
    mastered_at_start: Mapped[list[str] | None] = mapped_column(JSONB, nullable=True)
    """A practice session's skills that were mastered (not provisional) when it started:
    the only ones whose practice there counts as a revisit. None for an adventure."""


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
    variant: Mapped[str] = mapped_column(Text, nullable=False, server_default="bare")
    template_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    difficulty: Mapped[float] = mapped_column(Float)
    issued_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    answered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    correct: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    hints_used: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    """Hint levels viewed on this problem (0 to 3)."""
    warmup_for: Mapped[str | None] = mapped_column(Text, nullable=True)
    """The skill this problem warms up for, when it is a warm-up on a prerequisite."""
    newly_mastered: Mapped[bool] = mapped_column(Boolean, server_default="false")
    """Scoring this problem made its skill mastered from learning."""


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


class RevisitEvent(Base):
    """A skill that was already mastered when a practice session started, practiced
    again there: at most one per session and skill, at its first scored problem."""

    __tablename__ = "revisit_events"
    __table_args__ = (UniqueConstraint("session_id", "skill_id"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    player_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("players.id", ondelete="CASCADE"), index=True
    )
    session_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("play_sessions.id", ondelete="CASCADE")
    )
    skill_id: Mapped[str] = mapped_column(Text)
    at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


async def add_session(
    db: AsyncSession,
    *,
    player_id: uuid.UUID,
    mode: str,
    started_at: datetime,
    focus: list[str] | None = None,
    mastered_at_start: list[str] | None = None,
) -> PlaySession:
    row = PlaySession(
        player_id=player_id,
        mode=mode,
        started_at=started_at,
        focus=focus,
        mastered_at_start=mastered_at_start,
    )
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
    variant: str = "bare",
    template_id: str | None = None,
    warmup_for: str | None = None,
) -> ProblemInstance:
    row = ProblemInstance(
        session_id=session_id,
        player_id=player_id,
        skill_id=skill_id,
        tier=tier,
        seed=seed,
        variant=variant,
        template_id=template_id,
        difficulty=difficulty,
        issued_at=issued_at,
        warmup_for=warmup_for,
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


HISTORY_LIMIT = 50
"""The most problems of one session read back for the scheduler: enough for a run, the
reviews inside it, a warm-up and the misses that trigger one."""


async def session_history(
    db: AsyncSession, session_id: uuid.UUID
) -> list[tuple[str, bool | None, bool, str | None]]:
    """The session's problems, oldest first, as (skill_id, correct, stuck, warmup_for);
    ``stuck`` is whether a stuck event was recorded for the problem. At most the newest
    HISTORY_LIMIT."""
    stuck = select(StuckEvent.id).where(StuckEvent.problem_id == ProblemInstance.id).exists()
    result = await db.execute(
        select(
            ProblemInstance.skill_id,
            ProblemInstance.correct,
            stuck,
            ProblemInstance.warmup_for,
        )
        .where(ProblemInstance.session_id == session_id)
        .order_by(ProblemInstance.issued_at.desc(), ProblemInstance.id)
        .limit(HISTORY_LIMIT)
    )
    rows = [(r[0], r[1], bool(r[2]), r[3]) for r in result.all()]
    return list(reversed(rows))


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


async def get_session(db: AsyncSession, session_id: uuid.UUID) -> PlaySession:
    """An existing session, read without a lock."""
    row = await db.get(PlaySession, session_id)
    assert row is not None
    return row


async def add_revisit(
    db: AsyncSession,
    *,
    player_id: uuid.UUID,
    session_id: uuid.UUID,
    skill_id: str,
    at: datetime,
) -> None:
    """Record a revisit; a second one for the same session and skill is ignored."""
    await db.execute(
        pg_insert(RevisitEvent)
        .values(player_id=player_id, session_id=session_id, skill_id=skill_id, at=at)
        .on_conflict_do_nothing(index_elements=["session_id", "skill_id"])
    )


async def session_problems(
    db: AsyncSession, session_id: uuid.UUID
) -> list[tuple[str, bool | None, bool, datetime]]:
    """Every problem of the session, oldest first, as (skill_id, correct, newly_mastered,
    issued_at)."""
    result = await db.execute(
        select(
            ProblemInstance.skill_id,
            ProblemInstance.correct,
            ProblemInstance.newly_mastered,
            ProblemInstance.issued_at,
        )
        .where(ProblemInstance.session_id == session_id)
        .order_by(ProblemInstance.issued_at, ProblemInstance.id)
    )
    return [(r[0], r[1], bool(r[2]), r[3]) for r in result.all()]


async def last_answer_at(db: AsyncSession, session_id: uuid.UUID) -> datetime | None:
    """When the session's newest answer attempt arrived; None before the first."""
    return await db.scalar(
        select(func.max(Attempt.at))
        .join(ProblemInstance, ProblemInstance.id == Attempt.problem_id)
        .where(ProblemInstance.session_id == session_id)
    )
