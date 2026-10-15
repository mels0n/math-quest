"""Value objects returned by the play service (never database rows)."""

import uuid
from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field

from mathquest.engine.checker.check import Verdict
from mathquest.engine.mastery import SkillState
from mathquest.engine.teaching import FeedbackKind
from mathquest.engine.transport import PromptPartOut
from mathquest.engine.types import KeypadProfile


class _Frozen(BaseModel):
    model_config = ConfigDict(frozen=True)


class SessionOut(_Frozen):
    session_id: uuid.UUID
    mode: Literal["adventure"]
    started_at: datetime
    problem_count: int


class ProblemOut(_Frozen):
    """An issued problem. ``choices`` is set (and ``keypad`` is "choice") only for a
    multiple-choice problem, which is answered with a choice index."""

    type: Literal["problem"] = "problem"
    problem_id: uuid.UUID
    skill_id: str
    skill_name: str
    prompt: list[PromptPartOut]
    keypad: KeypadProfile
    choices: list[list[PromptPartOut]] | None = None
    has_lesson: bool = False
    """The skill has a lesson the player can replay (GET /api/lessons/{skill_id})."""
    hint_levels: int = 0
    """How many hint levels this problem offers (POST .../hint); 0 for none."""
    has_explanations: bool = False
    """The problem offers "explain it another way" (POST .../explain)."""
    dev_answer_latex: str | None = None
    dev_answer_choice: int | None = None


class LessonDueOut(_Frozen):
    """Shown instead of a problem before the first problem of a skill whose lesson the
    player has not seen. The lesson itself is read from the lessons routes."""

    type: Literal["lesson"] = "lesson"
    skill_id: str
    skill_name: str


NextOut = Annotated[ProblemOut | LessonDueOut, Field(discriminator="type")]
"""What ``next`` returns: a problem, or a lesson to show first."""


class MasteryOut(_Frozen):
    skill_id: str
    state: SkillState
    progress: float


class FeedbackOut(_Frozen):
    """What to tell the learner after a wrong answer. ``text`` is words and math; it
    never states the answer."""

    kind: FeedbackKind
    text: list[PromptPartOut]


class AnswerOut(_Frozen):
    verdict: Verdict
    misconception: str | None
    feedback: FeedbackOut | None = None
    solved: bool
    attempts_left: int
    mastery: MasteryOut
    answer_latex: str | None = None
    answer_choice: int | None = None
    total_solved: int
