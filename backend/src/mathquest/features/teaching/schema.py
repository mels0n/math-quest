"""Value objects returned by the teaching service (never database rows)."""

import uuid

from pydantic import BaseModel, ConfigDict

from mathquest.engine.checker.check import Verdict
from mathquest.engine.content.schema import ApproachStyle
from mathquest.engine.transport import FeedbackOut, PromptPartOut, VisualOut
from mathquest.engine.types import KeypadProfile


class _Frozen(BaseModel):
    model_config = ConfigDict(frozen=True)


type PromptOut = list[PromptPartOut]


class LessonScreenOut(_Frozen):
    title: str
    body: PromptOut
    """The screen's text as prompt parts (words and math), rendered from its body_md."""
    visual: VisualOut | None


class WorkedExampleOut(_Frozen):
    prompt: PromptOut
    steps: list[PromptOut]


class TryItOut(_Frozen):
    tier: int


class LessonOut(_Frozen):
    skill_id: str
    skill_name: str
    screens: list[LessonScreenOut]
    worked_example: WorkedExampleOut
    try_it: TryItOut


class SeenOut(_Frozen):
    skill_id: str
    seen: bool


class TryProblemOut(_Frozen):
    """A lesson's practice problem. It is answered like a play problem but never
    changes mastery or the solved count."""

    try_id: uuid.UUID
    skill_id: str
    skill_name: str
    prompt: PromptOut
    keypad: KeypadProfile
    dev_answer_latex: str | None = None


class TryAnswerOut(_Frozen):
    verdict: Verdict
    misconception: str | None
    feedback: FeedbackOut | None = None
    solved: bool
    attempts_left: int
    answer_latex: str | None
    """Sent once the practice problem is solved or out of tries."""


class HintOut(_Frozen):
    """One hint level for a play problem, gentlest first; level 3 works the problem."""

    level: int
    levels: int
    text: PromptOut


class ExplanationOut(_Frozen):
    """One way of explaining a play problem's skill, rendered with the problem's numbers."""

    approach: int
    """Which of the skill's approaches this is (0-based, in file order)."""
    approaches: int
    style: ApproachStyle
    body: PromptOut
    visual: VisualOut | None


class StuckProblemOut(_Frozen):
    """One stuck problem in the export: what the content coverage report reads with
    ``--stuck``. It carries no player identity."""

    skill: str
    generator: str
    tier: int
    seed: int
    wrong_answers: list[str]
