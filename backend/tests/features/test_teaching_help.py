# pyright: reportUnknownMemberType=false, reportUnknownArgumentType=false, reportUnknownVariableType=false
"""Hints, mistake feedback, explanations, the stuck log, warm-ups and the frustration
guard, through the play and teaching services."""

import json
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
import sympy
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from mathquest.cli.content_report import read_stuck
from mathquest.engine.catalog import load_catalog
from mathquest.engine.checker.bounded import CheckerPool
from mathquest.engine.checker.check import CheckResult, check
from mathquest.engine.mastery import (
    Outcome,
    SkillRating,
    SkillState,
    choose_tier,
    initial_rating,
    update,
)
from mathquest.engine.scheduler import FRUSTRATION_MISSES, WARMUP_MISSES, WARMUP_PROBLEMS
from mathquest.engine.teaching import (
    FEEDBACK_COPY,
    next_approach,
    render_explanations,
    render_feedback,
    render_hints,
)
from mathquest.engine.transport import latex, prompt_out
from mathquest.engine.types import Problem
from mathquest.entities import lessons, mastery, players, problems
from mathquest.entities.problems import ProblemInstance
from mathquest.entities.teaching import ExplanationView, StuckEvent
from mathquest.features import teaching
from mathquest.features.play import service
from mathquest.features.play.schema import AnswerOut, ProblemOut
from mathquest.shared.errors import Conflict, NotFound

CATALOG = load_catalog(Path(__file__).resolve().parents[2] / "content", "k8-core")
PACK = CATALOG.pack
SKILL = "add_within_10"


class _SyncPool(CheckerPool):
    async def check(self, problem: Problem, latex: str) -> CheckResult:
        return check(problem, latex)


POOL = _SyncPool()


async def _player(db: AsyncSession) -> uuid.UUID:
    row = await players.add(
        db,
        nickname=f"Helper{uuid.uuid4().hex[:6]}",
        pin_hash=None,
        picture_hash=None,
        recovery_hash="x",
    )
    for skill_id in PACK.lessons:
        await lessons.mark_seen(db, row.id, skill_id, datetime.now(UTC))
    return row.id


async def _session(db: AsyncSession, pid: uuid.UUID) -> uuid.UUID:
    return (await service.start_session(db, pid, "adventure")).session_id


async def _issue(
    db: AsyncSession,
    pid: uuid.UUID,
    session_id: uuid.UUID,
    skill_id: str = SKILL,
    tier: int = 1,
    seed: int = 11,
) -> ProblemInstance:
    problem = CATALOG.source(skill_id).generate(seed, tier)
    return await problems.add_problem(
        db,
        session_id=session_id,
        player_id=pid,
        skill_id=skill_id,
        tier=tier,
        seed=seed,
        difficulty=problem.difficulty,
        issued_at=datetime.now(UTC),
    )


def _problem(inst: ProblemInstance) -> Problem:
    return CATALOG.source(inst.skill_id).generate(inst.seed, inst.tier)


def _right(inst: ProblemInstance) -> str:
    return latex(_problem(inst).answer)


def _wrong(inst: ProblemInstance, k: int = 0) -> str:
    return sympy.latex(_problem(inst).answer + 1000 + k)


async def _submit(db: AsyncSession, pid: uuid.UUID, inst: ProblemInstance, given: str) -> AnswerOut:
    return await service.submit_answer(db, POOL, CATALOG, pid, inst.id, given)


async def _miss_out(db: AsyncSession, pid: uuid.UUID, inst: ProblemInstance) -> AnswerOut:
    out = None
    for k in range(3):
        out = await _submit(db, pid, inst, _wrong(inst, k))
    assert out is not None and out.answer_latex is not None
    return out


# --- hints ---


async def test_three_hint_levels_in_order_with_this_problems_numbers(db: AsyncSession) -> None:
    pid = await _player(db)
    inst = await _issue(db, pid, await _session(db, pid))
    expected = render_hints(PACK.hints[SKILL], _problem(inst))
    values = _problem(inst).values
    for level in (1, 2, 3):
        out = await teaching.next_hint(db, CATALOG, pid, inst.id)
        assert (out.level, out.levels) == (level, 3)
        assert out.text == prompt_out(expected[level - 1])
    assert str(values["big"]) in "".join(p.value for p in out.text)
    assert latex(_problem(inst).answer) in "".join(p.value for p in out.text)

    with pytest.raises(Conflict) as err:
        await teaching.next_hint(db, CATALOG, pid, inst.id)
    assert err.value.code == "no_more_hints"
    await db.refresh(inst)
    assert inst.hints_used == 3


async def test_hint_on_a_scored_or_closed_problem_is_a_conflict(db: AsyncSession) -> None:
    pid = await _player(db)
    session_id = await _session(db, pid)
    solved = await _issue(db, pid, session_id)
    await _submit(db, pid, solved, _right(solved))
    for ask in (teaching.next_hint, teaching.next_explanation):
        with pytest.raises(Conflict) as err:
            await ask(db, CATALOG, pid, solved.id)
        assert err.value.code == "problem_scored"

    first = await service.next_problem(db, CATALOG, pid, session_id)
    assert isinstance(first, ProblemOut)
    await service.next_problem(db, CATALOG, pid, session_id)  # closes `first`
    with pytest.raises(Conflict) as err:
        await teaching.next_hint(db, CATALOG, pid, first.problem_id)
    assert err.value.code == "problem_closed"


async def test_hint_for_another_player_or_a_skill_without_hints_is_not_found(
    db: AsyncSession,
) -> None:
    pid, other = await _player(db), await _player(db)
    session_id = await _session(db, pid)
    inst = await _issue(db, pid, session_id)
    with pytest.raises(NotFound):
        await teaching.next_hint(db, CATALOG, other, inst.id)
    bare = await _issue(db, pid, session_id, "place_value_tens_ones", 0)
    assert "place_value_tens_ones" not in PACK.hints
    with pytest.raises(NotFound):
        await teaching.next_hint(db, CATALOG, pid, bare.id)
    with pytest.raises(NotFound):
        await teaching.next_explanation(db, CATALOG, pid, bare.id)


async def test_issued_problems_say_what_help_they_offer(db: AsyncSession) -> None:
    pid = await _player(db)
    out = await service.next_problem(db, CATALOG, pid, await _session(db, pid))
    assert isinstance(out, ProblemOut)
    assert out.hint_levels == (3 if out.skill_id in PACK.hints else 0)
    assert out.has_explanations is (out.skill_id in PACK.explanations)


async def _rating_after(db: AsyncSession, hints: int, misses: int) -> float:
    pid = await _player(db)
    inst = await _issue(db, pid, await _session(db, pid))
    for _ in range(hints):
        await teaching.next_hint(db, CATALOG, pid, inst.id)
    for k in range(misses):
        await _submit(db, pid, inst, _wrong(inst, k))
    out = await _submit(db, pid, inst, _right(inst))
    assert out.solved
    row = await mastery.get(db, pid, SKILL)
    assert row is not None
    return row.rating


def _expected(help_steps: int) -> float:
    tiers = CATALOG.source(SKILL).tier_difficulties
    fluency = CATALOG.graph.skills[SKILL].fluency
    outcome = Outcome(correct=True, hints_used=help_steps, seconds=0.0, fluency=fluency, tier=1)
    after = update(SkillRating(rating=initial_rating(tiers)), tiers[1], outcome, max(tiers))
    return after.rating


async def test_hints_and_wrong_tries_reduce_credit_together_capped(db: AsyncSession) -> None:
    assert await _rating_after(db, 0, 0) == pytest.approx(_expected(0))
    assert await _rating_after(db, 1, 0) == pytest.approx(_expected(1))
    assert await _rating_after(db, 1, 1) == pytest.approx(_expected(2))
    # After the full worked example the solve still counts, at the floor credit.
    assert await _rating_after(db, 3, 0) == pytest.approx(_expected(3))
    assert await _rating_after(db, 3, 1) == pytest.approx(_expected(3))
    assert _expected(0) > _expected(1) > _expected(2) > _expected(3)


# --- feedback ---


async def test_a_matched_mistake_gets_its_feedback_instead_of_a_retry(db: AsyncSession) -> None:
    pid = await _player(db)
    inst = await _issue(db, pid, await _session(db, pid))
    problem = _problem(inst)
    wrong = problem.misconceptions[0]
    out = await _submit(db, pid, inst, latex(wrong.answer))
    assert out.misconception == wrong.key
    assert out.feedback is not None and out.feedback.kind == "misconception"
    rendered = render_feedback(PACK.explanations[SKILL], problem, wrong.key)
    assert rendered is not None
    assert out.feedback.text == prompt_out(rendered)
    assert latex(problem.answer) not in [p.value for p in out.feedback.text]


async def test_an_unmatched_miss_suggests_a_hint_until_none_are_left(db: AsyncSession) -> None:
    pid = await _player(db)
    inst = await _issue(db, pid, await _session(db, pid))
    first = await _submit(db, pid, inst, _wrong(inst, 0))
    assert first.feedback is not None and first.feedback.kind == "hint"
    assert first.feedback.text[0].value == FEEDBACK_COPY["hint"]
    for _ in range(3):
        await teaching.next_hint(db, CATALOG, pid, inst.id)
    second = await _submit(db, pid, inst, _wrong(inst, 1))
    assert second.feedback is not None and second.feedback.kind == "retry"
    # Repeating the same wrong answer reports the same feedback again.
    again = await _submit(db, pid, inst, _wrong(inst, 1))
    assert again.feedback == second.feedback
    last = await _submit(db, pid, inst, _wrong(inst, 2))
    assert last.answer_latex is not None and last.feedback is None
    right = await _issue(db, pid, inst.session_id, seed=12)
    assert (await _submit(db, pid, right, _right(right))).feedback is None


# --- explanations and the stuck log ---


async def test_explanations_rotate_from_a_per_player_start(db: AsyncSession) -> None:
    pid = await _player(db)
    inst = await _issue(db, pid, await _session(db, pid))
    count = len(PACK.explanations[SKILL].approaches)
    rendered = render_explanations(PACK.explanations[SKILL], _problem(inst))
    seen: list[int] = []
    for k in range(count + 1):
        out = await teaching.next_explanation(db, CATALOG, pid, inst.id)
        assert out.approach == next_approach(str(pid), SKILL, count, k)
        assert out.approaches == count
        assert out.body == prompt_out(rendered[out.approach].body)
        seen.append(out.approach)
    assert sorted(seen[:count]) == list(range(count))
    assert seen[count] == seen[0]
    # The rotation carries on over problems: the next problem gets the next approach.
    later = await _issue(db, pid, inst.session_id, seed=12)
    out = await teaching.next_explanation(db, CATALOG, pid, later.id)
    assert out.approach == next_approach(str(pid), SKILL, count, count + 1)


async def _stuck_count(db: AsyncSession, pid: uuid.UUID) -> int:
    total = await db.scalar(
        select(func.count()).select_from(StuckEvent).where(StuckEvent.player_id == pid)
    )
    return int(total or 0)


async def _explain_all(db: AsyncSession, pid: uuid.UUID, inst: ProblemInstance) -> None:
    for _ in PACK.explanations[SKILL].approaches:
        await teaching.next_explanation(db, CATALOG, pid, inst.id)


async def test_a_miss_after_every_explanation_records_a_stuck_event(db: AsyncSession) -> None:
    pid = await _player(db)
    session_id = await _session(db, pid)
    inst = await _issue(db, pid, session_id)
    await _explain_all(db, pid, inst)
    await _submit(db, pid, inst, _wrong(inst, 0))
    await _submit(db, pid, inst, _wrong(inst, 1))
    assert await _stuck_count(db, pid) == 0  # not scored yet
    await _submit(db, pid, inst, _wrong(inst, 2))
    (event,) = (await db.execute(select(StuckEvent).where(StuckEvent.player_id == pid))).scalars()
    assert (event.skill_id, event.generator, event.tier, event.seed) == (
        SKILL,
        CATALOG.source(SKILL).generator.generator_id,
        inst.tier,
        inst.seed,
    )
    assert event.wrong_answers == [_wrong(inst, k) for k in range(3)]
    assert event.problem_id == inst.id

    # Later misses of the skill in the same session are stuck too; a solve is not.
    again = await _issue(db, pid, session_id, seed=12)
    await _miss_out(db, pid, again)
    solved = await _issue(db, pid, session_id, seed=13)
    await _submit(db, pid, solved, _right(solved))
    assert await _stuck_count(db, pid) == 2


async def test_no_stuck_event_without_every_explanation_in_this_session(db: AsyncSession) -> None:
    pid = await _player(db)
    first_session = await _session(db, pid)
    inst = await _issue(db, pid, first_session)
    for _ in range(len(PACK.explanations[SKILL].approaches) - 1):
        await teaching.next_explanation(db, CATALOG, pid, inst.id)
    await _miss_out(db, pid, inst)
    assert await _stuck_count(db, pid) == 0

    # All shown, but in an earlier session: a new session starts over.
    earlier = await _issue(db, pid, first_session, seed=12)
    await _explain_all(db, pid, earlier)
    await _submit(db, pid, earlier, _right(earlier))
    later = await _issue(db, pid, await _session(db, pid), seed=13)
    await _miss_out(db, pid, later)
    assert await _stuck_count(db, pid) == 0
    views = await db.scalar(
        select(func.count()).select_from(ExplanationView).where(ExplanationView.player_id == pid)
    )
    assert views == 2 * len(PACK.explanations[SKILL].approaches) - 1


async def test_the_export_has_the_coverage_report_shape_and_no_identity(
    db: AsyncSession, tmp_path: Path
) -> None:
    pid = await _player(db)
    before = datetime.now(UTC)
    inst = await _issue(db, pid, await _session(db, pid))
    await _explain_all(db, pid, inst)
    await _miss_out(db, pid, inst)

    entries = [e for e in await teaching.stuck_log(db, before) if e.seed == inst.seed]
    assert len(entries) >= 1
    dumped = [e.model_dump(mode="json") for e in entries]
    for entry in dumped:
        assert set(entry) == {"skill", "generator", "tier", "seed", "wrong_answers"}
        assert str(pid) not in json.dumps(entry)
    path = tmp_path / "stuck.json"
    path.write_text(json.dumps(dumped))
    assert read_stuck(path)[SKILL] == len(dumped)

    assert await teaching.stuck_log(db, datetime.now(UTC) + timedelta(days=1)) == []
    csv = teaching.stuck_csv(entries).splitlines()
    assert csv[0] == "skill,generator,tier,seed,wrong_answers"
    assert csv[1].startswith(f"{SKILL},")


# --- warm-up and frustration guard through `next` ---


async def _only_ready(db: AsyncSession, pid: uuid.UUID, ready: str) -> None:
    """Master every skill except ``ready`` and the skills that build on it."""
    blocked = {ready}
    for sid in CATALOG.graph.topo_order():
        if any(p in blocked for p in CATALOG.graph.prerequisites(sid)):
            blocked.add(sid)
    now = datetime.now(UTC)
    for sid in CATALOG.graph.skills:
        if sid in blocked:
            continue
        tiers = CATALOG.source(sid).tier_difficulties
        row = await mastery.lock(db, pid, sid, max(tiers) + 1.5)
        row.state = SkillState.MASTERED
        row.attempts = 6
        row.review_interval_days = 7
        row.review_due_at = now + timedelta(days=7)


async def test_struggling_on_a_skill_warms_up_on_its_prerequisite(db: AsyncSession) -> None:
    pid = await _player(db)
    await _only_ready(db, pid, "add_within_20")
    session_id = await _session(db, pid)
    for n in range(WARMUP_MISSES):
        await _miss_out(db, pid, await _issue(db, pid, session_id, "add_within_20", 0, seed=n))

    for _ in range(WARMUP_PROBLEMS):
        out = await service.next_problem(db, CATALOG, pid, session_id, expose_answers=True)
        assert isinstance(out, ProblemOut)
        assert out.skill_id == "add_within_10"
        inst = await db.get(ProblemInstance, out.problem_id)
        assert inst is not None and inst.warmup_for == "add_within_20"
        await service.submit_answer(
            db, POOL, CATALOG, pid, out.problem_id, out.dev_answer_latex or ""
        )
    back = await service.next_problem(db, CATALOG, pid, session_id)
    assert isinstance(back, ProblemOut) and back.skill_id == "add_within_20"
    inst = await db.get(ProblemInstance, back.problem_id)
    assert inst is not None and inst.warmup_for is None


async def test_three_misses_in_a_row_make_the_next_problem_a_tier_easier(
    db: AsyncSession,
) -> None:
    pid = await _player(db)
    await _only_ready(db, pid, "add_within_20")
    session_id = await _session(db, pid)
    for n in range(FRUSTRATION_MISSES):
        await _miss_out(db, pid, await _issue(db, pid, session_id, "add_within_20", 2, seed=n))
    tiers = CATALOG.source("add_within_20").tier_difficulties
    row = await mastery.get(db, pid, "add_within_20")
    assert row is not None
    row.rating = max(tiers) + 1.0  # strong enough that choose_tier picks the top tier
    await db.commit()
    assert choose_tier(SkillRating(rating=row.rating), tiers) == 2

    out = await service.next_problem(db, CATALOG, pid, session_id)
    assert isinstance(out, ProblemOut) and out.skill_id == "add_within_20"
    inst = await db.get(ProblemInstance, out.problem_id)
    assert inst is not None and inst.tier == 1
