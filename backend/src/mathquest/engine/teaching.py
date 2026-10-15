"""Render a skill's teaching content (lessons, hints, explanations) into prompts.

Lessons are static: their text is rendered with no values, so a computed number in a
lesson (``{{= 9 + 6 }}``) can only use literal numbers. Hints, explanations and
misconception feedback are rendered for a problem, with the generator's values.
Every function is pure and returns prompts (text and math parts) ready to send.
A visual's string parameters are templates too, rendered with the same values; each must
render to a whole number, and the filled-in visual is checked against its kind's params
schema again (``content.visuals.resolve``). A visual that fails raises TemplateError, like
any other text that does not render.
"""

import hashlib
import re
from collections.abc import Collection, Mapping
from dataclasses import dataclass
from typing import Literal

from pydantic import JsonValue

from mathquest.engine.bank import to_prompt
from mathquest.engine.content.schema import (
    ApproachStyle,
    Explanations,
    HintLadder,
    Lesson,
    Pack,
)
from mathquest.engine.content.visuals import UnresolvedVisual, VisualModel, resolve
from mathquest.engine.templates import TemplateError, Value, plain, render
from mathquest.engine.types import Problem, Prompt, TextPart


@dataclass(frozen=True)
class LessonScreen:
    title: str
    body: Prompt
    visual: VisualModel | None


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
    visual: VisualModel | None


_WHOLE = re.compile(r"-?\d+")


def _param(value: JsonValue, values: Mapping[str, Value]) -> JsonValue:
    if isinstance(value, str):
        shown = plain(render(value, values)).strip()
        return int(shown) if _WHOLE.fullmatch(shown) else shown
    if isinstance(value, list):
        return [_param(item, values) for item in value]
    if isinstance(value, dict):
        return {k: _param(item, values) for k, item in value.items()}
    return value


def render_visual(visual: VisualModel | None, values: Mapping[str, Value]) -> VisualModel | None:
    """``visual`` with its template parameters filled in from ``values`` and checked."""
    if visual is None:
        return None
    raw: dict[str, JsonValue] = visual.params.model_dump(mode="json")
    params = {k: _param(v, values) for k, v in raw.items()}
    try:
        return resolve(visual, params)
    except UnresolvedVisual as err:
        raise TemplateError(str(err)) from None


def render_lesson(lesson: Lesson) -> RenderedLesson:
    return RenderedLesson(
        skill_id=lesson.skill,
        screens=tuple(
            LessonScreen(s.title, render(s.body_md, {}), render_visual(s.visual, {}))
            for s in lesson.screens
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
        RenderedApproach(
            a.style, render(a.body_md, problem.values), render_visual(a.visual, problem.values)
        )
        for a in explanations.approaches
    )


def render_feedback(explanations: Explanations, problem: Problem, key: str) -> Prompt | None:
    """Feedback for misconception ``key`` on ``problem``; None when there is none."""
    template = explanations.misconceptions.get(key)
    return None if template is None else render(template, problem.values)


def hint_count(pack: Pack, skill_id: str) -> int:
    """How many hint levels the skill has; 0 without a hint ladder."""
    ladder = pack.hints.get(skill_id)
    return 0 if ladder is None else len(ladder.levels)


FeedbackKind = Literal["misconception", "hint", "retry"]

FEEDBACK_COPY: Mapping[Literal["hint", "retry"], str] = {
    "hint": "Not quite. Try a hint.",
    "retry": "Not quite. Read it again and have one more go.",
}
"""The generic lines after a wrong answer that matched no known mistake: ``hint`` when a
hint is still there to ask for, ``retry`` otherwise. Kid-facing; no dashes."""


@dataclass(frozen=True)
class Feedback:
    kind: FeedbackKind
    text: Prompt


def answer_feedback(
    explanations: Explanations | None,
    problem: Problem,
    misconception: str | None,
    *,
    scored: bool,
    hint_available: bool,
) -> Feedback | None:
    """What to say after an incorrect answer to ``problem``.

    A matched mistake with feedback written gets that feedback, rendered with the
    problem's values. Otherwise, while the problem is still open, a short generic line
    (``FEEDBACK_COPY``). A problem just scored wrong with no matched mistake gets None:
    its answer is revealed instead. Call it only for an INCORRECT verdict. None of these
    texts states the answer (the content lint checks the written feedback).
    """
    if misconception is not None and explanations is not None:
        text = render_feedback(explanations, problem, misconception)
        if text is not None:
            return Feedback("misconception", text)
    if scored:
        return None
    kind: Literal["hint", "retry"] = "hint" if hint_available else "retry"
    return Feedback(kind, (TextPart(FEEDBACK_COPY[kind]),))


def first_approach(player_key: str, skill_id: str, count: int) -> int:
    """Where a player's rotation through a skill's ``count`` approaches starts: a stable
    hash of the player and skill, so different players meet a different one first."""
    digest = hashlib.sha256(f"{player_key}:{skill_id}".encode()).digest()
    return int.from_bytes(digest[:8], "big") % count


def next_approach(player_key: str, skill_id: str, count: int, shown_before: int) -> int:
    """The index of the approach to show after ``shown_before`` were shown to this player
    for this skill: the rotation moves on by one each time and wraps around."""
    return (first_approach(player_key, skill_id, count) + shown_before) % count


def all_approaches_shown(count: int, shown: Collection[int]) -> bool:
    """Every one of a skill's ``count`` approaches is among ``shown``."""
    return count > 0 and set(range(count)) <= set(shown)
