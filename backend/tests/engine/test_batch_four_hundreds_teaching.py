# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false
"""Teaching content of the four three-digit skills of batch 4: complete, renders for every
problem and keeps to short sentences."""

import re
from pathlib import Path

import pytest

from mathquest.engine.catalog import load_catalog
from mathquest.engine.content.coverage import skill_coverage
from mathquest.engine.teaching import (
    render_explanations,
    render_feedback,
    render_hints,
    render_lesson,
)
from mathquest.engine.templates import plain
from tests.engine.test_batch_three_arithmetic_teaching import sentences
from tests.engine.test_generators import flatten
from tests.engine.test_hundreds_generators import HUNDREDS

CONTENT = Path(__file__).resolve().parents[2] / "content"
CATALOG = load_catalog(CONTENT, "k8-core")
PACK = CATALOG.pack
SEEDS = 60


@pytest.mark.parametrize("skill_id", HUNDREDS)
def test_skill_meets_every_coverage_target(skill_id: str) -> None:
    source = CATALOG.source(skill_id)
    coverage = skill_coverage(PACK, source.skill, source.generator)
    assert coverage.gaps == ()
    assert coverage.misconceptions >= 2
    assert coverage.feedback == coverage.misconceptions


@pytest.mark.parametrize("skill_id", HUNDREDS)
def test_lesson_has_screens_a_worked_example_and_a_try_it(skill_id: str) -> None:
    lesson = render_lesson(PACK.lessons[skill_id])
    assert 2 <= len(lesson.screens) <= 4
    assert lesson.worked_steps
    assert lesson.try_it_tier == 0


@pytest.mark.parametrize("skill_id", HUNDREDS)
def test_hints_feedback_and_explanations_render_and_the_last_hint_names_the_answer(
    skill_id: str,
) -> None:
    source = CATALOG.source(skill_id)
    explanations = PACK.explanations[skill_id]
    for tier in range(len(source.tier_difficulties)):
        for seed in range(SEEDS):
            problem = source.generate(seed, tier)
            hints = [plain(h) for h in render_hints(PACK.hints[skill_id], problem)]
            assert len(hints) == 3
            assert re.search(rf"\b{problem.answer}\b", hints[2]), (tier, seed, hints[2])
            assert len(render_explanations(explanations, problem)) >= 3
            for wrong in problem.misconceptions:
                feedback = render_feedback(explanations, problem, wrong.key)
                assert feedback is not None, (skill_id, wrong.key)
                assert f"= {problem.answer}" not in plain(feedback)


@pytest.mark.parametrize("skill_id", HUNDREDS)
def test_rendered_help_keeps_to_twelve_words_a_sentence_and_has_no_dash(skill_id: str) -> None:
    """The lint counts a template as written; a child reads it filled in."""
    source = CATALOG.source(skill_id)
    explanations = PACK.explanations[skill_id]
    for tier in range(len(source.tier_difficulties)):
        for seed in range(SEEDS):
            problem = source.generate(seed, tier)
            shown = [plain(h) for h in render_hints(PACK.hints[skill_id], problem)]
            shown += [plain(a.body) for a in render_explanations(explanations, problem)]
            for wrong in problem.misconceptions:
                feedback = render_feedback(explanations, problem, wrong.key)
                assert feedback is not None
                shown.append(plain(feedback))
            for text in shown:
                for dash in (chr(0x2014), chr(0x2013), " - ", "--"):
                    assert dash not in text, (skill_id, tier, seed, text)
                for sentence in sentences(text):
                    assert len(sentence.split()) <= 12, (skill_id, tier, seed, sentence)
                    assert not re.match(r"\d", sentence), (skill_id, tier, seed, sentence)


@pytest.mark.parametrize("skill_id", HUNDREDS)
def test_hints_before_the_last_show_no_single_digit_of_the_working(skill_id: str) -> None:
    """Hints 1 and 2 may name the numbers of the question and little else, so that a
    digit that happens to be the answer cannot slip in (the lint would fail it)."""
    source = CATALOG.source(skill_id)
    for tier in range(len(source.tier_difficulties)):
        for seed in range(SEEDS):
            problem = source.generate(seed, tier)
            hints = [plain(h) for h in render_hints(PACK.hints[skill_id], problem)]
            shown = {int(n) for n in re.findall(r"\d+", flatten(problem))}
            answer = int(problem.answer)
            for hint in hints[:2]:
                for number in re.findall(r"\d+", hint):
                    assert int(number) != answer or answer in shown, (tier, seed, hint)


def test_the_borrowing_hints_walk_across_a_zero() -> None:
    """The last hint of a zero in the tens place borrows a hundred first, then a ten."""
    source = CATALOG.source("sub_3digit_regroup")
    seen = 0
    for seed in range(300):
        problem = source.generate(seed, 0)
        v = problem.values
        if int(v["top_tens"]) != 0 or int(v["top_ones"]) >= int(v["bottom_ones"]):
            continue
        last = plain(render_hints(PACK.hints["sub_3digit_regroup"], problem)[2])
        assert last.index("Borrow a hundred") < last.index("Borrow a ten"), last
        assert "10 tens" in last
        seen += 1
    assert seen >= 10


def test_the_carrying_hints_name_a_carry_only_when_there_is_one() -> None:
    source = CATALOG.source("add_3digit_regroup")
    for tier in range(3):
        for seed in range(SEEDS):
            problem = source.generate(seed, tier)
            last = plain(render_hints(PACK.hints["add_3digit_regroup"], problem)[2])
            v = problem.values
            ones = int(v["top_ones"]) + int(v["bottom_ones"])
            assert ("carry 1 ten" in last) == (ones >= 10), last
