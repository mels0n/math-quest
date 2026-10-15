"""Render a skill's teaching content (lessons, hints, explanations) into prompts.

Lessons are static: their text is rendered with no values, so a computed number in a
lesson (``{{= 9 + 6 }}``) can only use literal numbers. Hints, explanations and
misconception feedback are rendered for a problem, with the generator's values.
Every function is pure and returns prompts (text and math parts) ready to send.
"""

from dataclasses import dataclass

from mathquest.engine.bank import to_prompt
from mathquest.engine.content.schema import (
    ApproachStyle,
    Explanations,
    HintLadder,
    Lesson,
    Visual,
)
from mathquest.engine.templates import render
from mathquest.engine.types import Problem, Prompt


@dataclass(frozen=True)
class LessonScreen:
    title: str
    body: Prompt
    visual: Visual | None


@dataclass(frozen=True)
class RenderedLesson:
    skill_id: str
    screens: tuple[LessonScreen, ...]
    worked_prompt: Prompt
    worked_steps: tuple[Prompt, ...]
    try_it_tier: int
    try_it_seed: int | None


@dataclass(frozen=True)
class RenderedApproach:
    style: ApproachStyle
    body: Prompt
    visual: Visual | None


def render_lesson(lesson: Lesson) -> RenderedLesson:
    return RenderedLesson(
        skill_id=lesson.skill,
        screens=tuple(
            LessonScreen(s.title, render(s.body_md, {}), s.visual) for s in lesson.screens
        ),
        worked_prompt=to_prompt(lesson.worked_example.prompt),
        worked_steps=tuple(render(step, {}) for step in lesson.worked_example.steps),
        try_it_tier=lesson.try_it.tier,
        try_it_seed=lesson.try_it.seed_hint,
    )


def render_hints(ladder: HintLadder, problem: Problem) -> tuple[Prompt, ...]:
    """The three hint levels for ``problem``, gentlest first."""
    return tuple(render(level.text_template, problem.values) for level in ladder.levels)


def render_explanations(
    explanations: Explanations, problem: Problem
) -> tuple[RenderedApproach, ...]:
    return tuple(
        RenderedApproach(a.style, render(a.body_md, problem.values), a.visual)
        for a in explanations.approaches
    )


def render_feedback(explanations: Explanations, problem: Problem, key: str) -> Prompt | None:
    """Feedback for misconception ``key`` on ``problem``; None when there is none."""
    template = explanations.misconceptions.get(key)
    return None if template is None else render(template, problem.values)
