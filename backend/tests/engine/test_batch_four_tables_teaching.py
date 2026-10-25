# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false
"""Teaching content of the four times tables skills: complete, renders for every problem, keeps
to short sentences, teaches a strategy for each table and tells equal groups that are equal."""

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
from tests.engine.test_batch_two_teaching import text_of
from tests.engine.test_generators import flatten
from tests.engine.test_table_generators import TABLES

CONTENT = Path(__file__).resolve().parents[2] / "content"
CATALOG = load_catalog(CONTENT, "k8-core")
PACK = CATALOG.pack
SEEDS = 60
STRATEGY = {2: "double", 3: "double", 4: "double", 5: "half", 6: "fives", 7: "fives",
            8: "double", 9: "tens"}  # fmt: skip


@pytest.mark.parametrize("skill_id", TABLES)
def test_skill_meets_every_coverage_target(skill_id: str) -> None:
    source = CATALOG.source(skill_id)
    coverage = skill_coverage(PACK, source.skill, source.generator)
    assert coverage.gaps == ()
    assert coverage.misconceptions >= 2
    assert coverage.feedback == coverage.misconceptions


@pytest.mark.parametrize("skill_id", TABLES)
def test_lesson_has_screens_a_worked_example_and_a_try_it(skill_id: str) -> None:
    lesson = render_lesson(PACK.lessons[skill_id])
    assert 2 <= len(lesson.screens) <= 4
    assert lesson.worked_steps
    assert lesson.try_it_tier == 0
    kinds = {s.visual.kind for s in PACK.lessons[skill_id].screens if s.visual is not None}
    assert "array" in kinds and kinds <= {"array", "number_line"}


@pytest.mark.parametrize("skill_id", TABLES)
def test_hints_feedback_and_explanations_render_and_the_last_hint_names_the_answer(
    skill_id: str,
) -> None:
    source = CATALOG.source(skill_id)
    explanations = PACK.explanations[skill_id]
    for tier in range(3):
        for seed in range(SEEDS):
            problem = source.generate(seed, tier)
            hints = [plain(h) for h in render_hints(PACK.hints[skill_id], problem)]
            assert len(hints) == 3
            assert re.search(rf"\b{problem.answer}\b", hints[2]), (tier, seed, hints[2])
            assert 3 <= len(render_explanations(explanations, problem)) <= 4
            for wrong in problem.misconceptions:
                feedback = render_feedback(explanations, problem, wrong.key)
                assert feedback is not None, (skill_id, wrong.key)
                assert f"= {problem.answer}" not in plain(feedback)


@pytest.mark.parametrize("skill_id", TABLES)
def test_rendered_help_keeps_to_twelve_words_a_sentence_and_has_no_dash(skill_id: str) -> None:
    source = CATALOG.source(skill_id)
    explanations = PACK.explanations[skill_id]
    for tier in range(3):
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


@pytest.mark.parametrize("skill_id", TABLES)
def test_hints_before_the_last_never_show_the_answer_unless_the_question_does(
    skill_id: str,
) -> None:
    source = CATALOG.source(skill_id)
    for tier in range(3):
        for seed in range(SEEDS):
            problem = source.generate(seed, tier)
            hints = [plain(h) for h in render_hints(PACK.hints[skill_id], problem)]
            shown = {int(n) for n in re.findall(r"\d+", flatten(problem))}
            answer = int(problem.answer)
            for hint in hints[:2]:
                for number in re.findall(r"\d+", hint):
                    assert int(number) != answer or answer in shown, (tier, seed, hint)


@pytest.mark.parametrize("skill_id", TABLES)
def test_every_hint_teaches_the_strategy_for_the_table_in_the_fact(skill_id: str) -> None:
    """The hints name the strategy (doubles, fives, tens) of the table the fact is about."""
    source = CATALOG.source(skill_id)
    first, second = TABLES[skill_id]
    for tier in range(3):
        for seed in range(SEEDS):
            problem = source.generate(seed, tier)
            g, s = int(problem.values["g"]), int(problem.values["s"])
            tables = [t for t in (first, second) if t in (g, s)]
            hints = [plain(h) for h in render_hints(PACK.hints[skill_id], problem)]
            words = " ".join(hints[:2]).lower()
            assert any(STRATEGY[t] in words for t in tables), (tables, hints)
            assert str(g * s) in hints[2]


def test_the_nines_teach_the_digit_pattern() -> None:
    steps = " ".join(a.body_md for a in PACK.explanations["mult_8_9"].approaches)
    lesson = " ".join(s.body_md for s in PACK.lessons["mult_8_9"].screens)
    assert "add up to 9" in steps and "add up to 9" in lesson
    assert PACK.explanations["mult_8_9"].misconceptions["digits_swapped"]


# --- word problems ---------------------------------------------------------------------------


@pytest.mark.parametrize("skill_id", TABLES)
def test_at_least_fifteen_different_stories(skill_id: str) -> None:
    templates = PACK.word_problems[skill_id].templates
    assert len(templates) >= 15
    assert len({t.id for t in templates}) == len(templates)
    assert len({t.text_template for t in templates}) == len(templates)
    assert all(str(t.grade_band) == "3" for t in templates)
    assert all(t.answer_from == "generator_answer" for t in templates)
    others = {
        t.text_template
        for other in ("equal_groups", "mult_as_groups", *TABLES)
        if other != skill_id
        for t in PACK.word_problems[other].templates
    }
    assert not others & {t.text_template for t in templates}
    for t in templates:
        assert "{g}" in t.text_template, t.id
        assert "{s}" in t.text_template or "{s obj}" in t.text_template, t.id


@pytest.mark.parametrize("skill_id", TABLES)
def test_a_story_tells_the_groups_and_agrees_with_the_answer(skill_id: str) -> None:
    source = CATALOG.source(skill_id)
    served: set[str] = set()
    for template in PACK.word_problems[skill_id].templates:
        for tier in range(3):
            for seed in range(SEEDS):
                problem = source.generate(seed, tier, "word", template.id)
                text = text_of(problem.prompt)
                served.add(str(problem.template_id))
                g, s = int(problem.values["g"]), int(problem.values["s"])
                assert sorted(int(n) for n in re.findall(r"\d+", text)) == sorted([g, s]), text
                assert problem.answer == g * s
                assert 2 <= g <= 10 and 2 <= s <= 10
                assert not re.search(r"\b1 [a-z]+s\b", text), (template.id, text)
                assert " times" not in text.lower(), (template.id, text)
                for sentence in sentences(text):
                    assert len(sentence.split()) <= 12, (template.id, sentence)
                    assert not re.match(r"\d", sentence), (template.id, sentence)
    assert served == {t.id for t in PACK.word_problems[skill_id].templates}
