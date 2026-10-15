# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false
"""add_within_20 is the reference skill: lesson, hints, explanations and word problems."""

import re
from pathlib import Path

import pytest
import sympy

from mathquest.engine.catalog import load_catalog
from mathquest.engine.teaching import (
    render_explanations,
    render_feedback,
    render_hints,
    render_lesson,
)
from mathquest.engine.templates import plain
from mathquest.engine.types import MathPart, Prompt

CONTENT = Path(__file__).resolve().parents[2] / "content"
CATALOG = load_catalog(CONTENT, "k8-core")
PACK = CATALOG.pack
SKILL = "add_within_20"
SOURCE = CATALOG.source(SKILL)
SEEDS = 200
DASHES = (chr(0x2014), chr(0x2013))  # em dash, en dash


def _problems():
    for tier in range(len(SOURCE.tier_difficulties)):
        for seed in range(SEEDS):
            yield SOURCE.generate(seed, tier)


def _sentences(text: str) -> list[str]:
    return [s for s in re.split(r"(?<=[.?!])\s+", text.strip()) if s]


def test_reference_skill_has_every_kind_of_content() -> None:
    skill = PACK.skills[SKILL]
    assert skill.word_problems_fit
    lesson = PACK.lessons[SKILL]
    assert len(lesson.screens) == 3
    assert any(s.visual is not None and s.visual.kind == "number_line" for s in lesson.screens)
    assert lesson.try_it.tier == 0
    assert len(PACK.hints[SKILL].levels) == 3
    explanations = PACK.explanations[SKILL]
    assert [a.style for a in explanations.approaches] == ["visual", "steps", "story", "worked"]
    assert set(explanations.misconceptions) == set(SOURCE.generator.misconception_keys)
    templates = PACK.word_problems[SKILL].templates
    assert len(templates) == 15
    assert {t.grade_band for t in templates} == {"1"}
    assert all(t.answer_from == "generator_answer" for t in templates)


def test_lesson_renders_with_correct_static_numbers() -> None:
    lesson = render_lesson(PACK.lessons[SKILL])
    text = " ".join(plain(s.body) for s in lesson.screens)
    assert "You land on 13." in text
    assert "8 + 5 = 13" in text
    assert plain(lesson.worked_prompt) == "9 + 6 = ?"
    assert plain(lesson.worked_steps[-1]) == "So 9 + 6 = 15."
    assert lesson.try_it_tier == 0


def test_hints_are_ordered_and_the_last_works_the_answer() -> None:
    for problem in _problems():
        a, b = problem.values["a"], problem.values["b"]
        hints = render_hints(PACK.hints[SKILL], problem)
        assert len(hints) == 3
        assert f"{a}" in plain(hints[0]) and f"{b}" in plain(hints[0])
        assert str(problem.answer) not in plain(hints[0]).split()
        assert MathPart(f"{a} + {b} = {problem.answer}") in hints[2]
        big, small = max(int(a), int(b)), min(int(a), int(b))
        assert plain(hints[1]).startswith(f"Start at {big}, the bigger number. Count on {small}")
        assert plain(hints[2]).startswith(f"Start at {big} and count on {small}.")


def test_the_number_line_shows_this_problem() -> None:
    for problem in _problems():
        visual = render_explanations(PACK.explanations[SKILL], problem)[0].visual
        assert visual is not None and visual.kind == "number_line"
        a, b = int(problem.values["a"]), int(problem.values["b"])
        assert visual.params.model_dump() == {
            "min": 0, "max": 20, "start": max(a, b), "jumps": min(a, b), "end": a + b,
        }  # fmt: skip


def test_explanations_and_feedback_render_for_every_problem() -> None:
    explanations = PACK.explanations[SKILL]
    for problem in _problems():
        approaches = render_explanations(explanations, problem)
        assert len(approaches) == 4
        worked = plain(approaches[3].body)
        assert "7 + 6 = 13" in worked
        for misconception in problem.misconceptions:
            feedback = render_feedback(explanations, problem, misconception.key)
            assert feedback is not None
            assert str(problem.values["a"]) in plain(feedback)
            if misconception.key == "counted_start":
                assert misconception.answer == problem.answer - 1
    assert render_feedback(explanations, SOURCE.generate(1, 0), "unknown_key") is None


def _all_text(prompt: Prompt) -> str:
    return plain(prompt)


def test_word_problems_read_simply() -> None:
    assert SOURCE.word_problems is not None
    for template in SOURCE.word_problems.templates:
        for problem in _problems():
            text = _all_text(
                SOURCE.generate(problem.seed, problem.tier, "word", template.id).prompt
            )
            for sentence in _sentences(text):
                assert len(sentence.split()) <= 12, (template.id, sentence)
            assert text.rstrip().endswith("?"), template.id
            assert str(problem.values["a"]) in text and str(problem.values["b"]) in text


def test_word_problem_answer_is_the_sum() -> None:
    for problem in _problems():
        word = SOURCE.generate(problem.seed, problem.tier, "word")
        a, b = problem.values["a"], problem.values["b"]
        assert word.answer == sympy.Integer(int(a) + int(b))


@pytest.mark.parametrize("path", sorted(CONTENT.rglob("*.yaml")), ids=lambda p: p.name)
def test_content_has_no_long_dashes(path: Path) -> None:
    text = path.read_text(encoding="utf-8")
    for dash in DASHES:
        assert dash not in text, path
