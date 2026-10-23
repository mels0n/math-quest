# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false
"""Teaching content of the five batch 3 arithmetic skills: complete, renders for every
problem, keeps to short sentences, and tells each story with the numbers its tier makes."""

import re
from pathlib import Path

import pytest

from mathquest.engine.catalog import load_catalog
from mathquest.engine.content.coverage import skill_coverage
from mathquest.engine.content.schema import WordTemplate
from mathquest.engine.teaching import (
    render_explanations,
    render_feedback,
    render_hints,
    render_lesson,
)
from mathquest.engine.templates import plain
from tests.engine.test_arithmetic_generators import BATCH_THREE_ARITHMETIC
from tests.engine.test_batch_two_teaching import text_of
from tests.engine.test_generators import flatten

CONTENT = Path(__file__).resolve().parents[2] / "content"
CATALOG = load_catalog(CONTENT, "k8-core")
PACK = CATALOG.pack
SEEDS = 60
SKILL = "add_several_2digit"


def sentences(text: str) -> list[str]:
    unlisted = re.sub(r"(?m)^\d+\.\s", "", text)
    return [s for s in re.split(r"(?<=[.!?])\s+", unlisted) if s]


@pytest.mark.parametrize("skill_id", BATCH_THREE_ARITHMETIC)
def test_skill_meets_every_coverage_target(skill_id: str) -> None:
    source = CATALOG.source(skill_id)
    coverage = skill_coverage(PACK, source.skill, source.generator)
    assert coverage.gaps == ()
    assert coverage.misconceptions >= 2
    assert coverage.feedback == coverage.misconceptions


@pytest.mark.parametrize("skill_id", BATCH_THREE_ARITHMETIC)
def test_lesson_has_screens_a_worked_example_and_a_try_it(skill_id: str) -> None:
    lesson = render_lesson(PACK.lessons[skill_id])
    assert 2 <= len(lesson.screens) <= 4
    assert lesson.worked_steps
    assert lesson.try_it_tier == 0


@pytest.mark.parametrize("skill_id", BATCH_THREE_ARITHMETIC)
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


@pytest.mark.parametrize("skill_id", BATCH_THREE_ARITHMETIC)
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


@pytest.mark.parametrize("skill_id", BATCH_THREE_ARITHMETIC)
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


# --- word problems ---------------------------------------------------------------------------


def templates() -> tuple[WordTemplate, ...]:
    return PACK.word_problems[SKILL].templates


def test_at_least_fifteen_templates_and_two_numbers_counts() -> None:
    found = templates()
    assert len(found) >= 15
    assert len({t.id for t in found}) == len(found)
    three = [t for t in found if t.id.startswith("three_")]
    four = [t for t in found if t.id.startswith("four_")]
    assert len(three) + len(four) == len(found)
    assert len(three) >= 8 and len(four) >= 8


def test_stories_show_every_number_their_tier_makes_and_serve_that_tier() -> None:
    for template in templates():
        four = template.id.startswith("four_")
        assert template.tiers == ((1,) if four else (0, 2)), template.id
        assert template.answer_from == "generator_answer"
        for name in "abcd" if four else "abc":
            assert "{" + name + "}" in template.text_template or "{" + name + " " in (
                template.text_template
            ), (template.id, name)
        assert ("{d}" in template.text_template) == four, template.id


def test_stories_put_the_numbers_together_and_agree_with_their_tier() -> None:
    source = CATALOG.source(SKILL)
    served: dict[int, set[str]] = {0: set(), 1: set(), 2: set()}
    for tier in range(3):
        for seed in range(300):
            problem = source.generate(seed, tier, "word")
            assert problem.template_id is not None
            served[tier].add(problem.template_id)
            shown = [int(n) for n in re.findall(r"\d+", text_of(problem.prompt))]
            expected = 4 if tier == 1 else 3
            assert len(shown) == expected, (problem.template_id, shown)
            assert sum(shown) == problem.answer
            assert problem.template_id.startswith("four_") == (tier == 1)
    assert len(served[0]) >= 8 and len(served[2]) >= 8 and len(served[1]) >= 8


def test_stories_agree_with_one_and_keep_to_twelve_words_a_sentence() -> None:
    source = CATALOG.source(SKILL)
    for template in templates():
        for tier in template.tiers or ():
            for seed in range(SEEDS):
                problem = source.generate(seed, tier, "word", template.id)
                text = text_of(problem.prompt)
                assert not re.search(r"\b1 [a-z]+s\b", text), (template.id, text)
                for sentence in sentences(text):
                    assert len(sentence.split()) <= 12, (template.id, sentence)
                    assert not re.match(r"\d", sentence), (template.id, sentence)
