# pyright: reportUnknownMemberType=false, reportUnknownArgumentType=false, reportUnknownVariableType=false, reportPrivateUsage=false
"""Practice sessions, the skill list, and how sessions end with a summary."""

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from mathquest.engine.mastery import SkillState
from mathquest.engine.scheduler import SESSION_PROBLEMS
from mathquest.entities import mastery
from mathquest.entities.problems import PlaySession, ProblemInstance, RevisitEvent
from mathquest.features.play import service
from mathquest.features.play.schema import LessonDueOut, ProblemOut, SummaryOut
from mathquest.shared.errors import Conflict, Invalid, NotFound
from tests.features.test_play import (
    CATALOG,
    _issue,
    _mark_provisional,
    _player,
    _right,
    _row,
    _submit,
    _wrong,
)


async def _next(
    db: AsyncSession, pid: uuid.UUID, session_id: uuid.UUID, *, summary: bool = True
) -> ProblemOut | LessonDueOut | SummaryOut:
    return await service.next_problem(
        db, CATALOG, pid, session_id, expose_answers=True, offer_summary=summary
    )


async def _problem(db: AsyncSession, pid: uuid.UUID, session_id: uuid.UUID) -> ProblemOut:
    out = await _next(db, pid, session_id)
    assert isinstance(out, ProblemOut)
    return out


async def _answer_right(db: AsyncSession, pid: uuid.UUID, out: ProblemOut) -> None:
    assert out.dev_answer_latex is not None
    result = await _submit(db, pid, out.problem_id, out.dev_answer_latex)
    assert result.solved


async def _set_row(db: AsyncSession, pid: uuid.UUID, skill_id: str, **values: object) -> None:
    await mastery.lock(db, pid, skill_id, service._start_rating(CATALOG, skill_id))
    await db.execute(
        update(mastery.SkillMastery)
        .where(mastery.SkillMastery.player_id == pid, mastery.SkillMastery.skill_id == skill_id)
        .values(**values)
    )
    await db.commit()


# Practice


async def test_practice_on_a_chosen_skill_keeps_to_it(db: AsyncSession) -> None:
    pid = await _player(db)
    session = await service.start_practice(db, CATALOG, pid, skill_id="sub_within_10")

    assert session.mode == "practice"
    assert [(f.skill_id, f.name) for f in session.focus] == [("sub_within_10", "Subtract from 10")]
    for _ in range(SESSION_PROBLEMS + 2):
        out = await _problem(db, pid, session.session_id)
        assert out.skill_id == "sub_within_10"
        await _answer_right(db, pid, out)


async def test_practice_refuses_a_locked_or_unknown_skill(db: AsyncSession) -> None:
    pid = await _player(db)
    with pytest.raises(Conflict) as locked:
        await service.start_practice(db, CATALOG, pid, skill_id="add_2digit_regroup")
    assert locked.value.code == "skill_locked"
    with pytest.raises(NotFound):
        await service.start_practice(db, CATALOG, pid, skill_id="no_such_skill")
    with pytest.raises(Invalid):
        await service.start_practice(db, CATALOG, pid)
    with pytest.raises(Invalid):
        await service.start_practice(db, CATALOG, pid, skill_id="add_within_10", weak_spots=True)


async def test_practice_accepts_learning_provisional_and_mastered_skills(db: AsyncSession) -> None:
    pid = await _player(db)
    await _mark_provisional(db, pid, "add_within_10")
    await _set_row(db, pid, "sub_within_10", state="learning", attempts=2)
    await _set_row(
        db, pid, "place_value_tens_ones", state="mastered", attempts=8, review_interval_days=3
    )
    for skill_id in ("add_within_10", "sub_within_10", "place_value_tens_ones", "add_within_20"):
        session = await service.start_practice(db, CATALOG, pid, skill_id=skill_id)
        assert [f.skill_id for f in session.focus] == [skill_id]


async def test_practicing_a_provisional_skill_confirms_it_by_the_same_rule(
    db: AsyncSession,
) -> None:
    pid = await _player(db)
    await _mark_provisional(db, pid, "add_within_10")
    session = await service.start_practice(db, CATALOG, pid, skill_id="add_within_10")
    out = await _problem(db, pid, session.session_id)
    inst = await db.get(ProblemInstance, out.problem_id)
    assert inst is not None and inst.variant == "bare" and inst.tier >= 1
    await _answer_right(db, pid, out)
    assert (await _row(db, pid, "add_within_10")).state == "mastered"


async def test_weak_spots_are_the_three_weakest_learning_skills_then_due_reviews(
    db: AsyncSession,
) -> None:
    pid = await _player(db)
    now = datetime.now(UTC)
    for skill_id in ("add_within_10", "sub_within_10", "place_value_tens_ones"):
        await _set_row(
            db, pid, skill_id, state="mastered", attempts=9, review_due_at=now + timedelta(days=3)
        )
    await _set_row(db, pid, "place_value_tens_ones", review_due_at=now - timedelta(hours=1))
    # Four learning skills; add_within_20 is the strongest and is left out.
    for skill_id, offset in (
        ("add_within_20", 3.0),
        ("sub_within_20", -2.0),
        ("add_2digit_no_regroup", 0.0),
        ("equivalent_fractions", -1.0),
    ):
        start = service._start_rating(CATALOG, skill_id)
        await _set_row(db, pid, skill_id, state="learning", attempts=3, rating=start + offset)

    session = await service.start_practice(db, CATALOG, pid, weak_spots=True)

    assert [f.skill_id for f in session.focus] == [
        "sub_within_20",
        "equivalent_fractions",
        "add_2digit_no_regroup",
        "place_value_tens_ones",
    ]
    seen = set()
    for _ in range(9):
        out = await _problem(db, pid, session.session_id)
        seen.add(out.skill_id)
        await _answer_right(db, pid, out)
    assert seen <= {f.skill_id for f in session.focus}


async def test_no_weak_spots_is_a_conflict(db: AsyncSession) -> None:
    pid = await _player(db)
    with pytest.raises(Conflict) as err:
        await service.start_practice(db, CATALOG, pid, weak_spots=True)
    assert err.value.code == "no_weak_spots"


async def test_practice_is_untimed(db: AsyncSession) -> None:
    assert CATALOG.graph.skills["add_within_10"].fluency
    ratings: dict[str, float] = {}
    for mode in ("adventure", "practice"):
        pid = await _player(db)
        if mode == "adventure":
            session = await service.start_session(db, pid, "adventure")
        else:
            session = await service.start_practice(db, CATALOG, pid, skill_id="add_within_10")
        inst = await _issue(db, pid, session.session_id)
        inst.issued_at = datetime.now(UTC) - timedelta(seconds=30)
        await db.commit()
        await _submit(db, pid, inst.id, _right(inst))
        ratings[mode] = (await _row(db, pid, "add_within_10")).rating
    assert ratings["practice"] > ratings["adventure"]


async def _revisits(db: AsyncSession, pid: uuid.UUID) -> list[str]:
    rows = await db.execute(select(RevisitEvent.skill_id).where(RevisitEvent.player_id == pid))
    return list(rows.scalars().all())


async def test_practising_a_mastered_skill_records_one_revisit_per_session(
    db: AsyncSession,
) -> None:
    pid = await _player(db)
    later = datetime.now(UTC) + timedelta(days=3)
    top = service._top_tier(CATALOG, "add_within_10")
    await _set_row(
        db,
        pid,
        "add_within_10",
        state="mastered",
        attempts=9,
        review_due_at=later,
        review_interval_days=3,
        rating=service._top_difficulty(CATALOG, "add_within_10") + 1.5,
        recent=[[1, top]] * 6,
    )
    await _set_row(db, pid, "sub_within_10", state="learning", attempts=2)

    adventure = await service.start_session(db, pid, "adventure")
    inst = await _issue(db, pid, adventure.session_id, tier=top)
    await _submit(db, pid, inst.id, _right(inst))
    assert await _revisits(db, pid) == []

    for _ in range(2):
        session = await service.start_practice(db, CATALOG, pid, skill_id="add_within_10")
        for _ in range(2):
            inst = await _issue(db, pid, session.session_id, tier=top)
            await _submit(db, pid, inst.id, _right(inst))
    learning = await service.start_practice(db, CATALOG, pid, skill_id="sub_within_10")
    inst = await _issue(db, pid, learning.session_id, "sub_within_10")
    await _submit(db, pid, inst.id, _right(inst))

    assert await _revisits(db, pid) == ["add_within_10", "add_within_10"]


async def test_a_skill_mastered_or_confirmed_during_practice_is_not_a_revisit(
    db: AsyncSession,
) -> None:
    pid = await _player(db)
    skill_id = "add_within_10"
    top = service._top_tier(CATALOG, skill_id)
    await _set_row(
        db,
        pid,
        skill_id,
        state="learning",
        attempts=6,
        rating=service._top_difficulty(CATALOG, skill_id) + 1.5,
        recent=[[1, top]] * 5,
    )
    await _mark_provisional(db, pid, "sub_within_10")
    learning = await service.start_practice(db, CATALOG, pid, skill_id=skill_id)
    for _ in range(3):
        inst = await _issue(db, pid, learning.session_id, skill_id, tier=top)
        await _submit(db, pid, inst.id, _right(inst))
    assert (await _row(db, pid, skill_id)).state == "mastered"
    provisional = await service.start_practice(db, CATALOG, pid, skill_id="sub_within_10")
    for _ in range(3):
        inst = await _issue(db, pid, provisional.session_id, "sub_within_10", tier=1)
        await _submit(db, pid, inst.id, _right(inst))
    assert (await _row(db, pid, "sub_within_10")).state == "mastered"

    assert await _revisits(db, pid) == []


# Skill list


async def test_the_skill_list_shows_each_state_in_map_order(db: AsyncSession) -> None:
    pid = await _player(db)
    await _mark_provisional(db, pid, "add_within_10")
    await _set_row(db, pid, "sub_within_10", state="learning", attempts=2)

    out = await service.list_skills(db, CATALOG, pid)

    assert [r.id for r in out.regions] == [
        "number_meadows",
        "operation_canyon",
        "fraction_forest",
    ]
    states = {s.skill_id: s.state for s in out.skills}
    assert states["add_within_10"] is SkillState.PROVISIONAL
    assert states["sub_within_10"] is SkillState.LEARNING
    assert states["add_within_20"] is SkillState.READY
    assert states["place_value_tens_ones"] is SkillState.READY
    assert states["add_2digit_regroup"] is SkillState.LOCKED
    regions = [s.region for s in out.skills]
    assert regions == sorted(regions, key=[r.id for r in out.regions].index)
    lessons = {s.skill_id for s in out.skills if s.has_lesson}
    assert lessons == set(CATALOG.pack.lessons)


async def test_a_provisional_skill_past_its_review_reads_as_due(db: AsyncSession) -> None:
    pid = await _player(db)
    await _mark_provisional(db, pid, "add_within_10", due_in=timedelta(hours=-1))
    out = await service.list_skills(db, CATALOG, pid)
    states = {s.skill_id: s.state for s in out.skills}
    assert states["add_within_10"] is SkillState.REVIEW_DUE
    session = await service.start_practice(db, CATALOG, pid, weak_spots=True)
    assert [f.skill_id for f in session.focus] == ["add_within_10"]


# Session length and summary


async def test_an_adventure_ends_after_twelve_problems_with_a_summary(db: AsyncSession) -> None:
    pid = await _player(db)
    session = await service.start_session(db, pid, "adventure")
    first = None
    last: ProblemOut | None = None
    for index in range(SESSION_PROBLEMS):
        out = await _problem(db, pid, session.session_id)
        if first is None:
            first = out.problem_id
        if index in (3, 7):
            inst = await db.get(ProblemInstance, out.problem_id)
            assert inst is not None
            for k in range(3):
                await _submit(db, pid, out.problem_id, _wrong(inst, k))
        elif index != SESSION_PROBLEMS - 1:
            await _answer_right(db, pid, out)
        else:
            last = out  # left open: the summary closes it
    await db.execute(
        update(ProblemInstance)
        .where(ProblemInstance.id == first)
        .values(issued_at=datetime.now(UTC) - timedelta(seconds=95))
    )
    await db.commit()

    summary = await _next(db, pid, session.session_id)

    assert isinstance(summary, SummaryOut)
    assert summary.mode == "adventure"
    assert summary.problems_scored == SESSION_PROBLEMS - 1
    assert summary.problems_solved == SESSION_PROBLEMS - 1 - 2
    assert summary.accuracy == pytest.approx(9 / 11)
    assert 90 <= summary.seconds <= 120
    assert summary.skills_practiced
    assert summary.newly_mastered == []
    assert last is not None
    with pytest.raises(Conflict) as closed:
        await _submit(db, pid, last.problem_id, "1")
    assert closed.value.code == "problem_closed"
    with pytest.raises(Conflict) as ended:
        await _next(db, pid, session.session_id)
    assert ended.value.code == "session_ended"
    row = await db.get(PlaySession, session.session_id)
    assert row is not None and row.ended_at is not None


async def test_an_older_client_keeps_getting_problems_past_twelve(db: AsyncSession) -> None:
    pid = await _player(db)
    session = await service.start_session(db, pid, "adventure")
    for _ in range(SESSION_PROBLEMS + 1):
        out = await _next(db, pid, session.session_id, summary=False)
        assert isinstance(out, ProblemOut)


async def test_a_practice_session_has_no_set_length(db: AsyncSession) -> None:
    pid = await _player(db)
    session = await service.start_practice(db, CATALOG, pid, skill_id="add_within_10")
    for _ in range(SESSION_PROBLEMS + 1):
        await _problem(db, pid, session.session_id)


async def test_ending_early_returns_the_summary_and_closes_the_session(db: AsyncSession) -> None:
    pid = await _player(db)
    session = await service.start_practice(db, CATALOG, pid, skill_id="add_within_10")
    await _answer_right(db, pid, await _problem(db, pid, session.session_id))
    open_problem = await _problem(db, pid, session.session_id)

    summary = await service.end_session(db, CATALOG, pid, session.session_id)

    assert summary.mode == "practice"
    assert [s.skill_id for s in summary.skills_practiced] == ["add_within_10"]
    assert (summary.problems_solved, summary.problems_scored) == (1, 1)
    assert summary.accuracy == 1.0
    with pytest.raises(Conflict):
        await _submit(db, pid, open_problem.problem_id, "1")
    assert await service.end_session(db, CATALOG, pid, session.session_id) == summary
    with pytest.raises(Conflict):
        await _next(db, pid, session.session_id)


async def test_an_empty_session_summary(db: AsyncSession) -> None:
    pid = await _player(db)
    session = await service.start_session(db, pid, "adventure")
    summary = await service.end_session(db, CATALOG, pid, session.session_id)
    assert summary.skills_practiced == []
    assert (summary.problems_scored, summary.accuracy, summary.seconds) == (0, None, 0)


async def test_someone_elses_session_cannot_be_ended(db: AsyncSession) -> None:
    owner = await _player(db)
    other = await _player(db)
    session = await service.start_session(db, owner, "adventure")
    with pytest.raises(NotFound):
        await service.end_session(db, CATALOG, other, session.session_id)


async def test_the_summary_lists_skills_newly_mastered_in_the_session(db: AsyncSession) -> None:
    pid = await _player(db)
    skill_id = "add_within_10"
    top = service._top_tier(CATALOG, skill_id)
    top_difficulty = service._top_difficulty(CATALOG, skill_id)
    await _set_row(
        db,
        pid,
        skill_id,
        state="learning",
        attempts=6,
        rating=top_difficulty + 1.5,
        recent=[[1, top]] * 5,
    )
    await _mark_provisional(db, pid, "sub_within_10")
    session = await service.start_session(db, pid, "adventure")
    inst = await _issue(db, pid, session.session_id, skill_id, tier=top)
    out = await _submit(db, pid, inst.id, _right(inst))
    assert out.mastery.state is SkillState.MASTERED
    # Confirming a provisional skill is not new mastery.
    review = await _issue(db, pid, session.session_id, "sub_within_10", tier=1)
    assert (await _submit(db, pid, review.id, _right(review))).mastery.state is SkillState.MASTERED

    summary = await service.end_session(db, CATALOG, pid, session.session_id)

    assert [s.skill_id for s in summary.newly_mastered] == [skill_id]
    assert [s.skill_id for s in summary.skills_practiced] == [skill_id, "sub_within_10"]
    flagged = await db.scalar(
        select(func.count())
        .select_from(ProblemInstance)
        .where(ProblemInstance.session_id == session.session_id, ProblemInstance.newly_mastered)
    )
    assert flagged == 1
