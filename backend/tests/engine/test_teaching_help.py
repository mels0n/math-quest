"""Pure teaching rules: feedback after a wrong answer, the explanation rotation, the
stuck condition, hint credit and which problems get help at all."""

import uuid
from pathlib import Path

from mathquest.engine.catalog import build_catalog, load_catalog
from mathquest.engine.content import load_pack
from mathquest.engine.mastery import HELP_CAP, Outcome, help_used, score
from mathquest.engine.teaching import (
    FEEDBACK_COPY,
    all_approaches_shown,
    answer_feedback,
    first_approach,
    next_approach,
)
from mathquest.engine.templates import plain
from mathquest.engine.transport import latex
from mathquest.engine.types import Problem, TextPart

CONTENT = Path(__file__).resolve().parents[2] / "content"
CATALOG = load_catalog(CONTENT, "k8-core")
PACK = CATALOG.pack


def _problem(skill_id: str = "add_within_10", seed: int = 3, tier: int = 1) -> Problem:
    return CATALOG.source(skill_id).generate(seed, tier)


def test_a_matched_mistake_gets_its_own_feedback_with_the_numbers() -> None:
    problem = _problem()
    out = answer_feedback(
        PACK.explanations["add_within_10"],
        problem,
        "counted_start",
        scored=False,
        hint_available=True,
    )
    assert out is not None and out.kind == "misconception"
    text = plain(out.text)
    assert str(problem.values["big"]) in text
    assert f"= {latex(problem.answer)}" not in text


def test_an_unmatched_wrong_answer_gets_a_generic_line() -> None:
    problem = _problem()
    explanations = PACK.explanations["add_within_10"]
    hint = answer_feedback(explanations, problem, None, scored=False, hint_available=True)
    retry = answer_feedback(explanations, problem, None, scored=False, hint_available=False)
    assert hint is not None and hint.kind == "hint"
    assert hint.text == (TextPart(FEEDBACK_COPY["hint"]),)
    assert retry is not None and retry.kind == "retry"
    # A key with no feedback written falls back to the generic line too.
    other = answer_feedback(
        explanations, problem, "no_such_key", scored=False, hint_available=False
    )
    assert other is not None and other.kind == "retry"


def test_a_problem_scored_wrong_gets_only_mistake_feedback() -> None:
    problem = _problem()
    explanations = PACK.explanations["add_within_10"]
    assert answer_feedback(explanations, problem, None, scored=True, hint_available=True) is None
    out = answer_feedback(
        explanations, problem, "subtracted_instead", scored=True, hint_available=False
    )
    assert out is not None and out.kind == "misconception"


def test_generic_copy_has_no_dashes_and_never_a_number() -> None:
    for text in FEEDBACK_COPY.values():
        assert chr(0x2014) not in text and chr(0x2013) not in text
        assert not any(ch.isdigit() for ch in text)


def test_the_rotation_starts_in_different_places_and_visits_every_approach() -> None:
    count = 4
    starts = {first_approach(str(uuid.UUID(int=i)), "add_within_10", count) for i in range(40)}
    assert starts == set(range(count))
    player = str(uuid.UUID(int=7))
    order = [next_approach(player, "add_within_10", count, k) for k in range(count * 2)]
    assert sorted(order[:count]) == list(range(count))
    assert order[count:] == order[:count]
    assert order[0] == first_approach(player, "add_within_10", count)
    # Stable: the same player and skill always start at the same place.
    assert first_approach(player, "add_within_10", count) == order[0]


def test_stuck_needs_every_approach_shown() -> None:
    assert all_approaches_shown(3, {0, 1, 2})
    assert all_approaches_shown(3, [2, 1, 0, 1])
    assert not all_approaches_shown(3, {0, 2})
    assert not all_approaches_shown(0, set())


def test_hint_credit_adds_wrong_tries_and_hints_and_caps_them() -> None:
    assert help_used(0, 0) == 0
    assert help_used(1, 1) == 2
    assert help_used(0, 3) == HELP_CAP
    assert help_used(2, 3) == HELP_CAP

    def credit(tries: int, hints: int) -> float:
        return score(
            Outcome(correct=True, hints_used=help_used(tries, hints), seconds=1, fluency=False)
        )

    assert credit(0, 0) == 1.0
    assert credit(0, 1) == 0.75
    assert credit(1, 1) == 0.5
    assert credit(0, 3) == 0.25  # a solve after the worked example is still a hinted solve
    assert credit(2, 3) == 0.25


def test_only_problems_with_the_generator_numbers_get_help() -> None:
    fixture = load_pack(Path(__file__).resolve().parents[1] / "fixtures" / "packs" / "test-pack")
    catalog = build_catalog(fixture, CATALOG.slots)
    for skill_id, source in catalog.sources.items():
        assert source.shows_generator(source.generate(1, 0))
        if source.bank is not None:
            item = source.bank.items[0]
            assert not source.shows_generator(source.generate(1, 0, "bank", item.id))
        if source.word_problems is not None:
            for template in source.word_problems.templates:
                problem = source.generate(1, 0, "word", template.id)
                assert source.shows_generator(problem) is (template.expression is None), (
                    skill_id,
                    template.id,
                )
