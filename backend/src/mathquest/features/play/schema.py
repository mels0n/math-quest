"""Value objects returned by the play service (never database rows)."""

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict

from mathquest.engine.checker.check import Verdict
from mathquest.engine.mastery import SkillState


class _Frozen(BaseModel):
    model_config = ConfigDict(frozen=True)


class SessionOut(_Frozen):
    session_id: uuid.UUID
    mode: Literal["adventure"]
    started_at: datetime
    problem_count: int


class ProblemOut(_Frozen):
    problem_id: uuid.UUID
    skill_id: str
    skill_name: str
    prompt_latex: str
    keypad: str
    dev_answer_latex: str | None = None


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
    total_solved: int
