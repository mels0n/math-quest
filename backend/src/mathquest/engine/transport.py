# pyright: reportUnknownMemberType=false, reportUnknownArgumentType=false
"""How prompts and answers are sent: the one mapping every API response uses."""

from typing import Literal

import sympy
from pydantic import BaseModel, ConfigDict, JsonValue

from mathquest.engine.content.visuals import VisualKind, VisualModel
from mathquest.engine.teaching import Feedback, FeedbackKind
from mathquest.engine.types import KeypadProfile, Problem, Prompt, TextPart


class PromptPartOut(BaseModel):
    """One part of a prompt: words shown as text, or a math expression as LaTeX."""

    model_config = ConfigDict(frozen=True)

    kind: Literal["text", "math"]
    value: str


def prompt_out(prompt: Prompt) -> list[PromptPartOut]:
    return [
        PromptPartOut(kind="text", value=part.text)
        if isinstance(part, TextPart)
        else PromptPartOut(kind="math", value=part.latex)
        for part in prompt
    ]


class VisualOut(BaseModel):
    """A visual to draw: its kind and its params with every template filled in."""

    model_config = ConfigDict(frozen=True)

    kind: VisualKind
    params: dict[str, JsonValue]


def visual_out(visual: VisualModel | None) -> VisualOut | None:
    if visual is None:
        return None
    return VisualOut(kind=visual.kind, params=visual.params.model_dump(mode="json"))


class FeedbackOut(BaseModel):
    """What to tell the learner after a wrong answer. ``text`` is words and math; it
    never states the answer."""

    model_config = ConfigDict(frozen=True)

    kind: FeedbackKind
    text: list[PromptPartOut]


def feedback_out(feedback: Feedback | None) -> FeedbackOut | None:
    return (
        None
        if feedback is None
        else FeedbackOut(kind=feedback.kind, text=prompt_out(feedback.text))
    )


def latex(value: sympy.Expr) -> str:
    """An exact value as the LaTeX the answer checker reads."""
    return str(sympy.latex(value))


def answer_latex(problem: Problem) -> str | None:
    """The answer as LaTeX; None for a choice problem, whose answer is an index."""
    return None if problem.choices is not None else latex(problem.answer)


def keypad_for(problem: Problem, declared: KeypadProfile) -> KeypadProfile:
    """Choice buttons for a choice problem, else the skill's own keypad."""
    return "choice" if problem.choices is not None else declared
