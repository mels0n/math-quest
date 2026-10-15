# pyright: reportUnknownMemberType=false, reportUnknownArgumentType=false, reportUnknownVariableType=false
"""Play service tests.

They call the service directly. Answers are checked by `_SyncPool`, which runs the
engine's synchronous `check` in-process instead of the worker-process pool.
"""

import asyncio
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
import sympy
from sqlalchemy import delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from mathquest.engine.checker.bounded import CheckerPool
from mathquest.engine.checker.check import CheckResult, Verdict, check
from mathquest.engine.generators import get_generator
from mathquest.engine.mastery import SkillState, choose_tier, is_mastered
from mathquest.engine.scheduler import RUN_LENGTH
from mathquest.engine.skillgraph import SkillGraph, load_pack
from mathquest.engine.types import Problem
from mathquest.entities import mastery, players, problems
from mathquest.entities.mastery import SkillMastery
from mathquest.entities.models import Player
from mathquest.entities.problems import Attempt, PlaySession, ProblemInstance, add_problem
from mathquest.features.play import service
from mathquest.features.play.schema import AnswerOut
from mathquest.shared.errors import Conflict, NotFound
from tests.conftest import _database_url  # pyright: ignore[reportPrivateUsage]

PACK = Path(__file__).resolve().parents[2] / "content" / "packs" / "k8-core"
GRAPH = load_pack(PACK)
SEED = 7


class _SyncPool(CheckerPool):
    async def check(self, problem: Problem, latex: str) -> CheckResult:
        return check(problem, latex)


POOL = _SyncPool()


async def _player(db: AsyncSession, name: str = "Tester") -> uuid.UUID:
    row = await players.add(
        db,
        nickname=f"{name}{uuid.uuid4().hex[:6]}",
        pin_hash=None,
        picture_hash=None,
        recovery_hash="x",
    )
    return row.id


async def _issue(
    db: AsyncSession,
    player_id: uuid.UUID,
    session_id: uuid.UUID,
    skill_id: str = "add_within_10",
    tier: int = 0,
    seed: int = SEED,
) -> ProblemInstance:
    problem = get_generator(skill_id).generate(seed, tier)
    return await add_problem(
        db,
        session_id=session_id,
        player_id=player_id,
        skill_id=skill_id,
        tier=tier,
        seed=seed,
        difficulty=problem.difficulty,
        issued_at=datetime.now(UTC),
    )


def _answer(inst: ProblemInstance) -> sympy.Expr:
    return get_generator(inst.skill_id).generate(inst.seed, inst.tier).answer


def _right(inst: ProblemInstance) -> str:
    return sympy.latex(_answer(inst))


def _wrong(inst: ProblemInstance, k: int = 0) -> str:
    return sympy.latex(_answer(inst) + 1000 + k)


async def _row(db: AsyncSession, player_id: uuid.UUID, skill_id: str) -> SkillMastery:
    row = await mastery.get(db, player_id, skill_id)
    assert row is not None
    await db.refresh(row)
    return row


async def _submit(
    db: AsyncSession, player_id: uuid.UUID, problem_id: uuid.UUID, latex: str
) -> AnswerOut:
    return await service.submit_answer(db, POOL, GRAPH, player_id, problem_id, latex)


async def test_correct_answer_updates_mastery_once(db: AsyncSession) -> None:
    pid = await _player(db)
    session = await service.start_session(db, pid, "adventure")
    inst = await _issue(db, pid, session.session_id)

    out = await _submit(db, pid, inst.id, _right(inst))

    assert out.verdict is Verdict.CORRECT
    assert out.solved is True
    assert out.attempts_left == 3
    assert out.answer_latex == _right(inst)
    assert out.mastery.skill_id == "add_within_10"
    assert out.mastery.state is SkillState.LEARNING
    row = await _row(db, pid, "add_within_10")
    assert row.attempts == 1
    assert row.rating > service._start_rating("add_within_10")  # pyright: ignore[reportPrivateUsage]
    assert row.recent == [[1, 0]]


async def test_double_submit_idempotent(db: AsyncSession) -> None:
    pid = await _player(db)
    session = await service.start_session(db, pid, "adventure")
    inst = await _issue(db, pid, session.session_id)

    first = await _submit(db, pid, inst.id, _right(inst))
    rating = (await _row(db, pid, "add_within_10")).rating
    second = await _submit(db, pid, inst.id, _right(inst))
    third = await _submit(db, pid, inst.id, _wrong(inst))

    assert second == first
    assert third == first
    assert (first.total_solved, second.total_solved, third.total_solved) == (1, 1, 1)
    row = await _row(db, pid, "add_within_10")
    assert row.attempts == 1
    assert row.rating == rating
    stored = await db.scalar(select(func.count()).select_from(Attempt))
    assert stored == 1


async def test_wrong_form_does_not_consume_attempt(db: AsyncSession) -> None:
    pid = await _player(db)
    session = await service.start_session(db, pid, "adventure")
    inst = await _issue(db, pid, session.session_id, "add_fractions_unlike", tier=0)
    answer = _answer(inst)
    assert isinstance(answer, sympy.Rational) and answer.q != 1
    unreduced = rf"\frac{{{2 * answer.p}}}{{{2 * answer.q}}}"

    out = await _submit(db, pid, inst.id, unreduced)
    assert out.verdict is Verdict.WRONG_FORM
    assert out.attempts_left == 3
    assert out.solved is False
    assert out.answer_latex is None
    assert await mastery.get(db, pid, "add_fractions_unlike") is None

    unreadable = await _submit(db, pid, inst.id, r"\frac{")
    assert unreadable.verdict is Verdict.UNREADABLE
    assert unreadable.attempts_left == 3

    ok = await _submit(db, pid, inst.id, _right(inst))
    assert ok.verdict is Verdict.CORRECT
    assert ok.attempts_left == 3
    row = await _row(db, pid, "add_fractions_unlike")
    assert row.attempts == 1
    assert row.recent == [[1, 0]]


async def test_three_misses_reveals_answer_and_scores_incorrect(db: AsyncSession) -> None:
    pid = await _player(db)
    session = await service.start_session(db, pid, "adventure")
    inst = await _issue(db, pid, session.session_id)

    first = await _submit(db, pid, inst.id, _wrong(inst, 0))
    second = await _submit(db, pid, inst.id, _wrong(inst, 1))
    assert (first.attempts_left, second.attempts_left) == (2, 1)
    assert first.answer_latex is None and second.answer_latex is None
    assert await mastery.get(db, pid, "add_within_10") is None

    third = await _submit(db, pid, inst.id, _wrong(inst, 2))
    assert third.verdict is Verdict.INCORRECT
    assert third.solved is False
    assert third.attempts_left == 0
    assert third.answer_latex == _right(inst)
    row = await _row(db, pid, "add_within_10")
    assert row.attempts == 1
    assert row.rating < service._start_rating("add_within_10")  # pyright: ignore[reportPrivateUsage]
    assert row.recent == [[0, 0]]

    again = await _submit(db, pid, inst.id, _right(inst))
    assert again == third
    assert (await _row(db, pid, "add_within_10")).attempts == 1


async def test_wrong_then_right_leaves_exactly_one_grey_heart(db: AsyncSession) -> None:
    pid = await _player(db)
    session = await service.start_session(db, pid, "adventure")
    inst = await _issue(db, pid, session.session_id)

    miss = await _submit(db, pid, inst.id, _wrong(inst))
    hit = await _submit(db, pid, inst.id, _right(inst))

    assert miss.attempts_left == 2
    assert hit.solved is True
    assert hit.attempts_left == 2
    replay = await _submit(db, pid, inst.id, _right(inst))
    assert replay.attempts_left == 2


async def test_correct_after_misses_uses_hints_penalty(db: AsyncSession) -> None:
    pid = await _player(db)
    session = await service.start_session(db, pid, "adventure")
    clean = await _issue(db, pid, session.session_id, "sub_within_10")
    helped = await _issue(db, pid, session.session_id, "add_within_10")

    await _submit(db, pid, clean.id, _right(clean))
    await _submit(db, pid, helped.id, _wrong(helped, 0))
    await _submit(db, pid, helped.id, _wrong(helped, 1))
    await _submit(db, pid, helped.id, _right(helped))

    assert (await _row(db, pid, "add_within_10")).rating < (
        await _row(db, pid, "sub_within_10")
    ).rating


async def test_solved_total_is_per_player_and_counts_only_solved(db: AsyncSession) -> None:
    me = await _player(db, "Me")
    other = await _player(db, "Other")
    mine = await service.start_session(db, me, "adventure")
    theirs = await service.start_session(db, other, "adventure")
    solved = await _issue(db, me, mine.session_id, seed=1)
    missed = await _issue(db, me, mine.session_id, seed=2)
    pending = await _issue(db, me, mine.session_id, seed=3)
    elsewhere = await _issue(db, other, theirs.session_id, seed=4)

    assert await service.total_solved(db, me) == 0
    first = await _submit(db, me, solved.id, _right(solved))
    assert first.total_solved == 1
    for k in range(3):
        out = await _submit(db, me, missed.id, _wrong(missed, k))
        assert out.total_solved == 1
    tried = await _submit(db, me, pending.id, _wrong(pending))
    assert tried.total_solved == 1
    theirs_out = await _submit(db, other, elsewhere.id, _right(elsewhere))
    assert theirs_out.total_solved == 1

    assert await problems.count_solved(db, me) == 1
    assert await problems.count_solved(db, other) == 1
    assert await service.total_solved(db, me) == 1
    again = await _issue(db, me, mine.session_id, seed=5)
    assert (await _submit(db, me, again.id, _right(again))).total_solved == 2
    assert await service.total_solved(db, other) == 1


async def test_other_player_problem_404(db: AsyncSession) -> None:
    owner = await _player(db, "Owner")
    other = await _player(db, "Other")
    session = await service.start_session(db, owner, "adventure")
    inst = await _issue(db, owner, session.session_id)

    with pytest.raises(NotFound):
        await _submit(db, other, inst.id, _right(inst))
    with pytest.raises(NotFound):
        await service.next_problem(db, GRAPH, other, session.session_id)
    with pytest.raises(NotFound):
        await _submit(db, owner, uuid.uuid4(), "1")
    assert await mastery.get(db, owner, "add_within_10") is None


async def test_new_player_starts_on_ready_skills(db: AsyncSession) -> None:
    pid = await _player(db)
    session = await service.start_session(db, pid, "adventure")

    problem = await service.next_problem(db, GRAPH, pid, session.session_id)

    assert problem.skill_id in GRAPH.ready(set())
    assert problem.prompt
    assert problem.skill_name == GRAPH.skills[problem.skill_id].name
    assert problem.dev_answer_latex is None
    count = await db.scalar(
        select(func.count()).select_from(ProblemInstance).where(ProblemInstance.player_id == pid)
    )
    assert count == 1


async def test_next_problem_exposes_answer_only_when_asked(db: AsyncSession) -> None:
    pid = await _player(db)
    session = await service.start_session(db, pid, "adventure")

    problem = await service.next_problem(db, GRAPH, pid, session.session_id, expose_answers=True)

    inst = await db.get(ProblemInstance, problem.problem_id)
    assert inst is not None
    assert problem.dev_answer_latex == _right(inst)


async def test_next_problem_counts_and_regenerates_deterministically(db: AsyncSession) -> None:
    pid = await _player(db)
    session = await service.start_session(db, pid, "adventure")

    problem = await service.next_problem(db, GRAPH, pid, session.session_id)

    inst = await db.get(ProblemInstance, problem.problem_id)
    assert inst is not None
    regenerated = get_generator(inst.skill_id).generate(inst.seed, inst.tier)
    assert service._prompt_out(regenerated.prompt) == problem.prompt  # pyright: ignore[reportPrivateUsage]
    assert inst.difficulty == regenerated.difficulty
    again = await service.next_problem(db, GRAPH, pid, session.session_id)
    assert again.problem_id != problem.problem_id


async def test_next_problem_stays_on_a_skill_for_a_short_run(db: AsyncSession) -> None:
    pid = await _player(db)
    session = await service.start_session(db, pid, "adventure")
    skills: list[str] = []
    for _ in range(4):
        problem = await service.next_problem(
            db, GRAPH, pid, session.session_id, expose_answers=True
        )
        skills.append(problem.skill_id)
        await _submit(db, pid, problem.problem_id, problem.dev_answer_latex or "")

    assert skills[0] == skills[1] == skills[2]
    assert skills[3] != skills[0]
    recent = await problems.recent_skill_ids(db, session.session_id, limit=3)
    assert recent == skills[1:]
    assert service.RECENT_LOOKBACK == RUN_LENGTH * 2 + 2


async def _master(db: AsyncSession, pid: uuid.UUID, session_id: uuid.UUID, skill_id: str) -> int:
    """Answer correctly at the engine's chosen tier until mastered; returns the answer count."""
    tiers = get_generator(skill_id).tier_difficulties
    for n in range(1, 40):
        row = await mastery.get(db, pid, skill_id)
        tier = choose_tier(service._rating(row, skill_id), tiers)  # pyright: ignore[reportPrivateUsage]
        inst = await _issue(db, pid, session_id, skill_id, tier, seed=n)
        await _submit(db, pid, inst.id, _right(inst))
        if (await _row(db, pid, skill_id)).state == "mastered":
            return n
    raise AssertionError("never mastered")


async def test_mastery_unlocks_next_skill(db: AsyncSession) -> None:
    pid = await _player(db)
    session = await service.start_session(db, pid, "adventure")
    assert "add_within_20" not in GRAPH.ready(set())

    count = await _master(db, pid, session.session_id, "add_within_10")

    assert count <= 12
    row = await _row(db, pid, "add_within_10")
    assert row.state == "mastered"
    assert row.review_interval_days == 1
    assert row.review_due_at is not None
    mastered = {r.skill_id for r in await mastery.list_for_player(db, pid) if r.state == "mastered"}
    assert "add_within_20" in GRAPH.ready(mastered)


async def test_mastered_skill_review_schedule(db: AsyncSession) -> None:
    pid = await _player(db)
    session = await service.start_session(db, pid, "adventure")
    await _master(db, pid, session.session_id, "add_within_10")
    row = await _row(db, pid, "add_within_10")
    now = datetime.now(UTC)

    async def make_due() -> None:
        await db.execute(
            update(SkillMastery)
            .where(SkillMastery.player_id == pid, SkillMastery.skill_id == "add_within_10")
            .values(review_due_at=now - timedelta(hours=1))
        )

    # Not due yet: a correct answer leaves the schedule alone.
    inst = await _issue(db, pid, session.session_id, tier=2, seed=101)
    out = await _submit(db, pid, inst.id, _right(inst))
    assert out.mastery.state is SkillState.MASTERED
    assert (await _row(db, pid, "add_within_10")).review_due_at == row.review_due_at

    # Due: state reads as review_due; a correct review moves to the next step.
    await make_due()
    inst = await _issue(db, pid, session.session_id, tier=2, seed=102)
    out = await _submit(db, pid, inst.id, _right(inst))
    after = await _row(db, pid, "add_within_10")
    assert after.state == "mastered"
    assert after.review_interval_days == 3
    assert after.review_due_at is not None and after.review_due_at > now

    # A failed review resets the interval and drops out of mastered when the rating falls.
    await make_due()
    for seed in (103, 104, 105, 106, 107, 108):
        inst = await _issue(db, pid, session.session_id, tier=2, seed=seed)
        for k in range(3):
            await _submit(db, pid, inst.id, _wrong(inst, k))
    final = await _row(db, pid, "add_within_10")
    assert final.state == "learning"
    assert final.review_interval_days is None
    assert final.review_due_at is None


async def test_a_wrong_answer_never_promotes_a_learning_skill(db: AsyncSession) -> None:
    # A row rated far above the top tier (as saved before ratings were capped) with a
    # top-tier streak: after one more scored miss it still passes `is_mastered`.
    pid = await _player(db)
    session = await service.start_session(db, pid, "adventure")
    top = max(get_generator("add_within_10").tier_difficulties)
    db.add(
        SkillMastery(
            player_id=pid,
            skill_id="add_within_10",
            rating=top + 4.0,
            attempts=6,
            recent=[[1, 2]] * 6,
            state=SkillState.LEARNING.value,
        )
    )
    await db.flush()

    missed = await _issue(db, pid, session.session_id, tier=2, seed=21)
    await _submit(db, pid, missed.id, _wrong(missed, 0))
    await _submit(db, pid, missed.id, _wrong(missed, 1))
    out = await _submit(db, pid, missed.id, _wrong(missed, 2))
    assert out.answer_latex is not None  # scored as a miss
    row = await _row(db, pid, "add_within_10")
    assert is_mastered(service._rating(row, "add_within_10"), top)  # pyright: ignore[reportPrivateUsage]
    assert row.state == "learning"
    assert row.review_due_at is None
    assert out.mastery.state is SkillState.LEARNING

    solved = await _issue(db, pid, session.session_id, tier=2, seed=22)
    await _submit(db, pid, solved.id, _right(solved))
    assert (await _row(db, pid, "add_within_10")).state == "mastered"


async def test_due_review_state_and_pick(db: AsyncSession) -> None:
    pid = await _player(db)
    session = await service.start_session(db, pid, "adventure")
    await _master(db, pid, session.session_id, "add_within_10")
    await db.execute(
        update(SkillMastery)
        .where(SkillMastery.player_id == pid, SkillMastery.skill_id == "add_within_10")
        .values(review_due_at=datetime.now(UTC) - timedelta(days=1))
    )
    await db.execute(
        update(PlaySession).where(PlaySession.id == session.session_id).values(problem_count=4)
    )

    problem = await service.next_problem(db, GRAPH, pid, session.session_id)

    assert problem.skill_id == "add_within_10"
    inst = await db.get(ProblemInstance, problem.problem_id)
    assert inst is not None
    out = await _submit(db, pid, inst.id, _wrong(inst))
    assert out.mastery.state is SkillState.REVIEW_DUE
    assert out.mastery.progress == pytest.approx(1.0)


async def test_progress_is_clamped_fraction_of_target(db: AsyncSession) -> None:
    pid = await _player(db)
    session = await service.start_session(db, pid, "adventure")
    inst = await _issue(db, pid, session.session_id)
    out = await _submit(db, pid, inst.id, _right(inst))
    assert 0.0 < out.mastery.progress < 1.0


class _CountingPool(CheckerPool):
    def __init__(self) -> None:
        super().__init__()
        self.calls = 0

    async def check(self, problem: Problem, latex: str) -> CheckResult:
        self.calls += 1
        return check(problem, latex)


async def test_long_input_is_unreadable_without_the_checker_and_capped_when_stored(
    db: AsyncSession,
) -> None:
    pid = await _player(db)
    session = await service.start_session(db, pid, "adventure")
    inst = await _issue(db, pid, session.session_id)
    pool = _CountingPool()

    out = await service.submit_answer(db, pool, GRAPH, pid, inst.id, "9" * 500)

    assert out.verdict is Verdict.UNREADABLE
    assert out.attempts_left == 3
    assert pool.calls == 0
    stored = (await db.scalars(select(Attempt.latex))).all()
    assert [len(s) for s in stored] == [200]


async def test_free_verdicts_are_capped_at_three(db: AsyncSession) -> None:
    pid = await _player(db)
    session = await service.start_session(db, pid, "adventure")
    inst = await _issue(db, pid, session.session_id)

    for _ in range(3):
        free = await _submit(db, pid, inst.id, r"rac{")
        assert free.verdict is Verdict.UNREADABLE
        assert free.attempts_left == 3
    fourth = await _submit(db, pid, inst.id, r"rac{")
    assert fourth.verdict is Verdict.UNREADABLE
    assert fourth.attempts_left == 2
    assert fourth.answer_latex is None
    await _submit(db, pid, inst.id, r"rac{")
    last = await _submit(db, pid, inst.id, r"rac{")
    assert last.verdict is Verdict.UNREADABLE
    assert last.attempts_left == 0
    assert last.solved is False
    assert last.answer_latex == _right(inst)
    assert (await _row(db, pid, "add_within_10")).recent == [[0, 0]]


async def test_repeating_the_previous_wrong_answer_is_free(db: AsyncSession) -> None:
    pid = await _player(db)
    session = await service.start_session(db, pid, "adventure")
    inst = await _issue(db, pid, session.session_id)

    first = await _submit(db, pid, inst.id, _wrong(inst))
    tap = await _submit(db, pid, inst.id, _wrong(inst))
    assert tap == first
    assert first.attempts_left == 2
    other = await _submit(db, pid, inst.id, _wrong(inst) + "1")
    assert other.attempts_left == 1


async def test_next_problem_closes_the_previous_one(db: AsyncSession) -> None:
    pid = await _player(db)
    session = await service.start_session(db, pid, "adventure")
    first = await service.next_problem(db, GRAPH, pid, session.session_id, expose_answers=True)
    await service.next_problem(db, GRAPH, pid, session.session_id)

    with pytest.raises(Conflict) as err:
        await _submit(db, pid, first.problem_id, first.dev_answer_latex or "1")
    assert err.value.code == "problem_closed"
    inst = await db.get(ProblemInstance, first.problem_id)
    assert inst is not None
    assert inst.answered_at is not None and inst.correct is None
    assert await mastery.get(db, pid, first.skill_id) is None


class _SlowPool(CheckerPool):
    """Sleeps inside the check and records whether the session had a transaction open."""

    def __init__(self, delay: float, session: AsyncSession | None = None) -> None:
        super().__init__()
        self.delay = delay
        self.session = session
        self.open_during_check: list[bool] = []

    async def check(self, problem: Problem, latex: str) -> CheckResult:
        if self.session is not None:
            self.open_during_check.append(self.session.in_transaction())
        await asyncio.sleep(self.delay)
        return check(problem, latex)


async def test_no_transaction_is_open_during_the_check(db: AsyncSession) -> None:
    pid = await _player(db)
    session = await service.start_session(db, pid, "adventure")
    inst = await _issue(db, pid, session.session_id)
    await db.commit()
    pool = _SlowPool(0.0, db)

    out = await service.submit_answer(db, pool, GRAPH, pid, inst.id, _right(inst))

    assert out.solved is True
    assert pool.open_during_check == [False]


async def test_slow_check_does_not_block_or_double_count(db_schema: str) -> None:
    engine = create_async_engine(
        _database_url(),
        pool_size=10,
        connect_args={"server_settings": {"search_path": db_schema}},
    )
    factory = async_sessionmaker(engine, expire_on_commit=False)
    try:
        async with factory() as setup:
            pid = await _player(setup, "Slowpoke")
            session = await service.start_session(setup, pid, "adventure")
            inst = await _issue(setup, pid, session.session_id)
            await setup.commit()
        pool = _SlowPool(0.5)

        async def submit(latex: str) -> AnswerOut:
            async with factory() as s:
                return await service.submit_answer(s, pool, GRAPH, pid, inst.id, latex)

        slow = asyncio.create_task(submit(_right(inst)))
        await asyncio.sleep(0.1)
        # A second request on the same problem is not stalled behind the first one's check.
        other = await asyncio.wait_for(submit(_right(inst)), timeout=5)
        first = await slow
        assert first.solved and other.solved
        assert first == other
        async with factory() as s:
            row = await mastery.get(s, pid, "add_within_10")
            assert row is not None
            assert row.attempts == 1
            stored = await s.scalar(select(func.count()).select_from(Attempt))
            assert stored == 1
    finally:
        async with factory() as cleanup:
            await cleanup.execute(delete(Player).where(Player.nickname.like("Slowpoke%")))
            await cleanup.commit()
        await engine.dispose()


async def test_concurrent_submissions_two_devices(db_schema: str) -> None:
    """Real committed connections: two problems on one skill race for the mastery row."""
    engine = create_async_engine(
        _database_url(),
        pool_size=10,
        connect_args={"server_settings": {"search_path": db_schema}},
    )
    factory = async_sessionmaker(engine, expire_on_commit=False)
    graph: SkillGraph = GRAPH
    try:
        async with factory() as setup:
            pid = await _player(setup, "Racer")
            session = await service.start_session(setup, pid, "adventure")
            first = await _issue(setup, pid, session.session_id, seed=1)
            second = await _issue(setup, pid, session.session_id, seed=2)
            await setup.commit()

        async def submit(inst: ProblemInstance) -> AnswerOut:
            async with factory() as s:
                return await service.submit_answer(s, POOL, graph, pid, inst.id, _right(inst))

        async def submit_twice(inst: ProblemInstance) -> list[AnswerOut]:
            return list(await asyncio.gather(submit(inst), submit(inst)))

        outs = await asyncio.gather(submit(first), submit(second))
        assert all(o.solved for o in outs)
        async with factory() as check_session:
            row = await mastery.get(check_session, pid, "add_within_10")
            assert row is not None
            assert row.attempts == 2
            assert row.recent == [[1, 0], [1, 0]]

        # The same problem submitted from two devices at once still scores once.
        async with factory() as setup:
            third = await _issue(setup, pid, session.session_id, seed=3)
            await setup.commit()
        pair = await submit_twice(third)
        assert pair[0] == pair[1]
        async with factory() as check_session:
            row = await mastery.get(check_session, pid, "add_within_10")
            assert row is not None
            assert row.attempts == 3
    finally:
        async with factory() as cleanup:
            await cleanup.execute(delete(Player).where(Player.nickname.like("Racer%")))
            await cleanup.commit()
        await engine.dispose()


async def test_mastery_row_lock_makes_a_second_scorer_wait(db_schema: str) -> None:
    """A held skill_mastery lock stalls scoring of another problem of the same skill."""
    engine = create_async_engine(
        _database_url(),
        pool_size=10,
        connect_args={"server_settings": {"search_path": db_schema}},
    )
    factory = async_sessionmaker(engine, expire_on_commit=False)
    try:
        async with factory() as setup:
            pid = await _player(setup, "Holder")
            session = await service.start_session(setup, pid, "adventure")
            inst = await _issue(setup, pid, session.session_id, seed=11)
            await mastery.lock(setup, pid, "add_within_10", service._start_rating("add_within_10"))  # pyright: ignore[reportPrivateUsage]
            await setup.commit()

        async def submit() -> AnswerOut:
            async with factory() as s:
                return await service.submit_answer(s, POOL, GRAPH, pid, inst.id, _right(inst))

        async with factory() as holder:
            held = await mastery.lock(holder, pid, "add_within_10", 0.0)
            waiting = asyncio.create_task(submit())
            await asyncio.sleep(0.3)
            assert not waiting.done()
            held.attempts += 1
            await holder.commit()
        out = await asyncio.wait_for(waiting, timeout=5)
        assert out.solved
        async with factory() as check_session:
            row = await mastery.get(check_session, pid, "add_within_10")
            assert row is not None
            assert row.attempts == 2
    finally:
        async with factory() as cleanup:
            await cleanup.execute(delete(Player).where(Player.nickname.like("Holder%")))
            await cleanup.commit()
        await engine.dispose()
