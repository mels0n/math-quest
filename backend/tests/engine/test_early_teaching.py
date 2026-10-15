"""Teaching content of the first two skills: complete, renders for every problem, no leaks."""

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
from mathquest.engine.transport import latex

CONTENT = Path(__file__).resolve().parents[2] / "content"
CATALOG = load_catalog(CONTENT, "k8-core")
PACK = CATALOG.pack
SKILLS = ("add_within_10", "sub_within_10")
SEEDS = 100


@pytest.mark.parametrize("skill_id", SKILLS)
def test_skill_meets_every_coverage_target(skill_id: str) -> None:
    source = CATALOG.source(skill_id)
    coverage = skill_coverage(PACK, source.skill, source.generator)
    assert coverage.gaps == ()
    assert coverage.misconceptions >= 2
    assert coverage.feedback == coverage.misconceptions


@pytest.mark.parametrize("skill_id", SKILLS)
def test_lesson_has_a_visual_a_worked_example_and_a_try_it(skill_id: str) -> None:
    lesson = render_lesson(PACK.lessons[skill_id])
    assert 2 <= len(lesson.screens) <= 4
    assert any(s.visual is not None for s in lesson.screens)
    assert lesson.worked_steps
    assert lesson.try_it_tier == 0


@pytest.mark.parametrize("skill_id", SKILLS)
def test_teaching_renders_for_every_problem_and_feedback_hides_the_answer(skill_id: str) -> None:
    source = CATALOG.source(skill_id)
    explanations = PACK.explanations[skill_id]
    for tier in range(len(source.tier_difficulties)):
        for seed in range(SEEDS):
            problem = source.generate(seed, tier)
            answer = latex(problem.answer)
            hints = [plain(h) for h in render_hints(PACK.hints[skill_id], problem)]
            assert len(hints) == 3
            assert f"= {answer}" not in hints[0] + hints[1]
            assert f"= {answer}" in hints[2]
            assert len(render_explanations(explanations, problem)) >= 3
            for wrong in problem.misconceptions:
                feedback = render_feedback(explanations, problem, wrong.key)
                assert feedback is not None
                assert f"= {answer}" not in plain(feedback)
