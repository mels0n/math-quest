"""Placement: find where a new learner starts by probing anchor skills.

Anchors are the skills marked ``anchor: true``, taken in the graph's topological order
(the spine). A placement round asks one problem at a time, each at an anchor's middle
tier, and works only from the answers so far, so the whole round can be replayed from
its history.

The round keeps a probability for every possible level: -1 (no anchor passed) up to
the last anchor (every anchor passed). Each answer updates it with Bayes' rule under a
deliberately loose learner model (`answer_probability`: a learner at level L answers
anchor A right with probability GUESS + (1 - GUESS - SLIP) * logistic(SLOPE * (L - A))).
The model is not the simulated learners' model; tests check the search against several
different learner models (docs/adr/0015-placement.md).

1. **Prior.** Flat without a grade hint. With one, each level's weight falls off by
   HINT_DECAY (in log terms) per anchor away from the hint's anchor, so the hint is a
   mild head start that a few answers outweigh.
2. **Probe.** The first probe is the hint's anchor (`start_anchor`). After that, when
   the answers point above every anchor passed so far, the next anchor up is asked;
   otherwise the anchor whose answer is expected to leave the least uncertainty
   (posterior entropy), the lower one on a tie.
3. **Stop.** After MAX_QUESTIONS answers; after MIN_QUESTIONS when the placement is
   already STOP_CONFIDENCE likely to be within one anchor; or at any point when an end
   of the spine is END_CONFIDENCE likely (nothing passed; or everything passed, once the
   last anchor was answered right).
4. **Place.** The level with the least expected cost: the right level costs nothing,
   one anchor off costs NEAR_COST, two or more too low costs 1 and two or more too high
   costs OVER_COST, because a learner placed too high meets gaps while one placed too
   low only moves on quickly. Ties go to the lower level. The placement is never above
   the highest anchor answered right.

The result (`outcome`) is the frontier (the highest anchor passed, None when nothing
passed), the provisionally mastered skills (every anchor up to the frontier and all
their prerequisites, transitively) and the regions to reveal (those of the provisional
skills, plus the frontier's region, or the first anchor's when nothing passed).
"""

import math
from collections.abc import Sequence
from dataclasses import dataclass
from functools import lru_cache
from typing import Literal, get_args

from mathquest.engine.content.schema import GRADE_BANDS, Skill
from mathquest.engine.skillgraph import SkillGraph

MAX_QUESTIONS = 15
MIN_QUESTIONS = 12
GUESS = 0.12
SLIP = 0.08
SLOPE = 1.0
HINT_DECAY = 0.3
STOP_CONFIDENCE = 0.99
END_CONFIDENCE = 0.95
OVER_COST = 3.0
NEAR_COST = 0.15
EARLY_BANDS = ("K", "1", "2")
"""Without a grade hint the round starts at the middle anchor of these bands."""
GradeHint = Literal["K", "1", "2", "3", "4", "5", "6", "7", "8"]
"""What "what grade are you in?" accepts: kindergarten to grade 8."""
GRADE_HINTS: tuple[GradeHint, ...] = get_args(GradeHint)


@dataclass(frozen=True)
class Answer:
    """One scored placement answer: the anchor's index on the spine and whether it was right."""

    anchor: int
    correct: bool


@dataclass(frozen=True)
class Outcome:
    frontier: str | None
    provisional: tuple[str, ...]
    """Skills to mark provisionally mastered, in topological order."""
    revealed_regions: tuple[str, ...]
    """Region ids, in the order their first skill appears in topological order."""


def spine(graph: SkillGraph) -> tuple[str, ...]:
    """The anchor skills in topological order."""
    return tuple(sid for sid in graph.topo_order() if graph.skills[sid].anchor)


def probe_tier(skill: Skill) -> int:
    """The tier placement asks an anchor at: its middle tier."""
    return len(skill.tiers) // 2


def _band(skill: Skill) -> int:
    return GRADE_BANDS.index(skill.grade_band)


def start_anchor(graph: SkillGraph, anchors: Sequence[str], grade_hint: str | None) -> int:
    """The index of the first probe.

    With a hint, the first anchor of that grade band; if the spine has none, the last
    anchor of an earlier band; if there is none of those either, the first anchor.
    Without a hint, the middle anchor of the K to 2 bands (the lower middle of an even
    count), or the first anchor when none is in those bands.
    """
    if not anchors:
        raise ValueError("no anchors")
    bands = [_band(graph.skills[sid]) for sid in anchors]
    if grade_hint is None:
        early = [i for i, b in enumerate(bands) if GRADE_BANDS[b] in EARLY_BANDS]
        return early[(len(early) - 1) // 2] if early else 0
    wanted = GRADE_BANDS.index(grade_hint)
    for i, band in enumerate(bands):
        if band == wanted:
            return i
    below = [i for i, band in enumerate(bands) if band < wanted]
    return below[-1] if below else 0


def answer_probability(level: int, anchor: int) -> float:
    """How likely the search's learner model at ``level`` answers ``anchor`` right."""
    return GUESS + (1 - GUESS - SLIP) / (1 + math.exp(-SLOPE * (level - anchor)))


_Counts = tuple[tuple[tuple[int, bool], int], ...]


def _counts(answers: Sequence[Answer]) -> _Counts:
    seen: dict[tuple[int, bool], int] = {}
    for a in answers:
        seen[(a.anchor, a.correct)] = seen.get((a.anchor, a.correct), 0) + 1
    return tuple(sorted(seen.items()))


@lru_cache(maxsize=4096)
def _posterior(count: int, hint: int | None, counts: _Counts) -> tuple[float, ...]:
    """Probability of each level -1 .. count-1 (index 0 is level -1)."""
    logs = [0.0 if hint is None else -HINT_DECAY * abs(level - hint) for level in range(-1, count)]
    for (anchor, correct), times in counts:
        for i, level in enumerate(range(-1, count)):
            p = answer_probability(level, anchor)
            logs[i] += times * math.log(p if correct else 1 - p)
    top = max(logs)
    weights = [math.exp(x - top) for x in logs]
    total = sum(weights)
    return tuple(w / total for w in weights)


def posterior(count: int, answers: Sequence[Answer], hint: int | None = None) -> list[float]:
    """Probability of each level -1 .. count-1 given the answers (index 0 is level -1).
    ``hint`` is the grade hint's anchor, None without a hint."""
    return list(_posterior(count, hint, _counts(answers)))


def _miss_cost(placed: int, level: int) -> float:
    off = placed - level
    if off == 0:
        return 0.0
    if abs(off) == 1:
        return NEAR_COST
    return OVER_COST if off > 0 else 1.0


def _cost(probs: Sequence[float], placed: int) -> float:
    return sum(p * _miss_cost(placed, i) for i, p in enumerate(probs))


def _within_one(probs: Sequence[float], placed: int) -> float:
    return sum(probs[max(0, placed - 1) : placed + 2])


def _highest_passed(counts: _Counts) -> int:
    """The highest anchor answered right at least once, -1 for none."""
    return max((anchor for (anchor, correct), _times in counts if correct), default=-1)


def _place(probs: Sequence[float], counts: _Counts | None) -> int:
    """The index with the least expected cost, never above the highest anchor answered
    right in ``counts`` (a learner is never marked as knowing an anchor they did not
    show; None lifts the cap); the lowest on a tie."""
    allowed = len(probs) if counts is None else _highest_passed(counts) + 2
    costs = [_cost(probs, i) for i in range(allowed)]
    least = min(costs)
    return next(i for i, c in enumerate(costs) if c <= least + 1e-12)


def best_split(count: int, answers: Sequence[Answer], hint: int | None = None) -> int:
    """The placement: the highest anchor passed, -1 for none."""
    counts = _counts(answers)
    return _place(_posterior(count, hint, counts), counts) - 1


def _entropy(probs: Sequence[float]) -> float:
    return -sum(p * math.log(p) for p in probs if p > 0)


def _expected_entropy(probs: Sequence[float], anchor: int) -> float:
    likely = [answer_probability(level, anchor) for level in range(-1, len(probs) - 1)]
    right = sum(p * q for p, q in zip(probs, likely, strict=True))
    total = 0.0
    for correct, chance in ((True, right), (False, 1 - right)):
        after = [p * (q if correct else 1 - q) for p, q in zip(probs, likely, strict=True)]
        norm = sum(after)
        total += chance * _entropy([x / norm for x in after])
    return total


def next_probe(
    count: int, start: int, answers: Sequence[Answer], hint: int | None = None
) -> int | None:
    """The index of the anchor to ask next, or None when the round is over. ``start`` is
    the first probe; ``hint`` the grade hint's anchor (None without a hint)."""
    if count == 0 or len(answers) >= MAX_QUESTIONS:
        return None
    if not answers:
        return start
    return _next(count, hint, _counts(answers), len(answers))


@lru_cache(maxsize=1 << 16)
def _next(count: int, hint: int | None, counts: _Counts, asked: int) -> int | None:
    probs = _posterior(count, hint, counts)
    top_shown = _highest_passed(counts) == count - 1
    if probs[0] >= END_CONFIDENCE or (top_shown and probs[-1] >= END_CONFIDENCE):
        return None
    if asked >= MIN_QUESTIONS and _within_one(probs, _place(probs, counts)) >= STOP_CONFIDENCE:
        return None
    shown = _highest_passed(counts)
    if _place(probs, None) - 1 > shown:
        # The answers point above every anchor passed so far: ask the next one up.
        return shown + 1
    scores = [_expected_entropy(probs, anchor) for anchor in range(count)]
    least = min(scores)
    return next(a for a, score in enumerate(scores) if score <= least + 1e-12)


def outcome(
    graph: SkillGraph,
    anchors: Sequence[str],
    answers: Sequence[Answer],
    hint: int | None = None,
) -> Outcome:
    """Frontier, provisional skills and regions to reveal for a finished round."""
    split = best_split(len(anchors), answers, hint)
    passed: set[str] = set()
    for sid in anchors[: split + 1]:
        passed.add(sid)
        passed.update(graph.ancestors(sid))
    order = graph.topo_order()
    provisional = tuple(sid for sid in order if sid in passed)
    frontier = anchors[split] if split >= 0 else None
    shown = set(provisional)
    if frontier is not None:
        shown.add(frontier)
    elif anchors:
        shown.add(anchors[0])
    regions: list[str] = []
    for sid in order:
        region = graph.skills[sid].region
        if sid in shown and region not in regions:
            regions.append(region)
    return Outcome(frontier=frontier, provisional=provisional, revealed_regions=tuple(regions))
