"""Value objects returned by the play service (never database rows)."""

import uuid
from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field

from mathquest.engine.checker.check import Verdict
from mathquest.engine.mastery import SkillState
from mathquest.engine.transport import FeedbackOut, PromptPartOut
from mathquest.engine.types import KeypadProfile


class _Frozen(BaseModel):
    model_config = ConfigDict(frozen=True)


Mode = Literal["adventure", "practice"]


class SkillNameOut(_Frozen):
    skill_id: str
    name: str


class SessionOut(_Frozen):
    session_id: uuid.UUID
    mode: Mode
    started_at: datetime
    problem_count: int
    focus: list[SkillNameOut] = []
    """A practice session's skills; empty for an adventure."""


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


class SummaryOut(_Frozen):
    """How a finished session went. ``accuracy`` is correct over scored problems (None
    when none was scored); ``seconds`` runs from the first problem issued to the last
    answer received, as the server measured them."""

    type: Literal["summary"] = "summary"
    session_id: uuid.UUID
    mode: Mode
    skills_practiced: list[SkillNameOut]
    newly_mastered: list[SkillNameOut]
    problems_solved: int
    problems_scored: int
    accuracy: float | None
    seconds: int


NextOut = Annotated[ProblemOut | LessonDueOut | SummaryOut, Field(discriminator="type")]
"""What ``next`` returns: a problem, a lesson to show first, or the summary of a
session that has ended."""


class MasteryOut(_Frozen):
    skill_id: str
    state: SkillState
    progress: float


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


class SkillOut(_Frozen):
    """One skill as the practice picker shows it."""

    skill_id: str
    name: str
    region: str
    state: SkillState
    progress: float
    has_lesson: bool


class RegionOut(_Frozen):
    """A region of the map, in the same shape placement reports regions."""

    id: str
    name: str


class SkillsOut(_Frozen):
    """Every skill of the pack in map order (regions by their order, skills in
    topological order inside each), with the player's state of each."""

    regions: list[RegionOut]
    skills: list[SkillOut]
