"""Placement rounds: probe anchor skills, then mark what the learner already knows.

A round is driven by `engine.placement` and stored in one `placement_runs` row: the
anchors, the first probe and every probe issued (``state``), then the outcome
(``result``). Each probe is one problem at the anchor's middle tier, generated from a
stored seed like a play problem, and checked by the same checker. It is the bare
problem (a skill answered only with choices takes its bank item), because placement
measures the skill, not reading.

Placement gives no hearts, hints, lessons or explanations, and never says whether an
answer was right, so the answer never leaves the server. An answer that cannot be read
or is in the wrong form is not counted: the same problem is asked again, up to
FREE_RETRIES times; after that it counts as a miss. Placement problems are kept apart
from play's problem_instances, so they never count as solved, never move a rating and
never enter a session's history.

When the round ends, provisional marks left by an earlier round that no review has
confirmed are undone, and the new outcome's skills are marked provisionally mastered
(never touching a skill already mastered), due for review a day later. Starting a round
ends the player's unfinished one; answering an ended round is a Conflict.

The checker runs with no transaction open, like play: read the run and commit, check,
then lock the run and re-read it. If the open probe changed in between (a second
request answered it), this request records nothing and returns the round as it now is.
"""

import copy
import secrets
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from mathquest.engine.catalog import Catalog
from mathquest.engine.checker.bounded import CheckerPool
from mathquest.engine.checker.check import CheckResult, Verdict, check_choice
from mathquest.engine.limits import SEED_LIMIT, STORED_LATEX_MAX
from mathquest.engine.mastery import PROVISIONAL_REVIEW_DAYS, initial_rating
from mathquest.engine.placement import (
    MAX_QUESTIONS,
    Answer,
    next_probe,
    outcome,
    probe_tier,
    spine,
    start_anchor,
)
from mathquest.engine.transport import answer_latex, prompt_out
from mathquest.engine.types import KeypadProfile, Problem, Variant
from mathquest.entities import mastery, placement
from mathquest.entities.placement import PlacementRun
from mathquest.features.placement.schema import (
    PlacementDoneOut,
    PlacementProblemOut,
    PlacementStepOut,
    RegionOut,
)
from mathquest.shared.errors import Conflict, Invalid, NotFound

FREE_RETRIES = 3
"""Unreadable or wrong-form answers asked again before one counts as a miss."""

Probe = dict[str, Any]


def _now() -> datetime:
    return datetime.now(UTC)


def _new_probe(catalog: Catalog, skill_id: str, anchor: int) -> Probe:
    skill = catalog.graph.skills[skill_id]
    variant: Variant = "bank" if skill.keypad == "choice" else "bare"
    seed = secrets.randbelow(SEED_LIMIT)
    problem = catalog.source(skill_id).generate(seed, probe_tier(skill), variant)
    return {
        "id": str(uuid.uuid4()),
        "anchor": anchor,
        "skill_id": skill_id,
        "tier": probe_tier(skill),
        "seed": seed,
        "variant": problem.variant,
        "template_id": problem.template_id,
        "free": 0,
        "correct": None,
    }


def _problem(catalog: Catalog, probe: Probe) -> Problem:
    if probe["skill_id"] not in catalog.sources:
        raise Conflict("placement_closed")
    return catalog.regenerate(
        probe["skill_id"], probe["seed"], probe["tier"], probe["variant"], probe["template_id"]
    )


def _keypad(problem: Problem, declared: KeypadProfile) -> KeypadProfile:
    return "choice" if problem.choices is not None else declared


def _problem_out(catalog: Catalog, probe: Probe, expose_answers: bool) -> PlacementProblemOut:
    problem = _problem(catalog, probe)
    skill = catalog.graph.skills[probe["skill_id"]]
    return PlacementProblemOut(
        problem_id=uuid.UUID(probe["id"]),
        skill_id=skill.id,
        skill_name=skill.name,
        prompt=prompt_out(problem.prompt),
        keypad=_keypad(problem, skill.keypad),
        choices=None if problem.choices is None else [prompt_out(c) for c in problem.choices],
        dev_answer_latex=answer_latex(problem) if expose_answers else None,
        dev_answer_choice=problem.correct_choice if expose_answers else None,
    )


def _probes(row: PlacementRun) -> list[Probe]:
    probes: list[Probe] = row.state["probes"]
    return probes


def _open_probe(row: PlacementRun) -> Probe:
    probes = _probes(row)
    if not probes or probes[-1]["correct"] is not None:
        raise Conflict("placement_closed")
    return probes[-1]


def _hint(row: PlacementRun) -> int | None:
    """The grade hint's anchor, which shapes the search's prior; None without a hint."""
    return None if row.grade_hint is None else int(row.state["start"])


def _answers(probes: list[Probe]) -> list[Answer]:
    return [Answer(p["anchor"], p["correct"]) for p in probes if p["correct"] is not None]


def _step(
    catalog: Catalog,
    row: PlacementRun,
    expose_answers: bool,
    retry: Verdict | None = None,
) -> PlacementStepOut:
    probe = _open_probe(row)
    return PlacementStepOut(
        placement_id=row.id,
        problem=_problem_out(catalog, probe, expose_answers),
        question=len(_probes(row)),
        max_questions=MAX_QUESTIONS,
        retry=retry if retry in (Verdict.UNREADABLE, Verdict.WRONG_FORM) else None,
    )


def _done(catalog: Catalog, row: PlacementRun) -> PlacementDoneOut:
    result = row.result
    assert result is not None
    names = {r.id: r.name for r in catalog.pack.world.regions}
    return PlacementDoneOut(
        placement_id=row.id,
        frontier=list(result["frontier"]),
        provisional=list(result["provisional"]),
        revealed_regions=[
            RegionOut(id=rid, name=names[rid]) for rid in result["revealed_regions"] if rid in names
        ],
    )


def _current(
    catalog: Catalog, row: PlacementRun, expose_answers: bool
) -> PlacementStepOut | PlacementDoneOut:
    """The round as it stands: its outcome when finished, else its open question."""
    if row.finished_at is not None:
        if row.result is None:
            raise Conflict("placement_closed")
        return _done(catalog, row)
    return _step(catalog, row, expose_answers)


async def start(
    db: AsyncSession,
    catalog: Catalog,
    player_id: uuid.UUID,
    grade_hint: str | None,
    *,
    expose_answers: bool = False,
) -> PlacementStepOut:
    """Start a round (ending any unfinished one) and return its first question."""
    graph = catalog.graph
    anchors = spine(graph)
    if not anchors:
        raise Conflict("placement_unavailable")
    now = _now()
    await placement.abandon_open(db, player_id, now)
    first = start_anchor(graph, anchors, grade_hint)
    state = {
        "anchors": list(anchors),
        "start": first,
        "probes": [_new_probe(catalog, anchors[first], first)],
    }
    row = await placement.add_run(
        db, player_id=player_id, started_at=now, grade_hint=grade_hint, state=state
    )
    out = _step(catalog, row, expose_answers)
    await db.commit()
    return out


def _given(problem: Problem, latex: str | None, choice: int | None) -> None:
    """Reject an answer of the wrong kind for the problem (422), as play does."""
    if problem.choices is None:
        if latex is None or choice is not None:
            raise Invalid("latex_expected")
        return
    if choice is None or latex is not None:
        raise Invalid("choice_expected")
    if not 0 <= choice < len(problem.choices):
        raise Invalid("choice_out_of_range")


async def _finish(
    db: AsyncSession, catalog: Catalog, row: PlacementRun, probes: list[Probe], now: datetime
) -> None:
    anchors: list[str] = row.state["anchors"]
    graph = catalog.graph
    if any(sid not in graph.skills for sid in anchors):
        raise Conflict("placement_closed")
    result = outcome(graph, anchors, _answers(probes), _hint(row))
    await mastery.revert_provisional(db, row.player_id)
    ratings = {
        sid: initial_rating(catalog.source(sid).tier_difficulties) for sid in result.provisional
    }
    marked = await mastery.mark_provisional(
        db,
        row.player_id,
        ratings,
        review_due_at=now + timedelta(days=PROVISIONAL_REVIEW_DAYS),
        now=now,
    )
    order = {r.id: r.order for r in catalog.pack.world.regions}
    regions = sorted(result.revealed_regions, key=lambda rid: order.get(rid, len(order) + 1))
    row.result = {
        "frontier": [] if result.frontier is None else [result.frontier],
        "provisional": marked,
        "revealed_regions": regions,
        "asked": len(_answers(probes)),
    }
    row.finished_at = now


async def answer(
    db: AsyncSession,
    pool: CheckerPool,
    catalog: Catalog,
    player_id: uuid.UUID,
    placement_id: uuid.UUID,
    problem_id: uuid.UUID,
    latex: str | None = None,
    *,
    choice: int | None = None,
    expose_answers: bool = False,
) -> PlacementStepOut | PlacementDoneOut:
    """Record one answer and return the next question, or the outcome when done."""
    row = await placement.get_run(db, player_id, placement_id)
    if row is None:
        raise NotFound()
    if row.finished_at is not None or _open_probe(row)["id"] != str(problem_id):
        if all(p["id"] != str(problem_id) for p in _probes(row)):
            raise NotFound()
        out = _current(catalog, row, expose_answers)
        await db.commit()
        return out
    probe = _open_probe(row)
    free_before = probe["free"]
    problem = _problem(catalog, probe)
    _given(problem, latex, choice)
    await db.commit()

    if choice is not None:
        result = check_choice(problem, choice)
    elif latex is None or len(latex) > STORED_LATEX_MAX:
        result = CheckResult(Verdict.UNREADABLE, None)
    else:
        result = await pool.check(problem, latex)

    row = await placement.lock_run(db, player_id, placement_id)
    if row is None:
        raise NotFound()
    if (
        row.finished_at is not None
        or _open_probe(row)["id"] != str(problem_id)
        or _open_probe(row)["free"] != free_before
    ):
        out = _current(catalog, row, expose_answers)
        await db.commit()
        return out

    probes = copy.deepcopy(_probes(row))
    current = probes[-1]
    verdict = result.verdict
    retry: Verdict | None = None
    if verdict in (Verdict.CORRECT, Verdict.INCORRECT):
        current["correct"] = verdict is Verdict.CORRECT
    else:
        current["free"] += 1
        if current["free"] > FREE_RETRIES:
            current["correct"] = False
        else:
            retry = verdict
    if current["correct"] is not None:
        state = row.state
        anchors: list[str] = state["anchors"]
        nxt = next_probe(len(anchors), state["start"], _answers(probes), _hint(row))
        if nxt is not None and anchors[nxt] in catalog.graph.skills:
            probes.append(_new_probe(catalog, anchors[nxt], nxt))
            row.state = {**state, "probes": probes}
        else:
            row.state = {**state, "probes": probes}
            await _finish(db, catalog, row, probes, _now())
            out_done = _done(catalog, row)
            await db.commit()
            return out_done
    else:
        row.state = {**row.state, "probes": probes}
    out = _step(catalog, row, expose_answers, retry)
    await db.commit()
    return out
