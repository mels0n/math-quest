# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false
"""Teaching content of the four batch 4 skills that begin multiplying: complete, renders for
every problem, keeps to short sentences, and tells equal groups that are really equal."""

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
from tests.engine.test_group_generators import GROUPS

CONTENT = Path(__file__).resolve().parents[2] / "content"
CATALOG = load_catalog(CONTENT, "k8-core")
PACK = CATALOG.pack
SEEDS = 60
STORY_SKILLS = {"equal_groups": 2, "mult_as_groups": 3}


@pytest.mark.parametrize("skill_id", GROUPS)
def test_skill_meets_every_coverage_target(skill_id: str) -> None:
    source = CATALOG.source(skill_id)
    coverage = skill_coverage(PACK, source.skill, source.generator)
    assert coverage.gaps == ()
    assert coverage.misconceptions >= 2
    assert coverage.feedback == coverage.misconceptions


@pytest.mark.parametrize("skill_id", GROUPS)
def test_lesson_has_screens_a_worked_example_and_a_try_it(skill_id: str) -> None:
    lesson = render_lesson(PACK.lessons[skill_id])
    assert 2 <= len(lesson.screens) <= 4
    assert lesson.worked_steps
    assert lesson.try_it_tier == 0


@pytest.mark.parametrize("skill_id", GROUPS)
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


@pytest.mark.parametrize("skill_id", GROUPS)
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


@pytest.mark.parametrize("skill_id", GROUPS)
def test_hints_before_the_last_never_show_the_answer_unless_the_question_does(
    skill_id: str,
) -> None:
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


# --- the lessons -----------------------------------------------------------------------------


@pytest.mark.parametrize("skill_id", GROUPS)
def test_lesson_pictures_are_arrays_or_the_other_pictures_that_fit(skill_id: str) -> None:
    lesson = PACK.lessons[skill_id]
    kinds = {s.visual.kind for s in lesson.screens if s.visual is not None}
    assert kinds
    assert kinds <= {"array", "number_line", "base_ten"}


def test_the_grade_two_skills_never_write_the_times_sign() -> None:
    """Grade 2 finds totals by adding and skip counting (2.OA.C.4); the sign is grade 3."""
    for skill_id in ("equal_groups", "arrays"):
        lesson = PACK.lessons[skill_id]
        written = [s.body_md for s in lesson.screens] + list(lesson.worked_example.steps)
        source = CATALOG.source(skill_id)
        for tier in range(3):
            for seed in range(20):
                problem = source.generate(seed, tier)
                written += [plain(h) for h in render_hints(PACK.hints[skill_id], problem)]
        assert not any("\\times" in t for t in written if "{{" not in t), skill_id
        assert not any(chr(0xD7) in t for t in written), skill_id


def test_the_hints_for_zero_one_and_ten_name_the_rule_of_the_fact() -> None:
    source = CATALOG.source("mult_0_1_10")
    seen: set[str] = set()
    for tier in range(3):
        for seed in range(300):
            problem = source.generate(seed, tier)
            kind = str(problem.values["kind"])
            seen.add(kind)
            first, second, last = (
                plain(h) for h in render_hints(PACK.hints["mult_0_1_10"], problem)
            )
            assert {
                "zero": "nothing" in second,
                "one": "just that number" in second,
                "ten": "tens" in second and "zero" in second,
            }[kind], (kind, second)
            assert str(problem.answer) in last
            assert first != second
    assert seen == {"zero", "one", "ten"}


def test_the_array_hints_use_the_rows_after_the_change() -> None:
    source = CATALOG.source("arrays")
    for seed in range(100):
        problem = source.generate(seed, 2)
        _, second, last = (plain(h) for h in render_hints(PACK.hints["arrays"], problem))
        assert f"{problem.values['now']} rows" in second
        assert f"{problem.values['now']} times" in last
    for tier in (0, 1):
        problem = source.generate(1, tier)
        _, second, _ = (plain(h) for h in render_hints(PACK.hints["arrays"], problem))
        assert f"{problem.values['r']} rows" in second


# --- word problems ---------------------------------------------------------------------------


@pytest.mark.parametrize("skill_id", STORY_SKILLS)
def test_at_least_fifteen_different_stories(skill_id: str) -> None:
    templates = PACK.word_problems[skill_id].templates
    assert len(templates) >= 15
    assert len({t.id for t in templates}) == len(templates)
    assert len({t.text_template for t in templates}) == len(templates)
    assert all(str(t.grade_band) == str(STORY_SKILLS[skill_id]) for t in templates)
    assert all(t.answer_from == "generator_answer" for t in templates)
    for t in templates:
        assert "{g}" in t.text_template, t.id
        assert "{s}" in t.text_template or "{s obj}" in t.text_template, t.id


@pytest.mark.parametrize("skill_id", STORY_SKILLS)
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
                assert not re.search(r"\b1 [a-z]+s\b", text), (template.id, text)
                assert " times" not in text.lower(), (template.id, text)
                for sentence in sentences(text):
                    assert len(sentence.split()) <= 12, (template.id, sentence)
                    assert not re.match(r"\d", sentence), (template.id, sentence)
    assert served == {t.id for t in PACK.word_problems[skill_id].templates}


@pytest.mark.parametrize("skill_id", STORY_SKILLS)
def test_stories_make_sense_for_the_counts_they_are_given(skill_id: str) -> None:
    """No story has fewer than two groups or a group of fewer than two (a plural noun is
    always right), and the biggest total stays one a child can picture."""
    source = CATALOG.source(skill_id)
    for tier in range(3):
        for seed in range(SEEDS):
            v = source.generate(seed, tier, "word").values
            assert int(v["g"]) >= 2 and int(v["s"]) >= 2
            assert int(v["g"]) * int(v["s"]) <= (80 if skill_id == "equal_groups" else 60)
