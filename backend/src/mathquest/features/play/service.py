# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false
"""Adventure play loop: issue adaptive problems, check answers, update mastery.

Problems are stored as (skill, tier, seed, variant, template_id) and regenerated on
demand, so no answer is ever persisted or sent before the problem is solved or out of
tries. The variant ("bare", "word" or "bank") is a seeded draw from the skill's
word_share and bank_share (see `variants`); the template or bank item is picked by the
seed too, and its id is stored. A word problem keeps the generator's answer unless its
template computes one from an expression. If a stored template or item no longer exists
(removed from the content pack, say), regeneration falls back to the bare problem.
A bank item carries its own answer, so a problem issued from a bank item that is gone is
stale: answering it closes it as Conflict("problem_closed"), and the client moves on to
the next problem. Shipped bank items are never edited in place (ADR-0012), so an item
that still exists is the one the learner saw. If rendering a word or bank variant fails
when a problem is issued (a template that breaks for this seed), the failure is logged
and the problem is issued and stored as the bare variant instead.

Seeds are drawn below 2**53, so they survive a round trip through JavaScript numbers.

A bank item can be multiple choice. Its problem is answered with a choice index, never
LaTeX: sending LaTeX to a choice problem, a choice to any other problem, or an index
outside the shown choices is Invalid (422) and records nothing. A choice attempt is
stored in the attempts table's latex column as `choice:<index>`; a choice problem only
ever stores that form, and the answer route rejects typed LaTeX that starts with
`choice:`, so no other problem ever does and the column stays unambiguous. When a choice
problem is scored, `answer_choice` reveals the right index instead of `answer_latex`.

A typed problem allows three tries (MAX_ATTEMPTS); a choice problem allows two
(MAX_CHOICE_ATTEMPTS), since with three or more choices a third try would be a free
guess. `attempts_left` (the hearts on the play screen) is the problem's allowance minus
the tries used up by misses; a correct answer does not use one, so a first-try solve of
a typed problem still reports 3 and a wrong-then-right solve reports 2.

The first three WRONG_FORM or UNREADABLE verdicts on a problem are free; later ones use
up a try like INCORRECT does (the verdict returned is still WRONG_FORM or UNREADABLE).
Re-sending the previous wrong answer verbatim returns the stored result without using a
try. Input over 200 characters is UNREADABLE without reaching the checker. Mastery
changes once per problem: on the first correct answer or when the last try is used up
(scored incorrect).

Hint credit: a correct answer is scored as if it took `help_used(wrong tries before it,
hint levels viewed + explanations viewed)` hints, added and capped at 3, so the score is
`max(0.25, 1 - 0.25 * help)`: every wrong try, hint level and explanation costs a
quarter, and a solve after the full worked example (level 3) still counts as a hinted
solve worth a quarter. Hints and explanations are shown by the teaching slice, which
counts hints in the problem's `hints_used` and records each explanation in
`explanation_views`, both under the problem's row lock; this module only reads them.

Feedback: an INCORRECT answer carries `feedback`. A mistake the checker recognised gets
the skill's feedback for it, rendered with the problem's numbers; otherwise an open
problem gets a short generic line ("hint" while a hint is left to ask for, else
"retry"), and a problem just scored wrong gets none (its answer is revealed). Hints,
explanations and feedback are only offered for a problem that shows the generator's
numbers and answer (`SkillSource.shows_generator`): never for a bank item or a word
problem that computes its own answer. A problem scored wrong after every explanation of
its skill was shown in this session (explanations are shown by the teaching slice and
recorded in `explanation_views`) records a stuck event with its wrong answers.

The skill is chosen by `scheduler.plan_next` from the session's history, which can insert
a short warm-up on a weaker prerequisite (stored as `warmup_for`), and the tier by
`choose_tier` lowered by `scheduler.guard_tier` after three misses in a row.

Before the first problem of a skill that has a lesson, `next` returns a lesson to show
(only to a client that asked for lessons with `offer_lessons`; an older client that
cannot show one gets the problem)
instead of a problem (the skill and its name, no problem issued, the session's count
unchanged) until the player has marked that lesson seen (`lessons_seen`, written by the
teaching slice). A skill with a scored problem never gets one, so a player who practiced
it before lessons existed is not interrupted. Skill choice depends only on stored
state, so the `next` after the lesson picks the same skill and issues its problem.

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
- REVIEW_DUE is never stored. It is derived on read: a MASTERED or PROVISIONAL row
  whose `review_due_at` has passed. The scheduler's mastered set is MASTERED plus REVIEW_DUE
  plus PROVISIONAL.
- PROVISIONAL is written by placement (docs/adr/0015-placement.md): the skill counts as
  mastered and is due for review a day later. Its first scored problem that can confirm
  it (`_confirms`: a generator problem, not a bank item, at the placement probe's tier
  or above; a provisional skill's problems are issued that way) decides it: a correct
  answer makes it MASTERED with `placed` set and the normal first review interval; a
  wrong one makes it LEARNING. A correct answer on a problem that cannot confirm it
  leaves it provisional and due. Its lesson is never offered before that review, since
  placement found the learner already knows it.
- A `placed` MASTERED skill (`placed_keeps_mastery`) stays mastered on a correct answer
  even while `is_mastered` does not yet hold, and survives its first miss in the recent
  window with its review interval reset; a second miss in the window reverts it. Once
  `is_mastered` holds, `placed` is cleared and the normal rule applies.

Sessions (docs/adr/0016-practice-and-sessions.md). An adventure session lasts
SESSION_PROBLEMS problems: once that many were issued, `next` ends it and returns its
summary instead of a problem (only to a client that asked for summaries with
`offer_summary`; an older client keeps getting problems, as before sessions had an end).
`end_session` ends a session early and returns the same summary, and again for a session
already ended. `next` on an ended session is a Conflict("session_ended"). Ending a
session closes its open problems. The summary lists the skills with a scored problem in
the session, those that became mastered from learning in it (`newly_mastered` on the
problem that did it) and are still mastered, the problems solved and scored, and the time
from the first problem issued to the last answer received.

A practice session works on its `focus`: one skill the player picked (ready, learning,
provisional or mastered; a locked one is a Conflict("skill_locked")), or "my weak spots",
the WEAK_SPOTS learning skills with the lowest progress followed by the due reviews (none
of either is a Conflict("no_weak_spots")). The skill comes from `scheduler.plan_practice`;
lessons, hints, explanations, warm-ups and the frustration guard work as in an adventure.
A practice session has no set length and no review slots. It is untimed: a fluency
skill's speed does not change the score. The first scored problem of a focus skill that
was mastered (not provisional) when the session started, and still is, records a
revisit event (one per session and skill); a skill mastered or confirmed during the
session is not a revisit.

Row locks are always taken problem instance first, then skill_mastery, so concurrent
submissions cannot deadlock; the skill_mastery row is created with ON CONFLICT DO
NOTHING before it is locked.
"""

import logging
import secrets
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Literal

from sqlalchemy.ext.asyncio import AsyncSession

from mathquest.engine.catalog import Catalog
from mathquest.engine.checker.bounded import CheckerPool
from mathquest.engine.checker.check import (
    AnswerKindError,
    CheckResult,
    Verdict,
    check_answer_kind,
    check_choice,
)
from mathquest.engine.limits import (
    MAX_ATTEMPTS,
    MAX_CHOICE_ATTEMPTS,
    SEED_LIMIT,
    STORED_LATEX_MAX,
)
from mathquest.engine.mastery import (
    MASTERY_PREDICT,
    Outcome,
    SkillRating,
    SkillState,
    choose_tier,
    help_used,
    initial_rating,
    is_mastered,
    next_review_days,
    placed_keeps_mastery,
    predict,
    update,
)
from mathquest.engine.placement import probe_tier
from mathquest.engine.scheduler import (
    SESSION_PROBLEMS,
    Pick,
    Played,
    guard_tier,
    plan_next,
    plan_practice,
)
from mathquest.engine.teaching import all_approaches_shown, answer_feedback, hint_count
from mathquest.engine.templates import TemplateError
from mathquest.engine.transport import (
    FeedbackOut,
    answer_latex,
    feedback_out,
    keypad_for,
    prompt_out,
)
from mathquest.engine.types import Problem
from mathquest.entities import lessons, mastery, problems, teaching
from mathquest.entities.mastery import SkillMastery
from mathquest.entities.problems import Attempt, PlaySession, ProblemInstance
from mathquest.features.play.schema import (
    AnswerOut,
    LessonDueOut,
    MasteryOut,
    ProblemOut,
    RegionOut,
    SessionOut,
    SkillNameOut,
    SkillOut,
    SkillsOut,
    SummaryOut,
)
from mathquest.features.play.variants import choose_variant
from mathquest.shared.errors import Conflict, Invalid, NotFound

FREE_VERDICTS = 3
WEAK_SPOTS = 3
"""Learning skills in "my weak spots", the ones with the lowest progress."""
PRACTICE = "practice"
CHOICE_PREFIX = "choice:"
_FREE = (Verdict.WRONG_FORM.value, Verdict.UNREADABLE.value)


log = logging.getLogger(__name__)


def _now() -> datetime:
    return datetime.now(UTC)


def _start_rating(catalog: Catalog, skill_id: str) -> float:
    return initial_rating(catalog.source(skill_id).tier_difficulties)


def _rating(catalog: Catalog, row: SkillMastery | None, skill_id: str) -> SkillRating:
    if row is None:
        return SkillRating(rating=_start_rating(catalog, skill_id))
    recent = tuple((bool(e[0]), int(e[1])) for e in row.recent)
    return SkillRating(row.rating, row.attempts, recent)


def _top_difficulty(catalog: Catalog, skill_id: str) -> float:
    return max(catalog.source(skill_id).tier_difficulties)


def _top_tier(catalog: Catalog, skill_id: str) -> int:
    return len(catalog.source(skill_id).tier_difficulties) - 1


@dataclass(frozen=True)
class _Reveal:
    """The right answer, sent once a problem is scored."""

    latex: str | None
    choice: int | None


def _mastery_out(
    catalog: Catalog, skill_id: str, row: SkillMastery | None, now: datetime
) -> MasteryOut:
    top = _top_difficulty(catalog, skill_id)
    if row is not None and row.state == SkillState.PROVISIONAL:
        # Past its review date it reads as due, like a mastered skill, so it counts
        # toward "my weak spots".
        due = row.review_due_at is not None and row.review_due_at <= now
        state = SkillState.REVIEW_DUE if due else SkillState.PROVISIONAL
    elif row is None or row.attempts == 0:
        state = SkillState.READY
    elif row.state == SkillState.MASTERED:
        due = row.review_due_at is not None and row.review_due_at <= now
        state = SkillState.REVIEW_DUE if due else SkillState.MASTERED
    else:
        state = SkillState.LEARNING
    if state in (SkillState.MASTERED, SkillState.REVIEW_DUE, SkillState.PROVISIONAL):
        progress = 1.0
    else:
        rating = _rating(catalog, row, skill_id).rating
        progress = min(1.0, max(0.0, predict(rating, top) / MASTERY_PREDICT))
    return MasteryOut(skill_id=skill_id, state=state, progress=progress)


async def total_solved(db: AsyncSession, player_id: uuid.UUID) -> int:
    """The player's saved count of solved problems; commits to end the read."""
    total = await problems.count_solved(db, player_id)
    await db.commit()
    return total


def _names(catalog: Catalog, skill_ids: list[str]) -> list[SkillNameOut]:
    """Names of the skills still in the pack, in the given order."""
    skills = catalog.graph.skills
    return [SkillNameOut(skill_id=sid, name=skills[sid].name) for sid in skill_ids if sid in skills]


def _session_out(catalog: Catalog, row: PlaySession) -> SessionOut:
    return SessionOut(
        session_id=row.id,
        mode=PRACTICE if row.mode == PRACTICE else "adventure",
        started_at=row.started_at,
        problem_count=row.problem_count,
        focus=_names(catalog, list(row.focus or [])),
    )


async def start_session(
    db: AsyncSession, player_id: uuid.UUID, mode: Literal["adventure"]
) -> SessionOut:
    row = await problems.add_session(db, player_id=player_id, mode=mode, started_at=_now())
    out = SessionOut(
        session_id=row.id, mode=mode, started_at=row.started_at, problem_count=row.problem_count
    )
    await db.commit()
    return out


def _state(
    catalog: Catalog, skill_id: str, row: SkillMastery | None, ready: set[str], now: datetime
) -> MasteryOut:
    """The skill's state as the player sees it; READY only when it can be played."""
    out = _mastery_out(catalog, skill_id, row, now)
    if out.state is SkillState.READY and skill_id not in ready:
        return MasteryOut(skill_id=skill_id, state=SkillState.LOCKED, progress=0.0)
    return out


async def _player_states(
    db: AsyncSession, catalog: Catalog, player_id: uuid.UUID, now: datetime
) -> dict[str, MasteryOut]:
    rows = {r.skill_id: r for r in await mastery.list_for_player(db, player_id)}
    mastered = {sid for sid, r in rows.items() if r.state in mastery.COUNTS_AS_MASTERED}
    # A skill implied by what the learner has mastered is open to practice, not offered.
    ready = set(catalog.graph.ready(mastered, set(rows))) | catalog.graph.implied(mastered)
    return {
        sid: _state(catalog, sid, rows.get(sid), ready, now) for sid in catalog.graph.topo_order()
    }


async def list_skills(db: AsyncSession, catalog: Catalog, player_id: uuid.UUID) -> SkillsOut:
    """Every skill with the player's state of it, for the practice picker; regions
    without skills are left out."""
    states = await _player_states(db, catalog, player_id, _now())
    await db.commit()
    graph = catalog.graph
    regions = sorted(catalog.pack.world.regions, key=lambda r: r.order)
    order = {r.id: i for i, r in enumerate(regions)}
    skills = sorted(states, key=lambda sid: order.get(graph.skills[sid].region, len(order)))
    return SkillsOut(
        regions=[
            RegionOut(id=r.id, name=r.name)
            for r in regions
            if any(graph.skills[sid].region == r.id for sid in skills)
        ],
        skills=[
            SkillOut(
                skill_id=sid,
                name=graph.skills[sid].name,
                region=graph.skills[sid].region,
                state=states[sid].state,
                progress=states[sid].progress,
                has_lesson=sid in catalog.pack.lessons,
            )
            for sid in skills
        ],
    )


async def _weak_spots(
    db: AsyncSession, player_id: uuid.UUID, states: dict[str, MasteryOut], now: datetime
) -> list[str]:
    learning = [s for s in states.values() if s.state is SkillState.LEARNING]
    order = {sid: i for i, sid in enumerate(states)}
    weakest = sorted(learning, key=lambda s: (s.progress, order[s.skill_id]))
    focus = [s.skill_id for s in weakest[:WEAK_SPOTS]]
    for sid in await mastery.due_reviews(db, player_id, now):
        if sid in states and sid not in focus:
            focus.append(sid)
    return focus


async def start_practice(
    db: AsyncSession,
    catalog: Catalog,
    player_id: uuid.UUID,
    *,
    skill_id: str | None = None,
    weak_spots: bool = False,
) -> SessionOut:
    """A practice session on ``skill_id``, or on the player's weak spots."""
    if (skill_id is None) == (not weak_spots):
        raise Invalid("skill_or_weak_spots")
    now = _now()
    states = await _player_states(db, catalog, player_id, now)
    if skill_id is not None:
        if skill_id not in states:
            raise NotFound()
        if states[skill_id].state is SkillState.LOCKED:
            raise Conflict("skill_locked")
        focus = [skill_id]
    else:
        focus = await _weak_spots(db, player_id, states, now)
        if not focus:
            raise Conflict("no_weak_spots")
    rows = {r.skill_id: r for r in await mastery.list_for_player(db, player_id)}
    mastered = [sid for sid in focus if sid in rows and rows[sid].state == SkillState.MASTERED]
    row = await problems.add_session(
        db,
        player_id=player_id,
        mode=PRACTICE,
        started_at=now,
        focus=focus,
        mastered_at_start=mastered,
    )
    out = _session_out(catalog, row)
    await db.commit()
    return out


async def _summary(
    db: AsyncSession, catalog: Catalog, player_id: uuid.UUID, session: PlaySession
) -> SummaryOut:
    issued = await problems.session_problems(db, session.id)
    last = await problems.last_answer_at(db, session.id)
    rows = {r.skill_id: r for r in await mastery.list_for_player(db, player_id)}
    practiced: list[str] = []
    mastered: list[str] = []
    for skill_id, correct, newly, _at in issued:
        if correct is not None and skill_id not in practiced:
            practiced.append(skill_id)
        row = rows.get(skill_id)
        still = row is not None and row.state == SkillState.MASTERED
        if newly and still and skill_id not in mastered:
            mastered.append(skill_id)
    scored = sum(1 for _s, correct, _n, _a in issued if correct is not None)
    solved = sum(1 for _s, correct, _n, _a in issued if correct)
    seconds = 0
    if issued and last is not None:
        seconds = max(0, round((last - issued[0][3]).total_seconds()))
    return SummaryOut(
        session_id=session.id,
        mode=PRACTICE if session.mode == PRACTICE else "adventure",
        skills_practiced=_names(catalog, practiced),
        newly_mastered=_names(catalog, mastered),
        problems_solved=solved,
        problems_scored=scored,
        accuracy=solved / scored if scored else None,
        seconds=seconds,
    )


async def _finish(
    db: AsyncSession, catalog: Catalog, player_id: uuid.UUID, session: PlaySession, now: datetime
) -> SummaryOut:
    """End the session (closing its open problems) and summarise it; commits."""
    if session.ended_at is None:
        await problems.close_open(db, session.id, now)
        session.ended_at = now
    out = await _summary(db, catalog, player_id, session)
    await db.commit()
    return out


async def end_session(
    db: AsyncSession, catalog: Catalog, player_id: uuid.UUID, session_id: uuid.UUID
) -> SummaryOut:
    """End a session now and return its summary (again, for one already ended)."""
    session = await problems.lock_session(db, player_id, session_id)
    if session is None:
        raise NotFound()
    return await _finish(db, catalog, player_id, session, _now())


async def _lesson_due(
    db: AsyncSession,
    catalog: Catalog,
    player_id: uuid.UUID,
    skill_id: str,
    row: SkillMastery | None,
) -> bool:
    """The skill has a lesson the player has not seen, no problem of it is scored yet,
    and placement has not marked it provisionally mastered."""
    if skill_id not in catalog.pack.lessons:
        return False
    if row is not None and (row.attempts > 0 or row.state == SkillState.PROVISIONAL):
        return False
    return not await lessons.has_seen(db, player_id, skill_id)


async def next_problem(
    db: AsyncSession,
    catalog: Catalog,
    player_id: uuid.UUID,
    session_id: uuid.UUID,
    *,
    expose_answers: bool = False,
    offer_lessons: bool = True,
    offer_summary: bool = False,
) -> ProblemOut | LessonDueOut | SummaryOut:
    """The next problem, or the lesson to show first when ``offer_lessons`` (clients
    that do not understand lessons get the problem), or the summary once an adventure
    has had SESSION_PROBLEMS problems when ``offer_summary``."""
    session = await problems.lock_session(db, player_id, session_id)
    if session is None:
        raise NotFound()
    if session.ended_at is not None:
        raise Conflict("session_ended")
    now = _now()
    practice = session.mode == PRACTICE
    if offer_summary and not practice and session.problem_count >= SESSION_PROBLEMS:
        return await _finish(db, catalog, player_id, session, now)
    await problems.close_open(db, session_id, now)
    rows = await mastery.list_for_player(db, player_id)
    by_skill = {r.skill_id: r for r in rows}
    graph = catalog.graph
    ratings = {sid: _rating(catalog, by_skill.get(sid), sid) for sid in graph.skills}
    mastered = {r.skill_id for r in rows if r.state in mastery.COUNTS_AS_MASTERED}
    # A skill missing from the pack (a release rolled back) is neither reviewed nor picked.
    due = [sid for sid in await mastery.due_reviews(db, player_id, now) if sid in graph.skills]
    history = [
        Played(skill_id=sid, correct=correct, stuck=stuck, warmup_for=warmup_for)
        for sid, correct, stuck, warmup_for in await problems.session_history(db, session_id)
    ]
    pick: Pick
    if practice:
        pick = plan_practice(graph, ratings, list(session.focus or []), history)
    else:
        pick = plan_next(
            graph, ratings, mastered, due, session.problem_count, history, set(by_skill)
        )
    skill_id = pick.skill_id
    if offer_lessons and await _lesson_due(
        db, catalog, player_id, skill_id, by_skill.get(skill_id)
    ):
        await db.commit()
        return LessonDueOut(skill_id=skill_id, skill_name=graph.skills[skill_id].name)
    source = catalog.source(skill_id)
    tier = guard_tier(choose_tier(ratings[skill_id], source.tier_difficulties), history, skill_id)
    seed = secrets.randbelow(SEED_LIMIT)
    variant = choose_variant(source, seed, tier)
    row = by_skill.get(skill_id)
    if row is not None and row.state == SkillState.PROVISIONAL:
        # A problem that can confirm placement's mark: the generator's, at its tier.
        tier = max(tier, probe_tier(graph.skills[skill_id]))
        if graph.skills[skill_id].keypad != "choice":
            variant = "bare"
    try:
        problem = source.generate(seed, tier, variant)
    except TemplateError:
        log.exception(
            "%s variant of %s failed for seed %d; issuing it bare", variant, skill_id, seed
        )
        problem = source.generate(seed, tier)
    instance = await problems.add_problem(
        db,
        session_id=session_id,
        player_id=player_id,
        skill_id=skill_id,
        tier=tier,
        seed=seed,
        variant=problem.variant,
        template_id=problem.template_id,
        difficulty=problem.difficulty,
        issued_at=now,
        warmup_for=pick.warmup_for,
    )
    session.problem_count += 1
    teachable = source.shows_generator(problem)
    out = ProblemOut(
        problem_id=instance.id,
        skill_id=skill_id,
        skill_name=graph.skills[skill_id].name,
        prompt=prompt_out(problem.prompt),
        keypad=keypad_for(problem, graph.skills[skill_id].keypad),
        choices=None if problem.choices is None else [prompt_out(c) for c in problem.choices],
        has_lesson=skill_id in catalog.pack.lessons,
        hint_levels=hint_count(catalog.pack, skill_id) if teachable else 0,
        has_explanations=teachable and skill_id in catalog.pack.explanations,
        dev_answer_latex=answer_latex(problem) if expose_answers else None,
        dev_answer_choice=problem.correct_choice if expose_answers else None,
    )
    await db.commit()
    return out


def _confirms(catalog: Catalog, skill_id: str, variant: str, tier: int) -> bool:
    """Whether a correct answer on this problem can confirm a provisional skill: the
    generator's problem (a skill answered only by choices has only bank items) at the
    placement probe's tier or above."""
    skill = catalog.graph.skills[skill_id]
    generator = variant != "bank" or skill.keypad == "choice"
    return generator and tier >= probe_tier(skill)


def _apply_score(
    catalog: Catalog,
    row: SkillMastery,
    skill_id: str,
    difficulty: float,
    outcome: Outcome,
    now: datetime,
    *,
    confirms: bool = True,
) -> bool:
    """Apply a scored outcome to the skill; True when it became mastered from learning.

    ``confirms`` says whether the problem can confirm a provisional skill: a generator
    problem (not a bank item) at the placement probe's tier or above."""
    top = _top_difficulty(catalog, skill_id)
    top_tier = _top_tier(catalog, skill_id)
    after = update(_rating(catalog, row, skill_id), difficulty, outcome, top)
    was_mastered = row.state == SkillState.MASTERED
    was_provisional = row.state == SkillState.PROVISIONAL
    review_due = was_mastered and row.review_due_at is not None and row.review_due_at <= now
    row.rating = after.rating
    row.attempts = after.attempts
    row.recent = [[int(correct), tier] for correct, tier in after.recent]
    row.updated_at = now
    if was_provisional and outcome.correct and not confirms:
        # Right, but on a problem that cannot confirm it: stays provisional and due.
        return False
    by_rating = is_mastered(after, top, top_tier)
    if was_provisional:
        mastered = outcome.correct
        row.placed = outcome.correct and not by_rating
    elif was_mastered and row.placed:
        mastered = by_rating or placed_keeps_mastery(after, outcome.correct)
        row.placed = mastered and not by_rating
    else:
        mastered = by_rating
    if not mastered or (not was_mastered and not was_provisional and not outcome.correct):
        row.state = SkillState.LEARNING
        row.placed = False
        row.review_interval_days = None
        row.review_due_at = None
        return False
    row.state = SkillState.MASTERED
    if not was_mastered:
        interval = next_review_days(None, True)
    elif outcome.correct and not review_due and row.review_due_at is not None:
        return False
    else:
        interval = next_review_days(row.review_interval_days, outcome.correct)
    row.review_interval_days = interval
    row.review_due_at = now + timedelta(days=interval)
    return not was_mastered and not was_provisional


def regenerate(catalog: Catalog, instance: ProblemInstance) -> Problem:
    """The issued problem again, from its stored seed, tier, variant and template."""
    try:
        return catalog.regenerate(
            instance.skill_id, instance.seed, instance.tier, instance.variant, instance.template_id
        )
    except KeyError:
        # Issued for a skill the pack no longer has: closed, and the client moves on.
        raise Conflict("problem_closed") from None


def _allowed(problem: Problem) -> int:
    return MAX_CHOICE_ATTEMPTS if problem.choices is not None else MAX_ATTEMPTS


def _stale(instance: ProblemInstance, problem: Problem) -> bool:
    """Issued from a bank item that no longer exists, so its answer is unknown."""
    return instance.variant == "bank" and problem.variant != "bank"


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


def _feedback(
    catalog: Catalog,
    instance: ProblemInstance,
    problem: Problem,
    verdict: Verdict,
    misconception: str | None,
    scored: bool,
) -> FeedbackOut | None:
    """Teaching feedback after an incorrect answer (see ``engine.teaching.answer_feedback``)."""
    if verdict is not Verdict.INCORRECT:
        return None
    source = catalog.source(instance.skill_id)
    teachable = source.shows_generator(problem)
    hint_available = teachable and instance.hints_used < hint_count(catalog.pack, instance.skill_id)
    shown = answer_feedback(
        catalog.pack.explanations.get(instance.skill_id) if teachable else None,
        problem,
        misconception,
        scored=scored,
        hint_available=hint_available,
    )
    return feedback_out(shown)


async def _record_stuck(
    db: AsyncSession,
    catalog: Catalog,
    instance: ProblemInstance,
    problem: Problem,
    attempts: list[Attempt],
    now: datetime,
) -> None:
    """Record a stuck event when every explanation of the skill was shown in this session.

    Only for a problem that shows the generator's numbers and answer, so the event's
    (generator, tier, seed) is exactly the problem the learner saw."""
    explanations = catalog.pack.explanations.get(instance.skill_id)
    if explanations is None or not catalog.source(instance.skill_id).shows_generator(problem):
        return
    shown = await teaching.approaches_shown(db, instance.session_id, instance.skill_id)
    if not all_approaches_shown(len(explanations.approaches), shown):
        return
    await teaching.add_stuck(
        db,
        player_id=instance.player_id,
        problem_id=instance.id,
        skill_id=instance.skill_id,
        generator=catalog.source(instance.skill_id).generator.generator_id,
        tier=instance.tier,
        seed=instance.seed,
        wrong_answers=[
            a.latex[:STORED_LATEX_MAX] for a in attempts if a.verdict == Verdict.INCORRECT.value
        ],
        created_at=now,
    )


async def _stored(
    db: AsyncSession,
    catalog: Catalog,
    instance: ProblemInstance,
    problem: Problem,
    attempts: list[Attempt],
    reveal: _Reveal | None,
    now: datetime,
    allowed: int,
) -> AnswerOut:
    """The result already on record for this problem; commits to release the lock."""
    last = attempts[-1]
    used = _tries_used(attempts)
    row = await mastery.get(db, instance.player_id, instance.skill_id)
    verdict = Verdict(last.verdict)
    scored = instance.answered_at is not None
    out = AnswerOut(
        verdict=verdict,
        misconception=last.misconception,
        feedback=_feedback(catalog, instance, problem, verdict, last.misconception, scored),
        solved=bool(instance.correct),
        attempts_left=max(0, allowed - used),
        mastery=_mastery_out(catalog, instance.skill_id, row, now),
        answer_latex=reveal.latex if reveal else None,
        answer_choice=reveal.choice if reveal else None,
        total_solved=await problems.count_solved(db, instance.player_id),
    )
    await db.commit()
    return out


def _repeat_of_last_wrong(attempts: list[Attempt], given: str) -> bool:
    return bool(
        attempts
        and attempts[-1].verdict == Verdict.INCORRECT.value
        and attempts[-1].latex == given[:STORED_LATEX_MAX]
    )


def _given(problem: Problem, latex: str | None, choice: int | None) -> str:
    """The answer as stored: the LaTeX, or `choice:<index>` for a choice problem. An
    answer of the wrong kind is Invalid."""
    try:
        check_answer_kind(problem, latex, choice)
    except AnswerKindError as err:
        raise Invalid(err.code) from None
    return latex if latex is not None else f"{CHOICE_PREFIX}{choice}"


async def submit_answer(
    db: AsyncSession,
    pool: CheckerPool,
    catalog: Catalog,
    player_id: uuid.UUID,
    problem_id: uuid.UUID,
    latex: str | None = None,
    *,
    choice: int | None = None,
) -> AnswerOut:
    """Score one answer: ``latex`` for a typed answer, ``choice`` for a choice problem."""
    received = _now()
    instance, attempts = await _load(db, player_id, problem_id)
    skill_id = instance.skill_id
    problem = regenerate(catalog, instance)
    if _stale(instance, problem):
        if instance.answered_at is None:
            instance.answered_at = received
            await db.commit()
        raise Conflict("problem_closed")
    given = _given(problem, latex, choice)
    reveal = _Reveal(answer_latex(problem), problem.correct_choice)
    allowed = _allowed(problem)
    if instance.answered_at is not None:
        return await _stored(db, catalog, instance, problem, attempts, reveal, received, allowed)
    if _repeat_of_last_wrong(attempts, given):
        return await _stored(db, catalog, instance, problem, attempts, None, received, allowed)
    await db.commit()

    if choice is not None:
        result = check_choice(problem, choice)
    elif len(given) > STORED_LATEX_MAX:
        result = CheckResult(Verdict.UNREADABLE, None)
    else:
        result = await pool.check(problem, given)

    instance, attempts = await _load(db, player_id, problem_id)
    if instance.answered_at is not None:
        return await _stored(db, catalog, instance, problem, attempts, reveal, received, allowed)
    if _repeat_of_last_wrong(attempts, given):
        return await _stored(db, catalog, instance, problem, attempts, None, received, allowed)

    verdict = result.verdict
    misconception = result.misconception if verdict is Verdict.INCORRECT else None
    seconds = max(0.0, (received - instance.issued_at).total_seconds())
    tried = _tries_used(attempts)
    solved = verdict is Verdict.CORRECT
    attempt = await problems.add_attempt(
        db,
        problem_id=instance.id,
        player_id=player_id,
        latex=given[:STORED_LATEX_MAX],
        verdict=verdict.value,
        misconception=misconception,
        seconds=seconds,
        at=received,
    )
    used = _tries_used([*attempts, attempt])
    scored = solved or used >= allowed

    if scored:
        session = await problems.get_session(db, instance.session_id)
        practice = session.mode == PRACTICE
        row = await mastery.lock(db, player_id, skill_id, _start_rating(catalog, skill_id))
        if (
            practice
            and skill_id in (session.mastered_at_start or [])
            and row.state == SkillState.MASTERED
        ):
            await problems.add_revisit(
                db,
                player_id=player_id,
                session_id=instance.session_id,
                skill_id=skill_id,
                at=received,
            )
        outcome = Outcome(
            correct=solved,
            hints_used=help_used(
                tried,
                instance.hints_used + await teaching.views_on_problem(db, instance.id),
            ),
            seconds=seconds,
            # Practice is untimed: speed never lowers the score there.
            fluency=catalog.graph.skills[skill_id].fluency and not practice,
            tier=instance.tier,
        )
        confirms = _confirms(catalog, skill_id, instance.variant, instance.tier)
        instance.newly_mastered = _apply_score(
            catalog, row, skill_id, instance.difficulty, outcome, received, confirms=confirms
        )
        instance.answered_at = received
        instance.correct = solved
        if not solved:
            await _record_stuck(db, catalog, instance, problem, [*attempts, attempt], received)
    else:
        row = await mastery.get(db, player_id, skill_id)

    out = AnswerOut(
        verdict=verdict,
        misconception=misconception,
        feedback=_feedback(catalog, instance, problem, verdict, misconception, scored),
        solved=solved,
        attempts_left=allowed - used,
        mastery=_mastery_out(catalog, skill_id, row, received),
        answer_latex=reveal.latex if scored else None,
        answer_choice=reveal.choice if scored else None,
        total_solved=await problems.count_solved(db, player_id),
    )
    await db.commit()
    return out
