# pyright: reportUnknownMemberType=false, reportUnknownArgumentType=false
"""How prompts and answers are sent: the one mapping every API response uses."""

from typing import Literal

import sympy
from pydantic import BaseModel, ConfigDict

from mathquest.engine.types import Problem, Prompt, TextPart


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


def latex(value: sympy.Expr) -> str:
    """An exact value as the LaTeX the answer checker reads."""
    return str(sympy.latex(value))


def answer_latex(problem: Problem) -> str | None:
    """The answer as LaTeX; None for a choice problem, whose answer is an index."""
    return None if problem.choices is not None else latex(problem.answer)
