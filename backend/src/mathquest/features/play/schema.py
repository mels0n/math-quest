"""Value objects returned by the play service (never database rows)."""

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict

from mathquest.engine.checker.check import Verdict
from mathquest.engine.mastery import SkillState
from mathquest.engine.types import KeypadProfile


class _Frozen(BaseModel):
    model_config = ConfigDict(frozen=True)


class SessionOut(_Frozen):
    session_id: uuid.UUID
    mode: Literal["adventure"]
    started_at: datetime
    problem_count: int


class PromptPartOut(_Frozen):
    """One part of a prompt: words shown as text, or a math expression as LaTeX."""

    kind: Literal["text", "math"]
    value: str


class ProblemOut(_Frozen):
    """An issued problem. ``choices`` is set (and ``keypad`` is "choice") only for a
    multiple-choice problem, which is answered with a choice index."""

    problem_id: uuid.UUID
    skill_id: str
    skill_name: str
    prompt: list[PromptPartOut]
    keypad: KeypadProfile
    choices: list[list[PromptPartOut]] | None = None
    dev_answer_latex: str | None = None
    dev_answer_choice: int | None = None


class MasteryOut(_Frozen):
    skill_id: str
    state: SkillState
    progress: float


class AnswerOut(_Frozen):
    verdict: Verdict
    misconception: str | None
    solved: bool
    attempts_left: int
    mastery: MasteryOut
    answer_latex: str | None = None
    answer_choice: int | None = None
    total_solved: int
