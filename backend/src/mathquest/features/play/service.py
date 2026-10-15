# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false
"""Adventure play loop: issue adaptive problems, check answers, update mastery.

Problems are stored as (skill, tier, seed) and regenerated on demand, so no answer
is ever persisted or sent before the problem is solved or out of tries.

A problem allows three tries. `attempts_left` (the hearts on the play screen) is
MAX_ATTEMPTS minus the tries used up by misses; a correct answer does not use one, so a
first-try solve still reports 3 and a wrong-then-right solve reports 2.

The first three WRONG_FORM or UNREADABLE verdicts on a problem are free; later ones use
up a try like INCORRECT does (the verdict returned is still WRONG_FORM or UNREADABLE).
Re-sending the previous wrong answer verbatim returns the stored result without using a
try. Input over 200 characters is UNREADABLE without reaching the checker. Mastery
changes once per problem: on the first correct answer (hints_used is the number of
tries used before it) or when the third try is used up (scored incorrect).

`total_solved` on every answer is the player's saved count of solved problems after
that answer, the same number `total_solved` returns for the header on any device.

Starting a new problem closes the session's unanswered ones (answered_at set, correct
NULL, no mastery change); answering a closed problem is a Conflict("problem_closed").

The checker runs with no transaction open. Submission is three steps: lock the problem,
read its state and commit; check the answer; lock the problem again, re-read its state
and write the result. A second request that scored the problem in between wins, and this
one returns the stored result. The CheckerPool owns logging of checker failures and
reports them as UNREADABLE, so this module does not wrap it.

Skill state machine, applied when a problem is scored:
- A skill's first rating is `initial_rating` (base difficulty + 1.0).
- A skill with any scored problem that is not mastered is LEARNING.
- The rating update is capped at the top tier difficulty + RATING_CAP_ABOVE_TOP.
- After the rating update, `is_mastered` against the top tier difficulty makes a
  LEARNING skill MASTERED, with `review_interval_days = next_review_days(None, True)`
  and `review_due_at = now + interval`. Only a correct answer does this: a wrong answer
  never promotes a skill.
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
    MASTERY_PREDICT,
    Outcome,
    SkillRating,
    SkillState,
    choose_tier,
    initial_rating,
    is_mastered,
    next_review_days,
    predict,
    update,
)
from mathquest.engine.scheduler import RUN_LENGTH, pick_skill
from mathquest.engine.skillgraph import SkillGraph
from mathquest.entities import mastery, problems
from mathquest.entities.mastery import SkillMastery
from mathquest.entities.problems import Attempt, ProblemInstance
from mathquest.features.play.schema import AnswerOut, MasteryOut, ProblemOut, SessionOut
from mathquest.shared.errors import Conflict, NotFound

MAX_ATTEMPTS = 3
FREE_VERDICTS = 3
STORED_LATEX_MAX = 200
# Room for a whole run plus the reviews (every fifth problem) that can sit inside it.
RECENT_LOOKBACK = RUN_LENGTH * 2 + 2
_SEED_LIMIT = 2**62
_FREE = (Verdict.WRONG_FORM.value, Verdict.UNREADABLE.value)


def _now() -> datetime:
    return datetime.now(UTC)


def _start_rating(skill_id: str) -> float:
    return initial_rating(get_generator(skill_id).tier_difficulties)


def _rating(row: SkillMastery | None, skill_id: str) -> SkillRating:
    if row is None:
        return SkillRating(rating=_start_rating(skill_id))
    recent = tuple((bool(e[0]), int(e[1])) for e in row.recent)
    return SkillRating(row.rating, row.attempts, recent)


def _top_difficulty(skill_id: str) -> float:
    return max(get_generator(skill_id).tier_difficulties)


def _top_tier(skill_id: str) -> int:
    return len(get_generator(skill_id).tier_difficulties) - 1


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
        progress = min(1.0, max(0.0, predict(_rating(row, skill_id).rating, top) / MASTERY_PREDICT))
    return MasteryOut(skill_id=skill_id, state=state, progress=progress)


async def total_solved(db: AsyncSession, player_id: uuid.UUID) -> int:
    """The player's saved count of solved problems; commits to end the read."""
    total = await problems.count_solved(db, player_id)
    await db.commit()
    return total


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
    await problems.close_open(db, session_id, now)
    rows = await mastery.list_for_player(db, player_id)
    by_skill = {r.skill_id: r for r in rows}
    ratings = {sid: _rating(by_skill.get(sid), sid) for sid in graph.skills}
    mastered = {r.skill_id for r in rows if r.state == SkillState.MASTERED}
    due = await mastery.due_reviews(db, player_id, now)
    recent = await problems.recent_skill_ids(db, session_id, limit=RECENT_LOOKBACK)
    skill_id = pick_skill(graph, ratings, mastered, due, session.problem_count, recent)
    generator = get_generator(skill_id)
    tier = choose_tier(ratings[skill_id], generator.tier_difficulties)
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


def _apply_score(
    row: SkillMastery, skill_id: str, difficulty: float, outcome: Outcome, now: datetime
) -> None:
    top = _top_difficulty(skill_id)
    after = update(_rating(row, skill_id), difficulty, outcome, top)
    was_mastered = row.state == SkillState.MASTERED
    review_due = was_mastered and row.review_due_at is not None and row.review_due_at <= now
    row.rating = after.rating
    row.attempts = after.attempts
    row.recent = [[int(correct), tier] for correct, tier in after.recent]
    row.updated_at = now
    mastered = is_mastered(after, top, _top_tier(skill_id))
    if not mastered or (not was_mastered and not outcome.correct):
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


def _tries_used(attempts: list[Attempt]) -> int:
    wrong = sum(1 for a in attempts if a.verdict == Verdict.INCORRECT.value)
    free = sum(1 for a in attempts if a.verdict in _FREE)
    return wrong + max(0, free - FREE_VERDICTS)


async def _load(
    db: AsyncSession, player_id: uuid.UUID, problem_id: uuid.UUID
) -> tuple[ProblemInstance, list[Attempt]]:
    """Lock the problem and read its attempts; a closed problem is a Conflict."""
    instance = await problems.lock_problem(db, player_id, problem_id)
    if instance is None:
        raise NotFound()
    if instance.answered_at is not None and instance.correct is None:
        raise Conflict("problem_closed")
    return instance, await problems.attempts_for(db, instance.id)


async def _stored(
    db: AsyncSession,
    instance: ProblemInstance,
    attempts: list[Attempt],
    answer_latex: str | None,
    now: datetime,
) -> AnswerOut:
    """The result already on record for this problem; commits to release the lock."""
    last = attempts[-1]
    used = _tries_used(attempts)
    row = await mastery.get(db, instance.player_id, instance.skill_id)
    out = AnswerOut(
        verdict=Verdict(last.verdict),
        misconception=last.misconception,
        solved=bool(instance.correct),
        attempts_left=max(0, MAX_ATTEMPTS - used),
        mastery=_mastery_out(instance.skill_id, row, now),
        answer_latex=answer_latex,
        total_solved=await problems.count_solved(db, instance.player_id),
    )
    await db.commit()
    return out


def _repeat_of_last_wrong(attempts: list[Attempt], latex: str) -> bool:
    return bool(
        attempts
        and attempts[-1].verdict == Verdict.INCORRECT.value
        and attempts[-1].latex == latex[:STORED_LATEX_MAX]
    )


async def submit_answer(
    db: AsyncSession,
    pool: CheckerPool,
    graph: SkillGraph,
    player_id: uuid.UUID,
    problem_id: uuid.UUID,
    latex: str,
) -> AnswerOut:
    received = _now()
    instance, attempts = await _load(db, player_id, problem_id)
    skill_id = instance.skill_id
    problem = get_generator(skill_id).generate(instance.seed, instance.tier)
    answer_latex = str(sympy.latex(problem.answer))
    if instance.answered_at is not None:
        return await _stored(db, instance, attempts, answer_latex, received)
    if _repeat_of_last_wrong(attempts, latex):
        return await _stored(db, instance, attempts, None, received)
    await db.commit()

    if len(latex) > STORED_LATEX_MAX:
        result = CheckResult(Verdict.UNREADABLE, None)
    else:
        result = await pool.check(problem, latex)

    instance, attempts = await _load(db, player_id, problem_id)
    if instance.answered_at is not None:
        return await _stored(db, instance, attempts, answer_latex, received)
    if _repeat_of_last_wrong(attempts, latex):
        return await _stored(db, instance, attempts, None, received)

    verdict = result.verdict
    misconception = result.misconception if verdict is Verdict.INCORRECT else None
    seconds = max(0.0, (received - instance.issued_at).total_seconds())
    tried = _tries_used(attempts)
    solved = verdict is Verdict.CORRECT
    attempt = await problems.add_attempt(
        db,
        problem_id=instance.id,
        player_id=player_id,
        latex=latex[:STORED_LATEX_MAX],
        verdict=verdict.value,
        misconception=misconception,
        seconds=seconds,
        at=received,
    )
    used = _tries_used([*attempts, attempt])
    scored = solved or used >= MAX_ATTEMPTS

    if scored:
        row = await mastery.lock(db, player_id, skill_id, _start_rating(skill_id))
        outcome = Outcome(
            correct=solved,
            hints_used=tried,
            seconds=seconds,
            fluency=graph.skills[skill_id].fluency,
            tier=instance.tier,
        )
        _apply_score(row, skill_id, instance.difficulty, outcome, received)
        instance.answered_at = received
        instance.correct = solved
    else:
        row = await mastery.get(db, player_id, skill_id)

    out = AnswerOut(
        verdict=verdict,
        misconception=misconception,
        solved=solved,
        attempts_left=MAX_ATTEMPTS - used,
        mastery=_mastery_out(skill_id, row, received),
        answer_latex=answer_latex if scored else None,
        total_solved=await problems.count_solved(db, player_id),
    )
    await db.commit()
    return out
