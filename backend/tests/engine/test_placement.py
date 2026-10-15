"""Placement algorithm: rules, termination, and simulated learners."""

import math
import random
from collections.abc import Callable
from pathlib import Path

import pytest

from mathquest.engine.content import Skill, load_pack
from mathquest.engine.placement import (
    CONFIRM_MARGIN,
    MAX_QUESTIONS,
    MIN_QUESTIONS,
    Answer,
    best_split,
    next_probe,
    outcome,
    probe_tier,
    spine,
    start_anchor,
)
from mathquest.engine.skillgraph import SkillGraph

PACK = Path(__file__).resolve().parents[2] / "content" / "packs" / "k8-core"
GRADES = ("K", "1", "2", "3", "4", "5", "6", "7", "8")

SLIP = 0.05
GUESS = 0.10
SLOPE = 2.0
RUNS = 1000
BAR = 0.95


def _skill(
    sid: str,
    *prereqs: str,
    anchor: bool = False,
    grade: str = "K",
    region: str = "r",
    tiers: int = 3,
) -> Skill:
    return Skill(
        id=sid,
        name=sid,
        region=region,
        prerequisites=prereqs,
        fluency=False,
        anchor=anchor,
        generator=sid,
        tiers=tuple({"id": i, "label": f"t{i}"} for i in range(tiers)),  # pyright: ignore[reportArgumentType]
        grade_band=grade,  # pyright: ignore[reportArgumentType]
        keypad="numpad",
    )


def _synthetic() -> SkillGraph:
    """One anchor per grade K to 8 on a chain, each with a side skill it needs, and a
    region per two grades. Declared hardest first, so only the topological order puts
    the spine in order."""
    skills: list[Skill] = []
    for i in reversed(range(len(GRADES))):
        grade = GRADES[i]
        region = f"region_{i // 2}"
        prereqs = (f"side_{i}",) if i == 0 else (f"side_{i}", f"anchor_{i - 1}")
        skills.append(_skill(f"anchor_{i}", *prereqs, anchor=True, grade=grade, region=region))
        skills.append(_skill(f"side_{i}", grade=grade, region=region))
    return SkillGraph(skills)


SYNTH = _synthetic()
SYNTH_SPINE = spine(SYNTH)


def _learner(level: int, rng: random.Random) -> Callable[[int], bool]:
    """Answers anchor ``a`` correctly with 10% guessing, 5% slips, and in between a
    logistic of how far the anchor is above the learner's level (``level`` is the index
    of the highest anchor the learner has mastered; -1 for none)."""

    def answer(anchor: int) -> bool:
        knows = 1 / (1 + math.exp(-(SLOPE * (level - anchor) + SLOPE / 2)))
        return rng.random() < GUESS + (1 - GUESS - SLIP) * knows

    return answer


def _place(count: int, start: int, answer: Callable[[int], bool]) -> tuple[int, list[Answer]]:
    answers: list[Answer] = []
    while (probe := next_probe(count, start, answers)) is not None:
        answers.append(Answer(probe, answer(probe)))
        assert len(answers) <= MAX_QUESTIONS
    return best_split(count, answers), answers


def _hit_rate(
    graph: SkillGraph, level: int, hint: Callable[[int], str | None], seed: int
) -> tuple[float, float]:
    anchors = spine(graph)
    rng = random.Random(seed)
    hits = 0
    asked = 0
    for _ in range(RUNS):
        start = start_anchor(graph, anchors, hint(level))
        placed, answers = _place(len(anchors), start, _learner(level, rng))
        hits += abs(placed - level) <= 1
        asked += len(answers)
    return hits / RUNS, asked / RUNS


def test_spine_is_the_anchors_in_topological_order() -> None:
    assert tuple(f"anchor_{i}" for i in range(len(GRADES))) == SYNTH_SPINE
    real = SkillGraph(load_pack(PACK).skills.values())
    assert spine(real) == (
        "add_within_10",
        "add_within_20",
        "add_2digit_regroup",
        "add_fractions_unlike",
    )


def test_probe_tier_is_the_middle_tier() -> None:
    assert probe_tier(_skill("a", tiers=3)) == 1
    assert probe_tier(_skill("a", tiers=1)) == 0
    assert probe_tier(_skill("a", tiers=4)) == 2


def test_start_anchor_from_the_grade_hint() -> None:
    for i, grade in enumerate(GRADES):
        assert start_anchor(SYNTH, SYNTH_SPINE, grade) == i
    # No hint: the middle of the K to 2 anchors.
    assert start_anchor(SYNTH, SYNTH_SPINE, None) == 1


def test_start_anchor_falls_back_to_an_earlier_band() -> None:
    real = SkillGraph(load_pack(PACK).skills.values())
    anchors = spine(real)
    assert start_anchor(real, anchors, None) == 1  # add_within_20, the K-2 middle
    assert start_anchor(real, anchors, "K") == 0
    assert start_anchor(real, anchors, "3") == 2  # no grade 3 anchor: the grade 2 one
    assert start_anchor(real, anchors, "8") == 3
    late = SkillGraph(
        [_skill("a", anchor=True, grade="4"), _skill("b", "a", anchor=True, grade="6")]
    )
    assert start_anchor(late, spine(late), None) == 0
    assert start_anchor(late, spine(late), "2") == 0
    with pytest.raises(ValueError):
        start_anchor(late, (), None)


def test_best_split_agrees_with_the_most_answers() -> None:
    assert best_split(5, []) == -1
    assert best_split(5, [Answer(2, True), Answer(3, False)]) == 2
    assert best_split(5, [Answer(4, True)]) == 4
    # One pass and one miss on the same anchor: the lower split.
    assert best_split(5, [Answer(1, True), Answer(2, True), Answer(2, False)]) == 1
    # A lucky guess above a clear boundary does not move it.
    answers = [
        Answer(1, True),
        Answer(1, True),
        Answer(2, False),
        Answer(2, False),
        Answer(4, True),
    ]
    assert best_split(5, answers) == 1


def test_search_moves_up_on_a_pass_and_down_on_a_miss() -> None:
    assert next_probe(9, 4, []) == 4
    assert next_probe(9, 4, [Answer(4, True)]) == 6
    assert next_probe(9, 4, [Answer(4, False)]) == 1
    assert next_probe(9, 4, [Answer(4, False), Answer(1, True)]) == 2


def _exact(level: int) -> Callable[[int], bool]:
    return lambda anchor: anchor <= level


@pytest.mark.parametrize("level", range(-1, len(GRADES)))
def test_a_consistent_learner_lands_exactly(level: int) -> None:
    for start in (0, 1, 4, 8):
        placed, answers = _place(len(GRADES), start, _exact(level))
        assert placed == level
        # The boundary was confirmed on both sides it has.
        if level >= 0:
            assert sum(1 for a in answers if a.anchor == level and a.correct) >= CONFIRM_MARGIN
        if level + 1 < len(GRADES):
            assert sum(1 for a in answers if a.anchor == level + 1) >= CONFIRM_MARGIN


def test_stops_early_at_the_ends_of_the_spine() -> None:
    _, none = _place(len(GRADES), 1, _exact(-1))
    _, every = _place(len(GRADES), 1, _exact(len(GRADES) - 1))
    assert len(none) < MIN_QUESTIONS
    assert len(every) < MIN_QUESTIONS


def test_asks_at_least_the_minimum_inside_the_spine() -> None:
    _, answers = _place(len(GRADES), 1, _exact(4))
    assert MIN_QUESTIONS <= len(answers) <= MAX_QUESTIONS


def test_never_more_than_the_maximum() -> None:
    flip = iter(range(10_000))
    _, answers = _place(len(GRADES), 4, lambda _a: next(flip) % 2 == 0)
    assert len(answers) == MAX_QUESTIONS
    assert next_probe(len(GRADES), 4, answers) is None
    rng = random.Random(3)
    for _ in range(500):
        _, answers = _place(len(GRADES), rng.randrange(len(GRADES)), lambda _a: rng.random() < 0.5)
        assert len(answers) <= MAX_QUESTIONS


def test_no_anchors_means_no_probe() -> None:
    assert next_probe(0, 0, []) is None


@pytest.mark.parametrize("level", [0, 2, 4, 6, 8])
def test_simulated_learners_land_within_one_anchor(level: int) -> None:
    rate, asked = _hit_rate(SYNTH, level, lambda _lv: None, seed=1000 + level)
    assert rate >= BAR, f"no hint, level {GRADES[level]}: {rate:.3f}"
    assert asked <= MAX_QUESTIONS


@pytest.mark.parametrize("level", [0, 2, 4, 6, 8])
def test_simulated_learners_with_a_grade_hint(level: int) -> None:
    """A learner in grade g usually knows grade g-1 well: the hint is one grade above
    the level (capped at 8), and a hint that is their own level must work as well."""
    above, _ = _hit_rate(SYNTH, level, lambda lv: GRADES[min(lv + 1, 8)], seed=2000 + level)
    same, _ = _hit_rate(SYNTH, level, lambda lv: GRADES[lv], seed=3000 + level)
    assert above >= BAR, f"hint above, level {GRADES[level]}: {above:.3f}"
    assert same >= BAR, f"hint at level, level {GRADES[level]}: {same:.3f}"


@pytest.mark.parametrize("level", [-1, 0, 1, 2, 3])
def test_simulated_learners_on_the_real_pack(level: int) -> None:
    real = SkillGraph(load_pack(PACK).skills.values())
    rate, _ = _hit_rate(real, level, lambda _lv: None, seed=4000 + level)
    assert rate >= BAR, f"real pack, level {level}: {rate:.3f}"


def test_outcome_marks_the_frontier_and_everything_below() -> None:
    answers = [Answer(3, True), Answer(4, False)]
    result = outcome(SYNTH, SYNTH_SPINE, answers)
    assert result.frontier == "anchor_3"
    expected = {f"anchor_{i}" for i in range(4)} | {f"side_{i}" for i in range(4)}
    assert set(result.provisional) == expected
    order = SYNTH.topo_order()
    assert list(result.provisional) == [s for s in order if s in expected]
    assert set(result.revealed_regions) == {"region_0", "region_1"}


def test_outcome_with_nothing_passed_reveals_the_first_region() -> None:
    result = outcome(SYNTH, SYNTH_SPINE, [Answer(0, False), Answer(0, False)])
    assert result.frontier is None
    assert result.provisional == ()
    assert result.revealed_regions == ("region_0",)


def test_outcome_covers_anchors_off_the_frontiers_chain() -> None:
    """On the real pack the fractions anchor does not build on two-digit addition, but
    passing it still places the learner past every anchor below it."""
    real = SkillGraph(load_pack(PACK).skills.values())
    anchors = spine(real)
    result = outcome(real, anchors, [Answer(3, True)])
    assert result.frontier == "add_fractions_unlike"
    assert {"add_within_10", "add_2digit_regroup", "equivalent_fractions"} <= set(
        result.provisional
    )
    assert set(result.revealed_regions) == {
        "number_meadows",
        "operation_canyon",
        "fraction_forest",
    }


def test_ancestors_are_transitive() -> None:
    assert SYNTH.ancestors("anchor_2") == {"side_2", "anchor_1", "side_1", "anchor_0", "side_0"}
    assert SYNTH.ancestors("side_0") == set()
