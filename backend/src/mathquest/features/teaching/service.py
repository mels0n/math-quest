"""Lessons: the screens a skill teaches with, whether a player has seen them, and the
lesson's practice problem ("try it").

A lesson is read from the catalog the app loaded at boot and rendered by the engine
(``engine.teaching.render_lesson``); it can be fetched any number of times, seen or not,
so a learner can replay it. Play offers a lesson before the first problem of a skill
whose lesson the player has not seen (``features.play``, which reads the same
``lessons_seen`` rows); ``mark_seen`` records it, and calling it again changes nothing.

The practice problem is a real generated problem at the lesson's ``try_it.tier``, from
``try_it.seed_hint`` when the lesson pins one and a random seed otherwise, checked by the
same checker as play. It lives in ``lesson_tries``, apart from ``problem_instances``, so
it never reaches mastery, the solved count or the scheduler's history. It allows
TRY_ATTEMPTS misses, like a typed play problem; a wrong form or an unreadable answer
costs nothing. Its answer is sent only once it is solved or out of tries, and answering
it again after that returns the stored outcome. The checker runs with no transaction
open: read and commit, check, then lock the row and write, where a second request that
finished the problem in between wins.
"""

import secrets
import uuid
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from mathquest.engine.catalog import Catalog, SkillSource
from mathquest.engine.checker.bounded import CheckerPool
from mathquest.engine.checker.check import CheckResult, Verdict
from mathquest.engine.content.schema import Lesson
from mathquest.engine.teaching import render_lesson
from mathquest.engine.transport import answer_latex, prompt_out, visual_out
from mathquest.engine.types import Problem
from mathquest.entities import lessons
from mathquest.entities.lessons import LessonTry
from mathquest.features.teaching.schema import (
    LessonOut,
    LessonScreenOut,
    SeenOut,
    TryAnswerOut,
    TryItOut,
    TryProblemOut,
    WorkedExampleOut,
)
from mathquest.shared.errors import NotFound

TRY_ATTEMPTS = 3
STORED_LATEX_MAX = 200
SEED_LIMIT = 2**53
"""Seeds are below this, so they are exact as JavaScript numbers."""


def _now() -> datetime:
    return datetime.now(UTC)


def _lesson(catalog: Catalog, skill_id: str) -> tuple[SkillSource, Lesson]:
    """The skill's source and lesson; NotFound for an unknown skill or one with no lesson."""
    source = catalog.sources.get(skill_id)
    lesson = catalog.pack.lessons.get(skill_id)
    if source is None or lesson is None:
        raise NotFound()
    return source, lesson


def get_lesson(catalog: Catalog, skill_id: str) -> LessonOut:
    source, lesson = _lesson(catalog, skill_id)
    shown = render_lesson(lesson)
    return LessonOut(
        skill_id=skill_id,
        skill_name=source.skill.name,
        screens=[
            LessonScreenOut(title=s.title, body=prompt_out(s.body), visual=visual_out(s.visual))
            for s in shown.screens
        ],
        worked_example=WorkedExampleOut(
            prompt=prompt_out(shown.worked_prompt),
            steps=[prompt_out(step) for step in shown.worked_steps],
        ),
        try_it=TryItOut(tier=_try_tier(source, lesson)),
    )


def _try_tier(source: SkillSource, lesson: Lesson) -> int:
    return min(lesson.try_it.tier, len(source.tier_difficulties) - 1)


async def mark_seen(
    db: AsyncSession, catalog: Catalog, player_id: uuid.UUID, skill_id: str
) -> SeenOut:
    _lesson(catalog, skill_id)
    await lessons.mark_seen(db, player_id, skill_id, _now())
    await db.commit()
    return SeenOut(skill_id=skill_id, seen=True)


async def start_try(
    db: AsyncSession,
    catalog: Catalog,
    player_id: uuid.UUID,
    skill_id: str,
    *,
    expose_answers: bool = False,
) -> TryProblemOut:
    source, lesson = _lesson(catalog, skill_id)
    tier = _try_tier(source, lesson)
    hint = lesson.try_it.seed_hint
    seed = secrets.randbelow(SEED_LIMIT) if hint is None else hint
    problem = source.generate(seed, tier)
    row = await lessons.add_try(
        db, player_id=player_id, skill_id=skill_id, tier=tier, seed=seed, issued_at=_now()
    )
    out = TryProblemOut(
        try_id=row.id,
        skill_id=skill_id,
        skill_name=source.skill.name,
        prompt=prompt_out(problem.prompt),
        keypad=source.skill.keypad,
        dev_answer_latex=answer_latex(problem) if expose_answers else None,
    )
    await db.commit()
    return out


def _problem(catalog: Catalog, row: LessonTry) -> Problem:
    source = catalog.sources.get(row.skill_id)
    if source is None:
        raise NotFound()
    return source.generate(row.seed, row.tier)


def _outcome(row: LessonTry, problem: Problem, result: CheckResult | None) -> TryAnswerOut:
    """The answer response; ``result`` is None when reporting a finished problem again."""
    done = row.answered_at is not None
    if result is None:
        verdict = Verdict.CORRECT if row.correct else Verdict.INCORRECT
        misconception = None
    else:
        verdict = result.verdict
        misconception = result.misconception if verdict is Verdict.INCORRECT else None
    return TryAnswerOut(
        verdict=verdict,
        misconception=misconception,
        solved=bool(row.correct),
        attempts_left=max(0, TRY_ATTEMPTS - row.misses),
        answer_latex=answer_latex(problem) if done else None,
    )


async def answer_try(
    db: AsyncSession,
    pool: CheckerPool,
    catalog: Catalog,
    player_id: uuid.UUID,
    try_id: uuid.UUID,
    latex: str,
) -> TryAnswerOut:
    row = await lessons.get_try(db, player_id, try_id)
    if row is None:
        raise NotFound()
    problem = _problem(catalog, row)
    if row.answered_at is not None:
        out = _outcome(row, problem, None)
        await db.commit()
        return out
    await db.commit()

    if len(latex) > STORED_LATEX_MAX:
        result = CheckResult(Verdict.UNREADABLE, None)
    else:
        result = await pool.check(problem, latex)

    row = await lessons.lock_try(db, player_id, try_id)
    if row is None:
        raise NotFound()
    if row.answered_at is not None:
        out = _outcome(row, problem, None)
        await db.commit()
        return out
    if result.verdict is Verdict.CORRECT:
        row.correct = True
        row.answered_at = _now()
    elif result.verdict is Verdict.INCORRECT:
        row.misses += 1
        if row.misses >= TRY_ATTEMPTS:
            row.correct = False
            row.answered_at = _now()
    out = _outcome(row, problem, result)
    await db.commit()
    return out
