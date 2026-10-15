"""Placement: find where a new learner starts by probing anchor skills.

Anchors are the skills marked ``anchor: true``, taken in the graph's topological order
(the spine). A placement round asks one problem at a time, each at an anchor's middle
tier, and works only from the answers so far, so the whole round can be replayed from
its history.

Every decision comes from the split that best agrees with the answers so far: the
highest passed anchor (-1 for none) that disagrees with the fewest of them, counting
correct answers above it and misses at or below it (`best_split`).

1. **Search.** The first probe is the grade hint's anchor (`start_anchor`). While
   several splits agree equally well with the answers, the probe is the middle of their
   range, which is a binary search: a correct answer moves the probe up, a miss moves
   it down. A later answer that contradicts an earlier one widens the range again, and
   the search resumes inside it instead of creeping one anchor at a time.
2. **Confirm.** Once one split is best, its boundary is re-checked: the anchor just
   below it needs CONFIRM_MARGIN more correct answers than misses, the anchor just
   above it CONFIRM_MARGIN more misses than correct answers. The anchor furthest from
   its margin is asked next (the lower one on a tie). Each probe is one problem, so an
   anchor gets one problem while searching and a second at the boundary, and more only
   while its answers disagree.
3. **Stop.** After MAX_QUESTIONS answers; or when both neighbours are confirmed and at
   least MIN_QUESTIONS were asked; or when they are confirmed and the split is at an end
   of the spine (nothing passed, or everything passed), where more questions would only
   repeat what is already known. A tie between splits at the end goes to the lowest.

The result (`outcome`) is the frontier (the highest anchor of the split, None when
nothing passed), the provisionally mastered skills (every anchor up to the frontier and
all their prerequisites, transitively) and the regions to reveal (those of the
provisional skills, plus the frontier's region, or the first anchor's when nothing
passed). See docs/adr/0015-placement.md.
"""

from collections.abc import Sequence
from dataclasses import dataclass

from mathquest.engine.content.schema import GRADE_BANDS, Skill
from mathquest.engine.skillgraph import SkillGraph

MAX_QUESTIONS = 15
MIN_QUESTIONS = 12
CONFIRM_MARGIN = 2
EARLY_BANDS = ("K", "1", "2")
"""Without a grade hint the round starts at the middle anchor of these bands."""
GRADE_HINTS = ("K", "1", "2", "3", "4", "5", "6", "7", "8")


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


def _costs(count: int, answers: Sequence[Answer]) -> list[int]:
    """For each split -1 .. count-1 (the highest passed anchor), how many answers
    disagree with it: correct answers above it plus misses at or below it."""
    return [
        sum(1 for a in answers if a.correct == (a.anchor > split)) for split in range(-1, count)
    ]


def best_split(count: int, answers: Sequence[Answer]) -> int:
    """The split that disagrees with the fewest answers; the lowest of them on a tie, so
    an unclear boundary places the learner lower."""
    costs = _costs(count, answers)
    return costs.index(min(costs)) - 1


def _best_range(count: int, answers: Sequence[Answer]) -> tuple[int, int]:
    """The lowest and highest of the splits that disagree with the fewest answers."""
    costs = _costs(count, answers)
    least = min(costs)
    best = [i - 1 for i, cost in enumerate(costs) if cost == least]
    return best[0], best[-1]


def _margin(answers: Sequence[Answer], anchor: int) -> int:
    """Correct answers minus misses on ``anchor``."""
    return sum((1 if a.correct else -1) for a in answers if a.anchor == anchor)


def next_probe(count: int, start: int, answers: Sequence[Answer]) -> int | None:
    """The index of the anchor to ask next, or None when the round is over."""
    if count == 0 or len(answers) >= MAX_QUESTIONS:
        return None
    if not answers:
        return start
    low, high = _best_range(count, answers)
    if low < high:
        # Search: halve the range of splits the answers cannot tell apart.
        upper = high + 1
        middle = (low + upper) // 2
        return middle if middle > low else low + 1
    split = low
    # (distance still to go, anchor): the anchor below the split needs to show it is
    # passed, the anchor above it that it is not.
    needs: list[tuple[int, int]] = []
    if split >= 0:
        needs.append((CONFIRM_MARGIN - _margin(answers, split), split))
    if split + 1 < count:
        needs.append((CONFIRM_MARGIN + _margin(answers, split + 1), split + 1))
    open_needs = [n for n in needs if n[0] > 0]
    if not open_needs:
        at_end = split in (-1, count - 1)
        if at_end or len(answers) >= MIN_QUESTIONS:
            return None
        open_needs = needs
    return max(open_needs, key=lambda n: (n[0], -n[1]))[1]


def outcome(graph: SkillGraph, anchors: Sequence[str], answers: Sequence[Answer]) -> Outcome:
    """Frontier, provisional skills and regions to reveal for a finished round."""
    split = best_split(len(anchors), answers)
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
