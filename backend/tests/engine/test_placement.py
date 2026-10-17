"""Placement algorithm: rules, termination, and simulated learners."""

import math
import random
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

import pytest

from mathquest.engine.content import Skill, load_pack
from mathquest.engine.placement import (
    MAX_QUESTIONS,
    MIN_QUESTIONS,
    Answer,
    best_split,
    next_probe,
    outcome,
    posterior,
    probe_tier,
    spine,
    start_anchor,
)
from mathquest.engine.skillgraph import SkillGraph

PACK = Path(__file__).resolve().parents[2] / "content" / "packs" / "k8-core"
GRADES = ("K", "1", "2", "3", "4", "5", "6", "7", "8")

RUNS = 1000


@dataclass(frozen=True)
class Model:
    """A simulated learner at level L answers anchor A right with probability
    guess + (1 - guess - slip) * logistic(slope * (L - A) + offset)."""

    slope: float
    offset: float
    slip: float
    guess: float


MODELS = {
    # The steep learner the first version of placement was tuned on.
    "steep": Model(2.0, 1.0, 0.05, 0.10),
    # The reference learner: about even odds on their own level's anchor.
    "reference": Model(1.0, 0.0, 0.05, 0.10),
    "no_guess": Model(2.0, 1.0, 0.05, 0.0),
    "slip_15": Model(2.0, 1.0, 0.15, 0.10),
    "slope_15": Model(1.5, 0.0, 0.05, 0.10),
    # Choice anchors: a quarter of guesses land.
    "guess_25": Model(2.0, 1.0, 0.05, 0.25),
}

# Lowest share within one anchor, per model and hint, over grades K to 8, and the
# highest share placed two or more anchors too high. The reference model must meet 95%
# with a hint and keep over-placement to 2%; without a hint it measures 93.8% at worst,
# at the limit of what fifteen one-problem questions can tell apart (see ADR-0015). The
# other rows are the measured numbers (recorded in ADR-0015) less a small margin, so a
# change that makes any of them worse fails.
BARS: dict[tuple[str, str], tuple[float, float]] = {
    ("reference", "none"): (0.93, 0.02),
    ("reference", "same"): (0.95, 0.02),
    ("reference", "above"): (0.95, 0.02),
    ("steep", "none"): (0.98, 0.02),
    ("steep", "same"): (0.98, 0.015),
    ("steep", "above"): (0.975, 0.025),
    ("no_guess", "none"): (0.985, 0.01),
    ("no_guess", "same"): (0.99, 0.01),
    ("no_guess", "above"): (0.99, 0.01),
    ("slip_15", "none"): (0.905, 0.02),
    ("slip_15", "same"): (0.95, 0.015),
    ("slip_15", "above"): (0.94, 0.015),
    ("slope_15", "none"): (0.97, 0.015),
    ("slope_15", "same"): (0.98, 0.01),
    ("slope_15", "above"): (0.975, 0.01),
    ("guess_25", "none"): (0.835, 0.165),
    ("guess_25", "same"): (0.905, 0.095),
    ("guess_25", "above"): (0.90, 0.095),
}

HINTS: dict[str, Callable[[int], str | None]] = {
    "none": lambda _lv: None,
    "same": lambda lv: GRADES[lv],
    "above": lambda lv: GRADES[min(lv + 1, 8)],
}


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


def _learner(model: Model, level: int, rng: random.Random) -> Callable[[int], bool]:
    """Answers anchor ``a`` under ``model``; ``level`` is the index of the highest anchor
    the learner has mastered (-1 for none)."""

    def answer(anchor: int) -> bool:
        knows = 1 / (1 + math.exp(-(model.slope * (level - anchor) + model.offset)))
        return rng.random() < model.guess + (1 - model.guess - model.slip) * knows

    return answer


def _place(
    count: int, start: int, answer: Callable[[int], bool], hint: int | None = None
) -> tuple[int, list[Answer]]:
    answers: list[Answer] = []
    while (probe := next_probe(count, start, answers, hint)) is not None:
        answers.append(Answer(probe, answer(probe)))
        assert len(answers) <= MAX_QUESTIONS
    return best_split(count, answers, hint), answers


def _rates(
    graph: SkillGraph,
    model: Model,
    level: int,
    hint: Callable[[int], str | None],
    seed: int,
    runs: int = RUNS,
) -> tuple[float, float, float]:
    """Share within one anchor, share placed two or more too high, mean questions."""
    anchors = spine(graph)
    rng = random.Random(seed)
    hits = over = asked = 0
    for _ in range(runs):
        grade = hint(level)
        start = start_anchor(graph, anchors, grade)
        placed, answers = _place(
            len(anchors), start, _learner(model, level, rng), None if grade is None else start
        )
        hits += abs(placed - level) <= 1
        over += placed - level >= 2
        asked += len(answers)
    return hits / runs, over / runs, asked / runs


def test_spine_is_the_anchors_in_topological_order() -> None:
    assert tuple(f"anchor_{i}" for i in range(len(GRADES))) == SYNTH_SPINE
    real = SkillGraph(load_pack(PACK).skills.values())
    assert spine(real) == (
        "count_to_10",
        "add_within_10",
        "add_within_20",
        "compare_numbers_100",
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
    assert start_anchor(real, anchors, None) == 2  # add_within_20, the K-2 middle
    assert start_anchor(real, anchors, "K") == 0
    assert start_anchor(real, anchors, "1") == 2
    assert start_anchor(real, anchors, "3") == 4  # no grade 3 anchor: the grade 2 one
    assert start_anchor(real, anchors, "8") == 5
    late = SkillGraph(
        [_skill("a", anchor=True, grade="4"), _skill("b", "a", anchor=True, grade="6")]
    )
    assert start_anchor(late, spine(late), None) == 0
    assert start_anchor(late, spine(late), "2") == 0
    with pytest.raises(ValueError):
        start_anchor(late, (), None)


def test_the_posterior_follows_the_answers() -> None:
    flat = posterior(5, [])
    assert flat == pytest.approx([1 / 6] * 6)
    # Passing anchor 2 and missing anchor 3 points at level 2.
    answers = [Answer(2, True), Answer(3, False)] * 3
    probs = posterior(5, answers)
    assert max(range(6), key=lambda i: probs[i]) - 1 == 2
    assert best_split(5, answers) == 2
    # A hint is a mild prior: it leans toward its anchor but a few answers outweigh it.
    hinted = posterior(5, [], hint=4)
    assert hinted[-1] > hinted[0]
    assert best_split(5, [Answer(0, False)] * 4, hint=4) == -1


def test_ties_place_lower() -> None:
    assert best_split(5, []) == -1  # nothing answered right: nothing passed
    assert best_split(5, [Answer(1, True), Answer(2, True), Answer(2, False)]) <= 2


def test_a_lucky_guess_above_a_clear_boundary_does_not_move_it() -> None:
    answers = [Answer(1, True)] * 3 + [Answer(2, False)] * 3 + [Answer(4, True)]
    assert best_split(5, answers) == 1


def test_the_first_probe_is_the_start_then_the_search_moves() -> None:
    assert next_probe(9, 4, []) == 4
    up = next_probe(9, 4, [Answer(4, True)])
    down = next_probe(9, 4, [Answer(4, False)])
    assert up is not None and down is not None and down < up


def _exact(level: int) -> Callable[[int], bool]:
    return lambda anchor: anchor <= level


@pytest.mark.parametrize("level", range(-1, len(GRADES)))
def test_a_consistent_learner_lands_within_one(level: int) -> None:
    for start in (0, 1, 4, 8):
        placed, _ = _place(len(GRADES), start, _exact(level))
        assert abs(placed - level) <= 1


def test_stops_early_when_nothing_is_passed() -> None:
    """A child who cannot do the easiest anchor is not asked a dozen questions."""
    placed, none = _place(len(GRADES), 1, _exact(-1))
    assert placed == -1
    assert len(none) < MIN_QUESTIONS
    _, every = _place(len(GRADES), 1, _exact(len(GRADES) - 1))
    assert len(every) <= MIN_QUESTIONS


def test_asks_at_least_the_minimum_inside_the_spine() -> None:
    for level in range(0, len(GRADES) - 1):
        _, answers = _place(len(GRADES), 1, _exact(level))
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


@pytest.mark.parametrize(("model", "hint"), sorted(BARS))
def test_simulated_learners_across_models(model: str, hint: str) -> None:
    """Every model at every grade K to 8: the share placed within one anchor and the
    share placed two or more anchors too high, against BARS."""
    bar, over_bar = BARS[(model, hint)]
    seed = sum(map(ord, model + hint))
    for level in range(len(GRADES)):
        rate, over, asked = _rates(SYNTH, MODELS[model], level, HINTS[hint], seed + level)
        where = f"{model}, hint {hint}, level {GRADES[level]}"
        assert rate >= bar, f"{where}: within one {rate:.3f}"
        assert over <= over_bar, f"{where}: two or more too high {over:.3f}"
        assert asked <= MAX_QUESTIONS


# The real pack's six anchors, per model and hint: lowest share within one anchor and highest
# share placed two or more too high, over every level from "nothing passed" to "everything
# passed". Without a hint the reference learner is at the limit of fifteen questions on six
# anchors (the bars are set from the figures in ADR-0019, which supersedes the four-anchor figures in ADR-0015); with the hint of the learner's own grade it meets ADR-0015's bar.
REAL_BARS: dict[tuple[str, str], tuple[float, float]] = {
    ("reference", "none"): (0.94, 0.03),
    ("reference", "same"): (0.95, 0.02),
    ("steep", "none"): (0.98, 0.015),
    ("steep", "same"): (0.98, 0.015),
}


@pytest.mark.parametrize(("model", "hint"), sorted(REAL_BARS))
def test_simulated_learners_on_the_real_pack(model: str, hint: str) -> None:
    real = SkillGraph(load_pack(PACK).skills.values())
    anchors = spine(real)

    def grade(level: int) -> str | None:
        return None if hint == "none" else real.skills[anchors[max(level, 0)]].grade_band

    bar, over_bar = REAL_BARS[(model, hint)]
    for level in range(-1, len(anchors)):
        rate, over, _ = _rates(real, MODELS[model], level, grade, seed=4000 + level)
        where = f"real pack, {model}, hint {hint}, level {level}"
        assert rate >= bar, f"{where}: within one {rate:.3f}"
        assert over <= over_bar, f"{where}: over {over:.3f}"


def test_outcome_marks_the_frontier_and_everything_below() -> None:
    answers = [Answer(2, True), Answer(3, True), Answer(4, False), Answer(5, False)] * 3
    result = outcome(SYNTH, SYNTH_SPINE, answers)
    assert result.frontier == "anchor_3"
    expected = {f"anchor_{i}" for i in range(4)} | {f"side_{i}" for i in range(4)}
    assert set(result.provisional) == expected
    order = SYNTH.topo_order()
    assert list(result.provisional) == [s for s in order if s in expected]
    assert set(result.revealed_regions) == {"region_0", "region_1"}


def test_outcome_with_nothing_passed_reveals_the_first_region() -> None:
    result = outcome(SYNTH, SYNTH_SPINE, [Answer(0, False)] * 4)
    assert result.frontier is None
    assert result.provisional == ()
    assert result.revealed_regions == ("region_0",)


def test_outcome_covers_anchors_off_the_frontiers_chain() -> None:
    """On the real pack the fractions anchor does not build on two-digit addition, but
    passing it still places the learner past every anchor below it."""
    real = SkillGraph(load_pack(PACK).skills.values())
    anchors = spine(real)
    result = outcome(real, anchors, [Answer(4, True), Answer(5, True)] * 3)
    assert result.frontier == "add_fractions_unlike"
    assert {
        "count_to_10",
        "add_within_10",
        "compare_numbers_100",
        "add_2digit_regroup",
        "equivalent_fractions",
    } <= set(result.provisional)
    assert set(result.revealed_regions) == {
        "number_meadows",
        "operation_canyon",
        "fraction_forest",
    }


def test_ancestors_are_transitive() -> None:
    assert SYNTH.ancestors("anchor_2") == {"side_2", "anchor_1", "side_1", "anchor_0", "side_0"}
    assert SYNTH.ancestors("side_0") == set()
