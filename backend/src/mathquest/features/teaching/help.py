"""Help on a play problem: the hint ladder, "explain it another way", and the stuck log.

Hints and explanations are rendered by the engine from the problem regenerated from its
stored seed, so they quote the learner's own numbers. They are offered only for a
problem that shows the generator's numbers and answer (``SkillSource.shows_generator``)
and only while the problem is open: asking on a problem already scored is
Conflict("problem_scored"), on one closed unanswered Conflict("problem_closed"), and on
a skill with no hints or explanations (or a bank item) NotFound.

Hints. Each request returns the next level, up to the skill's three, and counts it in
the problem's ``hints_used`` under the problem's row lock (the same lock the answer route
takes, so a hint and an answer cannot interleave). A fourth request is
Conflict("no_more_hints") and changes nothing. Levels 1 and 2 never state the answer;
level 3 is the full worked example on this problem's numbers. The play slice reads
``hints_used`` when it scores the problem: each level viewed costs credit like a wrong
try (``engine.mastery.help_used``).

Explanations. Each request returns the next of the skill's 3 or 4 approaches in a
rotation per player (``engine.teaching.next_approach``): it starts at a place drawn from
the player and skill, so different players meet a different approach first, and moves
on by one with every explanation the player has seen for that skill. Every view is
recorded with its session; once every approach was shown in the session, a problem of
that skill scored wrong records a stuck event (play slice). Explanations cost no credit.

Stuck log. The admin export lists stuck events as ``StuckProblemOut``: skill, generator,
tier, seed and wrong answers, the exact shape ``content-report --stuck`` reads, with no
player id, nickname or time.
"""

import csv
import io
import json
import uuid
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from mathquest.engine.catalog import Catalog, SkillSource
from mathquest.engine.teaching import next_approach, render_explanations, render_hints
from mathquest.engine.transport import prompt_out, visual_out
from mathquest.engine.types import Problem
from mathquest.entities import problems, teaching
from mathquest.entities.problems import ProblemInstance
from mathquest.features.teaching.schema import ExplanationOut, HintOut, StuckProblemOut
from mathquest.shared.errors import Conflict, NotFound

STUCK_CSV_COLUMNS = ("skill", "generator", "tier", "seed", "wrong_answers")


def _now() -> datetime:
    return datetime.now(UTC)


async def _open_problem(
    db: AsyncSession, catalog: Catalog, player_id: uuid.UUID, problem_id: uuid.UUID
) -> tuple[ProblemInstance, SkillSource, Problem]:
    """Lock the problem; it must be open and show the generator's numbers."""
    instance = await problems.lock_problem(db, player_id, problem_id)
    if instance is None:
        raise NotFound()
    if instance.answered_at is not None:
        raise Conflict("problem_closed" if instance.correct is None else "problem_scored")
    source = catalog.sources.get(instance.skill_id)
    if source is None:
        raise NotFound()
    problem = catalog.regenerate(
        instance.skill_id, instance.seed, instance.tier, instance.variant, instance.template_id
    )
    if not source.shows_generator(problem):
        raise NotFound()
    return instance, source, problem


async def next_hint(
    db: AsyncSession, catalog: Catalog, player_id: uuid.UUID, problem_id: uuid.UUID
) -> HintOut:
    instance, source, problem = await _open_problem(db, catalog, player_id, problem_id)
    ladder = catalog.pack.hints.get(source.skill_id)
    if ladder is None:
        raise NotFound()
    levels = len(ladder.levels)
    if instance.hints_used >= levels:
        raise Conflict("no_more_hints")
    texts = render_hints(ladder, problem)
    instance.hints_used += 1
    out = HintOut(
        level=instance.hints_used, levels=levels, text=prompt_out(texts[instance.hints_used - 1])
    )
    await db.commit()
    return out


async def next_explanation(
    db: AsyncSession, catalog: Catalog, player_id: uuid.UUID, problem_id: uuid.UUID
) -> ExplanationOut:
    instance, source, problem = await _open_problem(db, catalog, player_id, problem_id)
    explanations = catalog.pack.explanations.get(source.skill_id)
    if explanations is None:
        raise NotFound()
    count = len(explanations.approaches)
    before = await teaching.count_views(db, player_id, source.skill_id)
    index = next_approach(str(player_id), source.skill_id, count, before)
    shown = render_explanations(explanations, problem)[index]
    await teaching.add_view(
        db,
        player_id=player_id,
        session_id=instance.session_id,
        problem_id=instance.id,
        skill_id=source.skill_id,
        approach=index,
        shown_at=_now(),
    )
    out = ExplanationOut(
        approach=index,
        approaches=count,
        style=shown.style,
        body=prompt_out(shown.body),
        visual=visual_out(shown.visual),
    )
    await db.commit()
    return out


async def stuck_log(db: AsyncSession, since: datetime | None = None) -> list[StuckProblemOut]:
    """Every stuck event (at or after ``since``), oldest first, without identity."""
    rows = await teaching.stuck_since(db, since)
    out = [
        StuckProblemOut(
            skill=r.skill_id,
            generator=r.generator,
            tier=r.tier,
            seed=r.seed,
            wrong_answers=list(r.wrong_answers),
        )
        for r in rows
    ]
    await db.commit()
    return out


def stuck_csv(entries: list[StuckProblemOut]) -> str:
    """The export as CSV. ``wrong_answers`` is one cell holding a JSON list, so answers
    with commas or quotes survive and no cell starts with a formula character."""
    buffer = io.StringIO()
    writer = csv.writer(buffer, lineterminator="\n")
    writer.writerow(STUCK_CSV_COLUMNS)
    for e in entries:
        writer.writerow([e.skill, e.generator, e.tier, e.seed, json.dumps(e.wrong_answers)])
    return buffer.getvalue()
