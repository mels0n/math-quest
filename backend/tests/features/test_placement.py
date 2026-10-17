# pyright: reportUnknownMemberType=false, reportUnknownArgumentType=false, reportUnknownVariableType=false
"""Placement service tests, against the real content pack and an in-process checker."""

import asyncio
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from mathquest.engine.catalog import load_catalog
from mathquest.engine.checker.bounded import CheckerPool
from mathquest.engine.checker.check import CheckResult, Verdict, check
from mathquest.engine.mastery import SkillState
from mathquest.engine.placement import MAX_QUESTIONS, spine
from mathquest.engine.types import Problem
from mathquest.entities import mastery, players, problems
from mathquest.entities.placement import PlacementRun
from mathquest.entities.problems import ProblemInstance
from mathquest.features.placement import FREE_RETRIES, service
from mathquest.features.placement.schema import PlacementDoneOut, PlacementStepOut
from mathquest.shared.errors import Conflict, Invalid, NotFound
from tests.conftest import _database_url  # pyright: ignore[reportPrivateUsage]

CATALOG = load_catalog(Path(__file__).resolve().parents[2] / "content", "k8-core")
ANCHORS = spine(CATALOG.graph)


class _SyncPool(CheckerPool):
    async def check(self, problem: Problem, latex: str) -> CheckResult:
        return check(problem, latex)


POOL = _SyncPool()


async def _player(db: AsyncSession) -> uuid.UUID:
    row = await players.add(
        db,
        nickname=f"Placer{uuid.uuid4().hex[:6]}",
        pin_hash=None,
        picture_hash=None,
        recovery_hash="x",
    )
    return row.id


async def _start(db: AsyncSession, pid: uuid.UUID, hint: str | None = None) -> PlacementStepOut:
    return await service.start(db, CATALOG, pid, hint, expose_answers=True)


async def _answer(
    db: AsyncSession, pid: uuid.UUID, step: PlacementStepOut, latex: str
) -> PlacementStepOut | PlacementDoneOut:
    """Answer the open probe; for a choice probe, ``latex`` is only read as right or wrong."""
    right_choice = step.problem.dev_answer_choice
    if right_choice is not None:
        picked = right_choice if latex == _right(step) else (right_choice + 1) % 3
        return await service.answer(
            db, POOL, CATALOG, pid, step.placement_id, step.problem.problem_id, None,
            choice=picked, expose_answers=True,
        )  # fmt: skip
    return await service.answer(
        db, POOL, CATALOG, pid, step.placement_id, step.problem.problem_id, latex,
        expose_answers=True,
    )  # fmt: skip


def _right(step: PlacementStepOut) -> str:
    if step.problem.dev_answer_choice is not None:
        return f"choice:{step.problem.dev_answer_choice}"
    assert step.problem.dev_answer_latex is not None
    return step.problem.dev_answer_latex


async def _round(
    db: AsyncSession, pid: uuid.UUID, level: int, hint: str | None = None
) -> tuple[PlacementDoneOut, list[str]]:
    """Play a whole round as a learner who knows exactly the anchors up to ``level``."""
    step = await _start(db, pid, hint)
    asked: list[str] = []
    for _ in range(MAX_QUESTIONS + 1):
        asked.append(step.problem.skill_id)
        knows = ANCHORS.index(step.problem.skill_id) <= level
        out = await _answer(db, pid, step, _right(step) if knows else "99999")
        if isinstance(out, PlacementDoneOut):
            return out, asked
        step = out
    raise AssertionError("placement did not finish")


async def _age_rounds(db: AsyncSession, pid: uuid.UUID) -> None:
    """Move the player's finished rounds past the retake cooldown."""
    await db.execute(
        update(PlacementRun)
        .where(PlacementRun.player_id == pid, PlacementRun.finished_at.is_not(None))
        .values(finished_at=PlacementRun.finished_at - service.RETAKE_COOLDOWN)
    )
    await db.commit()


async def _state(db: AsyncSession, pid: uuid.UUID, skill_id: str) -> str | None:
    row = await mastery.get(db, pid, skill_id)
    if row is None:
        return None
    await db.refresh(row)
    return row.state


async def test_the_grade_hint_picks_the_first_question(db: AsyncSession) -> None:
    pid = await _player(db)
    assert (await _start(db, pid)).problem.skill_id == "add_within_20"
    assert (await _start(db, pid, "K")).problem.skill_id == "count_to_10"
    assert (await _start(db, pid, "1")).problem.skill_id == "add_within_20"
    assert (await _start(db, pid, "3")).problem.skill_id == "add_2digit_regroup"
    first = await _start(db, pid, "8")
    assert first.problem.skill_id == "add_fractions_unlike"
    assert first.question == 1
    assert first.max_questions == MAX_QUESTIONS
    assert first.retry is None
    assert first.problem.hint_levels == 0
    assert first.problem.has_lesson is False
    assert first.problem.prompt


async def test_answers_stay_hidden_without_the_dev_setting(db: AsyncSession) -> None:
    pid = await _player(db)
    step = await service.start(db, CATALOG, pid, None)
    assert step.problem.dev_answer_latex is None
    assert step.problem.dev_answer_choice is None


async def test_a_round_marks_provisional_mastery(db: AsyncSession) -> None:
    pid = await _player(db)
    before = datetime.now(UTC)
    done, asked = await _round(db, pid, level=4)

    assert done.frontier == ["add_2digit_regroup"]
    assert len(asked) <= MAX_QUESTIONS
    # Every anchor up to the frontier, each with everything it builds on.
    expected = {sid for anchor in ANCHORS[:5] for sid in {anchor} | CATALOG.graph.ancestors(anchor)}
    assert {
        "count_to_10",
        "add_within_20",
        "compare_numbers_100",
        "place_value_tens_ones",
    } <= expected
    assert set(done.provisional) == expected
    assert [r.id for r in done.revealed_regions] == ["number_meadows", "operation_canyon"]
    assert done.revealed_regions[0].name == "Number Meadows"
    for sid in expected:
        row = await mastery.get(db, pid, sid)
        assert row is not None
        await db.refresh(row)
        assert row.state == SkillState.PROVISIONAL
        assert row.attempts == 0
        assert row.review_due_at is not None
        assert before + timedelta(hours=23) < row.review_due_at < before + timedelta(days=2)
    assert await _state(db, pid, "add_fractions_unlike") is None
    # Placement problems are not play problems: nothing solved, no session history.
    assert await problems.count_solved(db, pid) == 0
    count = await db.scalar(
        select(func.count()).select_from(ProblemInstance).where(ProblemInstance.player_id == pid)
    )
    assert count == 0
    run = await db.get(PlacementRun, done.placement_id)
    assert run is not None
    await db.refresh(run)
    assert run.finished_at is not None
    assert run.result is not None and run.result["frontier"] == ["add_2digit_regroup"]


async def test_nothing_passed_reveals_only_the_first_region(db: AsyncSession) -> None:
    pid = await _player(db)
    done, asked = await _round(db, pid, level=-1)
    assert done.frontier == []
    assert done.provisional == []
    assert [r.id for r in done.revealed_regions] == ["number_meadows"]
    assert len(asked) < MAX_QUESTIONS
    assert await mastery.list_for_player(db, pid) == []


async def test_unreadable_answers_are_asked_again_then_count(db: AsyncSession) -> None:
    pid = await _player(db)
    step = await _start(db, pid)
    for _ in range(FREE_RETRIES):
        again = await _answer(db, pid, step, r"\frac{")
        assert isinstance(again, PlacementStepOut)
        assert again.retry is Verdict.UNREADABLE
        assert again.problem.problem_id == step.problem.problem_id
        assert again.question == 1
    counted = await _answer(db, pid, step, r"\frac{")
    assert isinstance(counted, PlacementStepOut)
    assert counted.retry is None
    assert counted.question == 2
    # Counted as a miss: the probe moved down.
    assert counted.problem.skill_id == "count_to_10"


async def test_a_stale_problem_returns_the_round_as_it_is(db: AsyncSession) -> None:
    pid = await _player(db)
    first = await _start(db, pid)
    second = await _answer(db, pid, first, _right(first))
    assert isinstance(second, PlacementStepOut)
    again = await _answer(db, pid, first, "99999")
    assert isinstance(again, PlacementStepOut)
    assert again.problem.problem_id == second.problem.problem_id
    assert again.question == 2


async def test_unknown_problem_or_someone_elses_round_is_not_found(db: AsyncSession) -> None:
    owner = await _player(db)
    other = await _player(db)
    step = await _start(db, owner)
    with pytest.raises(NotFound):
        await _answer(db, other, step, _right(step))
    with pytest.raises(NotFound):
        await service.answer(
            db, POOL, CATALOG, owner, step.placement_id, uuid.uuid4(), "1"
        )  # fmt: skip
    with pytest.raises(NotFound):
        await service.answer(db, POOL, CATALOG, owner, uuid.uuid4(), uuid.uuid4(), "1")


async def test_a_choice_for_a_typed_problem_is_invalid(db: AsyncSession) -> None:
    pid = await _player(db)
    step = await _start(db, pid)
    with pytest.raises(Invalid):
        await service.answer(
            db, POOL, CATALOG, pid, step.placement_id, step.problem.problem_id, None, choice=0
        )


async def test_starting_again_ends_the_open_round(db: AsyncSession) -> None:
    pid = await _player(db)
    old = await _start(db, pid)
    new = await _start(db, pid)
    assert new.placement_id != old.placement_id
    with pytest.raises(Conflict):
        await _answer(db, pid, old, _right(old))


async def test_a_finished_round_answers_with_its_outcome(db: AsyncSession) -> None:
    pid = await _player(db)
    step = await _start(db, pid, "K")
    while True:
        out = await _answer(db, pid, step, "99999")
        if isinstance(out, PlacementDoneOut):
            break
        step = out
    repeat = await _answer(db, pid, step, "99999")
    assert repeat == out


async def test_retake_resets_unconfirmed_marks_and_keeps_real_mastery(db: AsyncSession) -> None:
    pid = await _player(db)
    first, _ = await _round(db, pid, level=5)
    assert "add_fractions_unlike" in first.provisional
    # One skill was confirmed since (mastered), one was played and is learning.
    confirmed = await mastery.lock(db, pid, "add_within_10", 0.0)
    confirmed.state = SkillState.MASTERED
    confirmed.placed = True
    confirmed.attempts = 1
    learning = await mastery.lock(db, pid, "sub_within_10", 0.0)
    learning.state = SkillState.LEARNING
    learning.attempts = 2
    await db.commit()
    await _age_rounds(db, pid)

    second, _ = await _round(db, pid, level=1)

    assert second.frontier == ["add_within_10"]
    assert "add_within_10" not in second.provisional
    assert await _state(db, pid, "add_within_10") == SkillState.MASTERED
    assert await _state(db, pid, "sub_within_10") == SkillState.LEARNING
    assert await _state(db, pid, "add_fractions_unlike") is None
    assert await _state(db, pid, "equivalent_fractions") is None
    assert await _state(db, pid, "add_within_20") is None


async def test_a_learning_skill_is_never_marked(db: AsyncSession) -> None:
    """Real progress is not hidden behind a provisional mark, on a first round or a retake."""
    pid = await _player(db)
    row = await mastery.lock(db, pid, "add_within_10", 0.0)
    row.rating = 1.25
    row.attempts = 3
    row.recent = [[1, 1], [0, 2], [1, 2]]
    await db.commit()
    row.state = "learning"
    await db.commit()
    done, _ = await _round(db, pid, level=2)
    after = await mastery.get(db, pid, "add_within_10")
    assert after is not None
    await db.refresh(after)
    assert after.state == SkillState.LEARNING
    assert (after.rating, after.attempts) == (1.25, 3)
    assert "add_within_10" not in done.provisional
    assert "add_within_20" in done.provisional


async def test_a_finished_round_cannot_be_retaken_straight_away(db: AsyncSession) -> None:
    pid = await _player(db)
    await _round(db, pid, level=1)
    with pytest.raises(Conflict) as err:
        await _start(db, pid)
    assert err.value.code == "retake_too_soon"
    await _age_rounds(db, pid)
    assert (await _start(db, pid)).question == 1


async def test_two_starts_at_once_leave_one_round_open(db_schema: str) -> None:
    engine = create_async_engine(
        _database_url(),
        pool_size=5,
        connect_args={"server_settings": {"search_path": db_schema}},
    )
    factory = async_sessionmaker(engine, expire_on_commit=False)
    try:
        async with factory() as setup:
            pid = await _player(setup)
            await setup.commit()

        async def start_one() -> None:
            async with factory() as session:
                await service.start(session, CATALOG, pid, None)

        await asyncio.gather(start_one(), start_one(), start_one())
        async with factory() as check:
            open_rounds = await check.scalar(
                select(func.count())
                .select_from(PlacementRun)
                .where(PlacementRun.player_id == pid, PlacementRun.finished_at.is_(None))
            )
        assert open_rounds == 1
    finally:
        await engine.dispose()
