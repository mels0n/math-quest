# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false
"""Adventure play loop: issue adaptive problems, check answers, update mastery.

Problems are stored as (skill, tier, seed) and regenerated on demand, so no answer
is ever persisted or sent before the problem is solved or out of tries.

A problem allows three tries. WRONG_FORM and UNREADABLE verdicts do not use one up.
Mastery changes once per problem: on the first correct answer (hints_used is the
number of earlier wrong tries) or on the third wrong one (scored incorrect).

Skill state machine, applied when a problem is scored:
- A skill with any scored problem that is not mastered is LEARNING.
- After the rating update, `is_mastered` against the top tier difficulty makes the
  skill MASTERED with `review_interval_days = next_review_days(None, True)` and
  `review_due_at = now + interval`.
- Scoring a skill that was already MASTERED: a wrong answer, or a correct one once the
  review is due, takes `next_review_days(previous, correct)` as the new interval (a wrong
  answer resets it to 1); a correct answer before the review is due leaves the schedule
  alone. If the new rating no longer satisfies `is_mastered`, the skill returns to
  LEARNING and its schedule is cleared.
- REVIEW_DUE is never stored. It is derived on read: a MASTERED row whose
  `review_due_at` has passed. The scheduler's mastered set is MASTERED plus REVIEW_DUE.

Row locks are always taken problem instance first, then skill_mastery, so concurrent
submissions cannot deadlock; the skill_mastery row is created with ON CONFLICT DO
NOTHING before it is locked.
"""

import logging
import secrets
import uuid
from datetime import UTC, datetime, timedelta
from typing import Literal

import sympy
from sqlalchemy.ext.asyncio import AsyncSession

from mathquest.engine.checker.bounded import CheckerPool
from mathquest.engine.checker.check import CheckResult, Verdict
from mathquest.engine.generators import get_generator
from mathquest.engine.mastery import (
    Outcome,
    SkillRating,
    SkillState,
    choose_tier,
    is_mastered,
    next_review_days,
    predict,
    update,
)
from mathquest.engine.scheduler import pick_skill
from mathquest.engine.skillgraph import SkillGraph
from mathquest.engine.types import Problem
from mathquest.entities import mastery, problems
from mathquest.entities.mastery import SkillMastery
from mathquest.features.play.schema import AnswerOut, MasteryOut, ProblemOut, SessionOut
from mathquest.shared.errors import NotFound

log = logging.getLogger(__name__)

MAX_ATTEMPTS = 3
STORED_LATEX_MAX = 200
MASTERY_TARGET = 0.9
_SEED_LIMIT = 2**62


def _now() -> datetime:
    return datetime.now(UTC)


def _rating(row: SkillMastery | None) -> SkillRating:
    if row is None:
        return SkillRating()
    return SkillRating(row.rating, row.attempts, tuple(row.recent))


def _top_difficulty(skill_id: str) -> float:
    return max(get_generator(skill_id).tier_difficulties)


def _mastery_out(skill_id: str, row: SkillMastery | None, now: datetime) -> MasteryOut:
    top = _top_difficulty(skill_id)
    if row is None or row.attempts == 0:
        state = SkillState.READY
    elif row.state == SkillState.MASTERED:
        due = row.review_due_at is not None and row.review_due_at <= now
        state = SkillState.REVIEW_DUE if due else SkillState.MASTERED
    else:
        state = SkillState.LEARNING
    if state in (SkillState.MASTERED, SkillState.REVIEW_DUE):
        progress = 1.0
    else:
        progress = min(1.0, max(0.0, predict(_rating(row).rating, top) / MASTERY_TARGET))
    return MasteryOut(skill_id=skill_id, state=state, progress=progress)


async def start_session(
    db: AsyncSession, player_id: uuid.UUID, mode: Literal["adventure"]
) -> SessionOut:
    row = await problems.add_session(db, player_id=player_id, mode=mode, started_at=_now())
    out = SessionOut(
        session_id=row.id, mode=mode, started_at=row.started_at, problem_count=row.problem_count
    )
    await db.commit()
    return out


async def next_problem(
    db: AsyncSession,
    graph: SkillGraph,
    player_id: uuid.UUID,
    session_id: uuid.UUID,
    *,
    expose_answers: bool = False,
) -> ProblemOut:
    session = await problems.lock_session(db, player_id, session_id)
    if session is None:
        raise NotFound()
    now = _now()
    rows = await mastery.list_for_player(db, player_id)
    ratings = {r.skill_id: _rating(r) for r in rows}
    mastered = {r.skill_id for r in rows if r.state == SkillState.MASTERED}
    due = await mastery.due_reviews(db, player_id, now)
    skill_id = pick_skill(graph, ratings, mastered, due, session.problem_count)
    generator = get_generator(skill_id)
    tier = choose_tier(ratings.get(skill_id, SkillRating()), generator.tier_difficulties)
    seed = secrets.randbelow(_SEED_LIMIT)
    problem = generator.generate(seed, tier)
    instance = await problems.add_problem(
        db,
        session_id=session_id,
        player_id=player_id,
        skill_id=skill_id,
        tier=tier,
        seed=seed,
        difficulty=problem.difficulty,
        issued_at=now,
    )
    session.problem_count += 1
    out = ProblemOut(
        problem_id=instance.id,
        skill_id=skill_id,
        skill_name=graph.skills[skill_id].name,
        prompt_latex=problem.prompt_latex,
        keypad=problem.keypad,
        dev_answer_latex=sympy.latex(problem.answer) if expose_answers else None,
    )
    await db.commit()
    return out


async def _check(
    pool: CheckerPool, problem_id: uuid.UUID, problem: Problem, latex: str
) -> CheckResult:
    try:
        return await pool.check(problem, latex)
    except Exception:
        log.warning("checker failed for problem %s", problem_id)
        return CheckResult(Verdict.UNREADABLE, None)


def _apply_score(
    row: SkillMastery, difficulty: float, outcome: Outcome, top: float, now: datetime
) -> None:
    after = update(_rating(row), difficulty, outcome)
    was_mastered = row.state == SkillState.MASTERED
    review_due = was_mastered and row.review_due_at is not None and row.review_due_at <= now
    row.rating = after.rating
    row.attempts = after.attempts
    row.recent = list(after.recent)
    row.updated_at = now
    if not is_mastered(after, top):
        row.state = SkillState.LEARNING
        row.review_interval_days = None
        row.review_due_at = None
        return
    row.state = SkillState.MASTERED
    if not was_mastered:
        interval = next_review_days(None, True)
    elif outcome.correct and not review_due and row.review_due_at is not None:
        return
    else:
        interval = next_review_days(row.review_interval_days, outcome.correct)
    row.review_interval_days = interval
    row.review_due_at = now + timedelta(days=interval)


async def submit_answer(
    db: AsyncSession,
    pool: CheckerPool,
    graph: SkillGraph,
    player_id: uuid.UUID,
    problem_id: uuid.UUID,
    latex: str,
) -> AnswerOut:
    instance = await problems.lock_problem(db, player_id, problem_id)
    if instance is None:
        raise NotFound()
    skill_id = instance.skill_id
    generator = get_generator(skill_id)
    problem = generator.generate(instance.seed, instance.tier)
    tried = await problems.consuming_attempts(db, instance.id)
    now = _now()

    if instance.answered_at is not None:
        last = tried[-1]
        out = AnswerOut(
            verdict=Verdict(last.verdict),
            misconception=last.misconception,
            solved=bool(instance.correct),
            attempts_left=max(0, MAX_ATTEMPTS - len(tried)),
            mastery=_mastery_out(skill_id, await mastery.get(db, player_id, skill_id), now),
            answer_latex=sympy.latex(problem.answer),
        )
        await db.commit()
        return out

    result = await _check(pool, instance.id, problem, latex)
    verdict = result.verdict
    misconception = result.misconception if verdict is Verdict.INCORRECT else None
    seconds = max(0.0, (now - instance.issued_at).total_seconds())
    await problems.add_attempt(
        db,
        problem_id=instance.id,
        player_id=player_id,
        latex=latex[:STORED_LATEX_MAX],
        verdict=verdict.value,
        misconception=misconception,
        seconds=seconds,
        at=now,
    )
    used = len(tried) + (1 if verdict in (Verdict.CORRECT, Verdict.INCORRECT) else 0)
    solved = verdict is Verdict.CORRECT
    scored = solved or (verdict is Verdict.INCORRECT and used >= MAX_ATTEMPTS)

    if scored:
        row = await mastery.lock(db, player_id, skill_id)
        outcome = Outcome(
            correct=solved,
            hints_used=len(tried),
            seconds=seconds,
            fluency=graph.skills[skill_id].fluency,
        )
        _apply_score(row, instance.difficulty, outcome, _top_difficulty(skill_id), now)
        instance.answered_at = now
        instance.correct = solved
    else:
        row = await mastery.get(db, player_id, skill_id)

    out = AnswerOut(
        verdict=verdict,
        misconception=misconception,
        solved=solved,
        attempts_left=MAX_ATTEMPTS - used,
        mastery=_mastery_out(skill_id, row, now),
        answer_latex=sympy.latex(problem.answer) if scored else None,
    )
    await db.commit()
    return out
