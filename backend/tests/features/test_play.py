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

from mathquest.engine.catalog import Catalog, build_catalog, load_catalog
from mathquest.engine.checker.bounded import CheckerPool
from mathquest.engine.checker.check import CheckResult, Verdict, check
from mathquest.engine.content import load_pack
from mathquest.engine.content.schema import Bank, WordProblems, WordTemplate
from mathquest.engine.mastery import Outcome, SkillState, choose_tier, is_mastered
from mathquest.engine.scheduler import RUN_LENGTH
from mathquest.engine.transport import prompt_out
from mathquest.engine.types import Problem
from mathquest.entities import lessons, mastery, players, problems
from mathquest.entities.mastery import SkillMastery
from mathquest.entities.models import Player
from mathquest.entities.problems import Attempt, PlaySession, ProblemInstance, add_problem
from mathquest.features.play import service
from mathquest.features.play.schema import AnswerOut, LessonDueOut, ProblemOut, SummaryOut
from mathquest.features.play.variants import choose_variant
from mathquest.shared.errors import Conflict, Invalid, NotFound
from tests.conftest import EARLY_SKILLS, _database_url  # pyright: ignore[reportPrivateUsage]

CATALOG = load_catalog(Path(__file__).resolve().parents[2] / "content", "k8-core")
GRAPH = CATALOG.graph
SEED = 7


class _SyncPool(CheckerPool):
    async def check(self, problem: Problem, latex: str) -> CheckResult:
        return check(problem, latex)


POOL = _SyncPool()


async def _player(
    db: AsyncSession, name: str = "Tester", *, lessons_seen: bool = True, fresh: bool = False
) -> uuid.UUID:
    """A new player; by default one who has seen every lesson, so `next` issues problems,
    and who has passed `EARLY_SKILLS` (`fresh=True`: none, to see where a new player begins)."""
    row = await players.add(
        db,
        nickname=f"{name}{uuid.uuid4().hex[:6]}",
        pin_hash=None,
        picture_hash=None,
        recovery_hash="x",
    )
    if lessons_seen:
        for skill_id in CATALOG.pack.lessons:
            await lessons.mark_seen(db, row.id, skill_id, datetime.now(UTC))
    if not fresh:
        await _mark_provisional(db, row.id, *EARLY_SKILLS, due_in=timedelta(days=365))
    return row.id


async def _next_problem(
    db: AsyncSession,
    catalog: Catalog,
    player_id: uuid.UUID,
    session_id: uuid.UUID,
    *,
    expose_answers: bool = False,
) -> ProblemOut:
    out = await service.next_problem(
        db, catalog, player_id, session_id, expose_answers=expose_answers
    )
    assert isinstance(out, ProblemOut)
    return out


async def _issue(
    db: AsyncSession,
    player_id: uuid.UUID,
    session_id: uuid.UUID,
    skill_id: str = "add_within_10",
    tier: int = 0,
    seed: int = SEED,
    variant: str = "bare",
    template_id: str | None = None,
) -> ProblemInstance:
    problem = CATALOG.source(skill_id).generate(seed, tier)
    return await add_problem(
        db,
        session_id=session_id,
        player_id=player_id,
        skill_id=skill_id,
        tier=tier,
        seed=seed,
        difficulty=problem.difficulty,
        issued_at=datetime.now(UTC),
        variant=variant,
        template_id=template_id,
    )


def _answer(inst: ProblemInstance) -> sympy.Expr:
    return CATALOG.source(inst.skill_id).generate(inst.seed, inst.tier).answer


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
    return await service.submit_answer(db, POOL, CATALOG, player_id, problem_id, latex)


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
    assert row.rating > service._start_rating(CATALOG, "add_within_10")  # pyright: ignore[reportPrivateUsage]
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
    assert row.rating < service._start_rating(CATALOG, "add_within_10")  # pyright: ignore[reportPrivateUsage]
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
        await _next_problem(db, CATALOG, other, session.session_id)
    with pytest.raises(NotFound):
        await _submit(db, owner, uuid.uuid4(), "1")
    assert await mastery.get(db, owner, "add_within_10") is None


async def test_new_player_starts_on_ready_skills(db: AsyncSession) -> None:
    pid = await _player(db, fresh=True)
    session = await service.start_session(db, pid, "adventure")

    problem = await _next_problem(db, CATALOG, pid, session.session_id)

    assert problem.skill_id in GRAPH.ready(set())
    assert problem.prompt
    assert problem.skill_name == GRAPH.skills[problem.skill_id].name
    assert problem.keypad == GRAPH.skills[problem.skill_id].keypad
    assert problem.dev_answer_latex is None
    count = await db.scalar(
        select(func.count()).select_from(ProblemInstance).where(ProblemInstance.player_id == pid)
    )
    assert count == 1


async def test_a_new_skill_with_a_lesson_starts_with_the_lesson(db: AsyncSession) -> None:
    pid = await _player(db, lessons_seen=False)
    session = await service.start_session(db, pid, "adventure")
    out = await service.next_problem(db, CATALOG, pid, session.session_id)
    assert out == LessonDueOut(skill_id="add_within_10", skill_name="Add to 10")
    issued = await db.scalar(select(func.count()).select_from(ProblemInstance))
    assert issued == 0
    row = await db.get(PlaySession, session.session_id)
    assert row is not None and row.problem_count == 0


async def test_a_skill_already_practiced_gets_no_lesson(db: AsyncSession) -> None:
    pid = await _player(db, lessons_seen=False)
    row = await mastery.lock(db, pid, "add_within_10", -10.0)
    row.attempts = 4
    await db.commit()
    session = await service.start_session(db, pid, "adventure")
    out = await service.next_problem(db, CATALOG, pid, session.session_id)
    assert isinstance(out, ProblemOut)
    assert out.skill_id == "add_within_10"


async def test_next_problem_exposes_answer_only_when_asked(db: AsyncSession) -> None:
    pid = await _player(db)
    session = await service.start_session(db, pid, "adventure")

    problem = await _next_problem(db, CATALOG, pid, session.session_id, expose_answers=True)

    inst = await db.get(ProblemInstance, problem.problem_id)
    assert inst is not None
    assert problem.dev_answer_latex == _right(inst)


async def test_next_problem_counts_and_regenerates_deterministically(db: AsyncSession) -> None:
    pid = await _player(db)
    session = await service.start_session(db, pid, "adventure")

    problem = await _next_problem(db, CATALOG, pid, session.session_id)

    inst = await db.get(ProblemInstance, problem.problem_id)
    assert inst is not None
    regenerated = service.regenerate(CATALOG, inst)
    assert prompt_out(regenerated.prompt) == problem.prompt
    assert inst.difficulty == regenerated.difficulty
    again = await _next_problem(db, CATALOG, pid, session.session_id)
    assert again.problem_id != problem.problem_id


async def test_a_skill_without_word_or_bank_content_stays_bare(db: AsyncSession) -> None:
    pid = await _player(db)
    session = await service.start_session(db, pid, "adventure")

    problem = await _next_problem(db, CATALOG, pid, session.session_id)

    inst = await db.get(ProblemInstance, problem.problem_id)
    assert inst is not None
    assert (inst.variant, inst.template_id) == ("bare", None)


@pytest.mark.parametrize(
    ("variant", "template_id"), [("word", "removed_template"), ("nonsense", "x")]
)
async def test_unknown_variant_or_template_falls_back_to_bare(
    db: AsyncSession, variant: str, template_id: str | None
) -> None:
    pid = await _player(db)
    session = await service.start_session(db, pid, "adventure")
    inst = await _issue(db, pid, session.session_id, variant=variant, template_id=template_id)

    bare = CATALOG.source(inst.skill_id).generate(inst.seed, inst.tier)
    assert service.regenerate(CATALOG, inst) == bare
    out = await _submit(db, pid, inst.id, _right(inst))
    assert out.solved


async def test_next_problem_stays_on_a_skill_for_a_short_run(db: AsyncSession) -> None:
    pid = await _player(db)
    session = await service.start_session(db, pid, "adventure")
    skills: list[str] = []
    for _ in range(4):
        problem = await _next_problem(db, CATALOG, pid, session.session_id, expose_answers=True)
        skills.append(problem.skill_id)
        await _submit(db, pid, problem.problem_id, problem.dev_answer_latex or "")

    assert skills[0] == skills[1] == skills[2]
    assert skills[3] != skills[0]
    history = await problems.session_history(db, session.session_id)
    assert [h[0] for h in history] == skills
    assert [h[1] for h in history] == [True] * 4
    assert skills.count(skills[0]) == RUN_LENGTH


async def _master(db: AsyncSession, pid: uuid.UUID, session_id: uuid.UUID, skill_id: str) -> int:
    """Answer correctly at the engine's chosen tier until mastered; returns the answer count."""
    tiers = CATALOG.source(skill_id).tier_difficulties
    for n in range(1, 40):
        row = await mastery.get(db, pid, skill_id)
        tier = choose_tier(service._rating(CATALOG, row, skill_id), tiers)  # pyright: ignore[reportPrivateUsage]
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
    top = max(CATALOG.source("add_within_10").tier_difficulties)
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
    assert is_mastered(service._rating(CATALOG, row, "add_within_10"), top)  # pyright: ignore[reportPrivateUsage]
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

    problem = await _next_problem(db, CATALOG, pid, session.session_id)

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

    out = await service.submit_answer(db, pool, CATALOG, pid, inst.id, "9" * 500)

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
    first = await _next_problem(db, CATALOG, pid, session.session_id, expose_answers=True)
    await _next_problem(db, CATALOG, pid, session.session_id)

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

    out = await service.submit_answer(db, pool, CATALOG, pid, inst.id, _right(inst))

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
                return await service.submit_answer(s, pool, CATALOG, pid, inst.id, latex)

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
    catalog: Catalog = CATALOG
    try:
        async with factory() as setup:
            pid = await _player(setup, "Racer")
            session = await service.start_session(setup, pid, "adventure")
            first = await _issue(setup, pid, session.session_id, seed=1)
            second = await _issue(setup, pid, session.session_id, seed=2)
            await setup.commit()

        async def submit(inst: ProblemInstance) -> AnswerOut:
            async with factory() as s:
                return await service.submit_answer(s, POOL, catalog, pid, inst.id, _right(inst))

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
            start = service._start_rating(CATALOG, "add_within_10")  # pyright: ignore[reportPrivateUsage]
            await mastery.lock(setup, pid, "add_within_10", start)
            await setup.commit()

        async def submit() -> AnswerOut:
            async with factory() as s:
                return await service.submit_answer(s, POOL, CATALOG, pid, inst.id, _right(inst))

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


FIXTURE = build_catalog(
    load_pack(Path(__file__).resolve().parents[1] / "fixtures" / "packs" / "test-pack"),
    CATALOG.slots,
)


async def test_variant_and_template_are_drawn_from_the_seed_and_stored(db: AsyncSession) -> None:
    pid = await _player(db)
    row = await mastery.lock(db, pid, "pick", 0.0)
    row.state = SkillState.MASTERED
    await db.commit()
    session = await service.start_session(db, pid, "adventure")
    source = FIXTURE.source("story")
    seen: set[str] = set()
    for _ in range(16):
        problem = await _next_problem(db, FIXTURE, pid, session.session_id)
        inst = await db.get(ProblemInstance, problem.problem_id)
        assert inst is not None and inst.skill_id == "story"
        assert inst.variant == choose_variant(source, inst.seed)
        expected = service.regenerate(FIXTURE, inst)
        assert inst.template_id == expected.template_id
        assert prompt_out(expected.prompt) == problem.prompt
        assert problem.choices is None and problem.keypad == "numpad"
        seen.add(inst.variant)
    assert "word" in seen


async def _choice_problem(db: AsyncSession) -> tuple[uuid.UUID, ProblemOut]:
    pid = await _player(db)
    session = await service.start_session(db, pid, "adventure")
    problem = await _next_problem(db, FIXTURE, pid, session.session_id, expose_answers=True)
    return pid, problem


async def test_a_choice_problem_is_answered_by_index(db: AsyncSession) -> None:
    pid, problem = await _choice_problem(db)
    assert problem.skill_id == "pick" and problem.keypad == "choice"
    assert problem.choices and problem.dev_answer_choice is not None
    assert problem.dev_answer_latex is None
    right = problem.dev_answer_choice
    wrong = (right + 1) % len(problem.choices)

    miss = await service.submit_answer(db, POOL, FIXTURE, pid, problem.problem_id, choice=wrong)
    assert (miss.verdict, miss.attempts_left, miss.answer_choice) == (Verdict.INCORRECT, 1, None)
    again = await service.submit_answer(db, POOL, FIXTURE, pid, problem.problem_id, choice=wrong)
    assert again.attempts_left == 1

    hit = await service.submit_answer(db, POOL, FIXTURE, pid, problem.problem_id, choice=right)
    assert hit.verdict is Verdict.CORRECT and hit.solved
    assert (hit.answer_choice, hit.answer_latex) == (right, None)
    stored = (
        (
            await db.execute(
                select(Attempt.latex)
                .where(Attempt.problem_id == problem.problem_id)
                .order_by(Attempt.id)
            )
        )
        .scalars()
        .all()
    )
    assert stored == [f"choice:{wrong}", f"choice:{right}"]
    replay = await service.submit_answer(db, POOL, FIXTURE, pid, problem.problem_id, choice=wrong)
    assert replay.solved and replay.answer_choice == right


@pytest.mark.parametrize(
    ("latex", "choice", "code"),
    [
        ("1", None, "choice_expected"),
        (None, 99, "choice_out_of_range"),
        (None, -1, "choice_out_of_range"),
    ],
)
async def test_bad_choice_answers_are_invalid_and_record_nothing(
    db: AsyncSession, latex: str | None, choice: int | None, code: str
) -> None:
    pid, problem = await _choice_problem(db)
    with pytest.raises(Invalid) as exc:
        await service.submit_answer(
            db, POOL, FIXTURE, pid, problem.problem_id, latex, choice=choice
        )
    assert exc.value.code == code
    await db.rollback()
    count = await db.scalar(
        select(func.count()).select_from(Attempt).where(Attempt.problem_id == problem.problem_id)
    )
    assert count == 0


async def test_a_choice_for_a_typed_problem_is_invalid(db: AsyncSession) -> None:
    pid = await _player(db)
    session = await service.start_session(db, pid, "adventure")
    inst = await _issue(db, pid, session.session_id)
    with pytest.raises(Invalid, match="latex_expected"):
        await service.submit_answer(db, POOL, CATALOG, pid, inst.id, choice=0)


async def test_a_second_miss_on_a_choice_problem_scores_it(db: AsyncSession) -> None:
    pid, problem = await _choice_problem(db)
    assert problem.choices and problem.dev_answer_choice is not None
    right = problem.dev_answer_choice
    first, second = ((right + k) % len(problem.choices) for k in (1, 2))

    await service.submit_answer(db, POOL, FIXTURE, pid, problem.problem_id, choice=first)
    out = await service.submit_answer(db, POOL, FIXTURE, pid, problem.problem_id, choice=second)
    assert (out.solved, out.attempts_left, out.answer_choice) == (False, 0, right)
    assert service.MAX_CHOICE_ATTEMPTS == 2


def _without_bank_item(item_id: str) -> Catalog:
    pack = FIXTURE.pack
    bank = pack.bank["pick"]
    kept = Bank(skill="pick", items=tuple(i for i in bank.items if i.id != item_id))
    return build_catalog(
        pack.model_copy(update={"bank": {**pack.bank, "pick": kept}}), FIXTURE.slots
    )


@pytest.mark.parametrize("send", ["choice", "latex"])
async def test_a_problem_whose_bank_item_is_gone_is_closed(db: AsyncSession, send: str) -> None:
    pid, problem = await _choice_problem(db)
    inst = await db.get(ProblemInstance, problem.problem_id)
    assert inst is not None and inst.variant == "bank" and inst.template_id is not None
    changed = _without_bank_item(inst.template_id)
    latex, choice = (None, 0) if send == "choice" else ("1", None)

    for _ in range(2):
        with pytest.raises(Conflict, match="problem_closed"):
            await service.submit_answer(
                db, POOL, changed, pid, problem.problem_id, latex, choice=choice
            )
        await db.rollback()
    await db.refresh(inst)
    assert inst.answered_at is not None and inst.correct is None
    count = await db.scalar(
        select(func.count()).select_from(Attempt).where(Attempt.problem_id == inst.id)
    )
    assert count == 0


def _failing_word_catalog() -> Catalog:
    """`story` always draws a word problem whose text breaks for an odd `a`."""
    pack = FIXTURE.pack
    story = pack.skills["story"].model_copy(update={"word_share": 1.0, "bank_share": 0.0})
    template = WordTemplate(
        id="halves", text_template=r"Half of {a} is {{= \frac{a}{2} }}.", grade_band="1"
    )
    words = WordProblems(skill="story", templates=(template,))
    return build_catalog(
        pack.model_copy(
            update={
                "skills": {**pack.skills, "story": story},
                "word_problems": {**pack.word_problems, "story": words},
            }
        ),
        FIXTURE.slots,
    )


async def test_a_variant_that_fails_to_render_is_issued_bare(
    db: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    catalog = _failing_word_catalog()
    seeds = iter(range(12))
    monkeypatch.setattr(service.secrets, "randbelow", lambda _limit: next(seeds))  # pyright: ignore[reportUnknownLambdaType]
    pid = await _player(db)
    row = await mastery.lock(db, pid, "pick", 0.0)
    row.state = SkillState.MASTERED
    await db.commit()
    session = await service.start_session(db, pid, "adventure")
    variants: set[str] = set()
    for _ in range(12):
        problem = await _next_problem(db, catalog, pid, session.session_id)
        inst = await db.get(ProblemInstance, problem.problem_id)
        assert inst is not None and inst.skill_id == "story"
        source = catalog.source("story")
        a = source.generate(inst.seed, inst.tier).values["a"]
        assert isinstance(a, int)
        expected = "word" if a % 2 == 0 else "bare"
        assert (inst.variant, inst.template_id) == (
            (expected, "halves") if expected == "word" else ("bare", None)
        )
        regenerated = service.regenerate(catalog, inst)
        assert prompt_out(regenerated.prompt) == problem.prompt
        variants.add(inst.variant)
    assert variants == {"word", "bare"}


async def test_new_seeds_are_safe_javascript_integers(db: AsyncSession) -> None:
    assert service.SEED_LIMIT == 2**53
    pid = await _player(db)
    session = await service.start_session(db, pid, "adventure")
    problem = await _next_problem(db, CATALOG, pid, session.session_id)
    inst = await db.get(ProblemInstance, problem.problem_id)
    assert inst is not None and 0 <= inst.seed < 2**53


async def test_a_stored_seed_above_the_new_limit_still_regenerates(db: AsyncSession) -> None:
    pid = await _player(db)
    session = await service.start_session(db, pid, "adventure")
    inst = await _issue(db, pid, session.session_id, seed=2**62 - 1)
    out = await _submit(db, pid, inst.id, _right(inst))
    assert out.solved


async def _mark_provisional(
    db: AsyncSession, pid: uuid.UUID, *skill_ids: str, due_in: timedelta = timedelta(days=1)
) -> datetime:
    now = datetime.now(UTC)
    ratings = {
        sid: service._start_rating(CATALOG, sid)  # pyright: ignore[reportPrivateUsage]
        for sid in skill_ids
    }
    await mastery.mark_provisional(db, pid, ratings, review_due_at=now + due_in, now=now)
    return now


async def test_provisional_skills_count_as_mastered_for_the_ready_set(db: AsyncSession) -> None:
    pid = await _player(db, lessons_seen=False)
    await _mark_provisional(db, pid, "add_within_10", "sub_within_10", "place_value_tens_ones")
    session = await service.start_session(db, pid, "adventure")

    out = await service.next_problem(db, CATALOG, pid, session.session_id)
    assert not isinstance(out, SummaryOut)

    # Not yet due, so not reviewed: play moves on to what they unlock.
    assert out.skill_id not in {"add_within_10", "sub_within_10", "place_value_tens_ones"}
    assert out.skill_id in GRAPH.ready({"add_within_10", "sub_within_10", "place_value_tens_ones"})


async def test_a_due_provisional_skill_is_reviewed_without_its_lesson(db: AsyncSession) -> None:
    pid = await _player(db, lessons_seen=False)
    await _mark_provisional(db, pid, "add_within_10", due_in=timedelta(hours=-1))
    session = await service.start_session(db, pid, "adventure")
    await db.execute(
        update(PlaySession).where(PlaySession.id == session.session_id).values(problem_count=4)
    )

    out = await service.next_problem(db, CATALOG, pid, session.session_id)

    assert isinstance(out, ProblemOut)
    assert out.skill_id == "add_within_10"


async def test_a_correct_review_confirms_a_provisional_skill(db: AsyncSession) -> None:
    pid = await _player(db)
    now = await _mark_provisional(db, pid, "add_within_10", due_in=timedelta(hours=-1))
    session = await service.start_session(db, pid, "adventure")

    inst = await _issue(db, pid, session.session_id, tier=1, seed=31)
    out = await _submit(db, pid, inst.id, _right(inst))

    assert out.mastery.state is SkillState.MASTERED
    row = await _row(db, pid, "add_within_10")
    assert row.state == "mastered"
    assert row.placed is True
    assert row.review_interval_days == 1
    assert row.review_due_at is not None and row.review_due_at > now + timedelta(hours=23)
    top = len(CATALOG.source("add_within_10").tier_difficulties) - 1

    # Later correct reviews keep it mastered and space the reviews out.
    for seed in (32, 33):
        await db.execute(
            update(SkillMastery)
            .where(SkillMastery.player_id == pid, SkillMastery.skill_id == "add_within_10")
            .values(review_due_at=datetime.now(UTC) - timedelta(hours=1))
        )
        inst = await _issue(db, pid, session.session_id, tier=top, seed=seed)
        out = await _submit(db, pid, inst.id, _right(inst))
        assert out.mastery.state is SkillState.MASTERED
    row = await _row(db, pid, "add_within_10")
    assert row.state == "mastered"
    assert row.review_interval_days == 7


async def test_a_review_below_the_probe_tier_does_not_confirm(db: AsyncSession) -> None:
    pid = await _player(db)
    await _mark_provisional(db, pid, "add_within_10", due_in=timedelta(hours=-1))
    session = await service.start_session(db, pid, "adventure")
    inst = await _issue(db, pid, session.session_id, tier=0, seed=34)

    out = await _submit(db, pid, inst.id, _right(inst))

    assert out.solved
    # Still provisional and still due, so it reads as a review due.
    assert out.mastery.state is SkillState.REVIEW_DUE
    row = await _row(db, pid, "add_within_10")
    assert row.state == "provisional"
    assert row.review_due_at is not None and row.review_due_at <= datetime.now(UTC)


async def test_a_bank_item_does_not_confirm_a_typed_skill(db: AsyncSession) -> None:
    pid = await _player(db)
    await _mark_provisional(db, pid, "add_within_10", due_in=timedelta(hours=-1))
    row = await _row(db, pid, "add_within_10")
    outcome = Outcome(correct=True, hints_used=0, seconds=2.0, fluency=False, tier=1)
    now = datetime.now(UTC)
    confirms = service._confirms(CATALOG, "add_within_10", "bank", 1)  # pyright: ignore[reportPrivateUsage]
    assert not confirms
    assert service._confirms(CATALOG, "add_within_10", "bare", 1)  # pyright: ignore[reportPrivateUsage]
    assert service._confirms(CATALOG, "add_within_10", "word", 2)  # pyright: ignore[reportPrivateUsage]
    service._apply_score(CATALOG, row, "add_within_10", 1.0, outcome, now, confirms=confirms)  # pyright: ignore[reportPrivateUsage]
    assert row.state == "provisional"


async def test_a_provisional_skill_is_reviewed_at_the_probe_tier_without_a_bank_item(
    db: AsyncSession,
) -> None:
    pid = await _player(db)
    await _mark_provisional(db, pid, "add_within_10", due_in=timedelta(hours=-1))
    session = await service.start_session(db, pid, "adventure")
    for index in range(5):
        out = await _next_problem(db, CATALOG, pid, session.session_id)
        if index == 4:
            assert out.skill_id == "add_within_10"
            inst = await db.get(ProblemInstance, out.problem_id)
            assert inst is not None
            assert inst.tier >= 1
            assert inst.variant == "bare"
        else:
            await db.execute(
                update(ProblemInstance)
                .where(ProblemInstance.id == out.problem_id)
                .values(answered_at=datetime.now(UTC), correct=True)
            )
            await db.commit()


async def test_a_missed_review_reverts_a_provisional_skill(db: AsyncSession) -> None:
    pid = await _player(db)
    await _mark_provisional(db, pid, "add_within_10")
    session = await service.start_session(db, pid, "adventure")

    inst = await _issue(db, pid, session.session_id, tier=1, seed=41)
    for k in range(2):
        await _submit(db, pid, inst.id, _wrong(inst, k))
    out = await _submit(db, pid, inst.id, _wrong(inst, 2))

    assert out.mastery.state is SkillState.LEARNING
    row = await _row(db, pid, "add_within_10")
    assert row.state == "learning"
    assert row.placed is False
    assert row.review_due_at is None
    assert row.attempts == 1


async def test_a_confirmed_skill_survives_one_miss_then_a_second_reverts(
    db: AsyncSession,
) -> None:
    pid = await _player(db)
    await _mark_provisional(db, pid, "add_within_10", due_in=timedelta(hours=-1))
    session = await service.start_session(db, pid, "adventure")
    top = len(CATALOG.source("add_within_10").tier_difficulties) - 1
    inst = await _issue(db, pid, session.session_id, tier=1, seed=51)
    await _submit(db, pid, inst.id, _right(inst))
    assert (await _row(db, pid, "add_within_10")).placed is True

    async def miss(seed: int) -> AnswerOut:
        inst = await _issue(db, pid, session.session_id, tier=top, seed=seed)
        for k in range(2):
            await _submit(db, pid, inst.id, _wrong(inst, k))
        return await _submit(db, pid, inst.id, _wrong(inst, 2))

    first = await miss(52)
    assert first.mastery.state is SkillState.MASTERED
    row = await _row(db, pid, "add_within_10")
    assert (row.state, row.review_interval_days) == ("mastered", 1)

    second = await miss(53)
    assert second.mastery.state is SkillState.LEARNING
    row = await _row(db, pid, "add_within_10")
    assert (row.state, row.placed) == ("learning", False)


async def test_a_provisional_skill_reads_as_provisional(db: AsyncSession) -> None:
    pid = await _player(db)
    await _mark_provisional(db, pid, "add_within_10")
    row = await _row(db, pid, "add_within_10")
    out = service._mastery_out(  # pyright: ignore[reportPrivateUsage]
        CATALOG, "add_within_10", row, datetime.now(UTC)
    )
    assert out.state is SkillState.PROVISIONAL
    assert out.progress == pytest.approx(1.0)
    later = service._mastery_out(  # pyright: ignore[reportPrivateUsage]
        CATALOG, "add_within_10", row, datetime.now(UTC) + timedelta(days=3)
    )
    assert later.state is SkillState.REVIEW_DUE


async def test_an_old_learner_keeps_the_skill_they_were_on(db: AsyncSession) -> None:
    """add_within_10 gained count_to_10 as a prerequisite after this learner started it."""
    pid = await _player(db, fresh=True)
    row = await mastery.lock(db, pid, "add_within_10", -1.0)
    row.attempts = 4
    row.state = "learning"
    await db.commit()

    out = await service.list_skills(db, CATALOG, pid)
    states = {s.skill_id: s.state for s in out.skills}
    assert states["add_within_10"] is SkillState.LEARNING
    assert states["sub_within_10"] is SkillState.LOCKED  # never started: waits for counting
    session = await service.start_practice(db, CATALOG, pid, skill_id="add_within_10")
    assert [f.skill_id for f in session.focus] == ["add_within_10"]
    ready = CATALOG.graph.ready(set(), {"add_within_10"})
    assert "add_within_10" in ready and "count_to_10" in ready
    adventure = await service.start_session(db, pid, "adventure")
    problem = await _next_problem(db, CATALOG, pid, adventure.session_id)
    assert problem.skill_id in ready


async def test_a_learner_placed_high_before_counting_existed_is_not_sent_back(
    db: AsyncSession,
) -> None:
    """A grade 2 placement from before: the old anchors' ancestors, none of the new skills."""
    pid = await _player(db, fresh=True)
    old = (
        "add_within_10",
        "add_within_20",
        "place_value_tens_ones",
        "add_2digit_no_regroup",
        "add_2digit_regroup",
    )
    await _mark_provisional(db, pid, *old)
    out = await service.list_skills(db, CATALOG, pid)
    states = {s.skill_id: s.state for s in out.skills}
    assert states["place_value_tens_ones"] is SkillState.PROVISIONAL
    # Under skills they know, so open to practice but never offered by the scheduler.
    for implied in ("count_to_10", "count_to_20", "teen_numbers"):
        assert states[implied] is SkillState.READY
        assert implied not in CATALOG.graph.ready(set(old), set(old))
    assert "count_to_100" in CATALOG.graph.ready(set(old), set(old))
    session = await service.start_session(db, pid, "adventure")
    problem = await _next_problem(db, CATALOG, pid, session.session_id)
    assert problem.skill_id not in ("count_to_10", "count_to_20", "teen_numbers")


async def test_a_typed_skill_serves_choice_bank_items_of_the_learners_tier(
    db: AsyncSession,
) -> None:
    """The comparing skills are typed, with a bank of button questions served beside them."""
    pid = await _player(db)
    await _mark_provisional(db, pid, "place_value_tens_ones")
    session = await service.start_practice(db, CATALOG, pid, skill_id="compare_numbers_100")
    source = CATALOG.source("compare_numbers_100")
    assert source.skill.keypad == "numpad" and source.bank is not None
    variants: dict[str, int] = {"bare": 0, "bank": 0}
    for _ in range(40):
        out = await _next_problem(db, CATALOG, pid, session.session_id, expose_answers=True)
        inst = await db.get(ProblemInstance, out.problem_id)
        assert inst is not None
        variants[inst.variant] += 1
        if inst.variant == "bank":
            assert out.keypad == "choice" and out.choices and out.dev_answer_choice is not None
            item = next(i for i in source.bank.items if i.id == inst.template_id)
            assert item.tier in (None, inst.tier)
            hit = await service.submit_answer(
                db, POOL, CATALOG, pid, out.problem_id, choice=out.dev_answer_choice
            )
            assert hit.verdict is Verdict.CORRECT
        else:
            assert out.keypad == "numpad" and out.choices is None
            await _submit(db, pid, out.problem_id, out.dev_answer_latex or "")
    assert variants["bank"] > 3 and variants["bare"] > 10
