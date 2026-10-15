"""Value objects returned by the placement service (never database rows)."""

import uuid
from typing import Literal

from pydantic import BaseModel, ConfigDict

from mathquest.engine.checker.check import Verdict
from mathquest.engine.transport import PromptPartOut
from mathquest.engine.types import KeypadProfile


class _Frozen(BaseModel):
    model_config = ConfigDict(frozen=True)


class PlacementProblemOut(_Frozen):
    """A placement problem, in the same shape as a play problem so the same card draws
    it. Placement offers no lesson, hints or explanations."""

    type: Literal["problem"] = "problem"
    problem_id: uuid.UUID
    skill_id: str
    skill_name: str
    prompt: list[PromptPartOut]
    keypad: KeypadProfile
    choices: list[list[PromptPartOut]] | None = None
    has_lesson: Literal[False] = False
    hint_levels: Literal[0] = 0
    has_explanations: Literal[False] = False
    dev_answer_latex: str | None = None
    dev_answer_choice: int | None = None


class PlacementStepOut(_Frozen):
    """The next question of a placement round.

    ``retry`` is set when the last answer could not be read or was in the wrong form:
    the same problem is asked again and nothing was counted."""

    done: Literal[False] = False
    placement_id: uuid.UUID
    problem: PlacementProblemOut
    question: int
    """1 for the first question; a retried question keeps its number."""
    max_questions: int
    retry: Literal[Verdict.UNREADABLE, Verdict.WRONG_FORM] | None = None


class RegionOut(_Frozen):
    id: str
    name: str


class PlacementDoneOut(_Frozen):
    """The outcome of a finished round. It never says which answers were right."""

    done: Literal[True] = True
    placement_id: uuid.UUID
    frontier: list[str]
    """The highest anchor skill passed; empty when none was."""
    provisional: list[str]
    """Skills now provisionally mastered (never including skills already mastered)."""
    revealed_regions: list[RegionOut]
    """Regions now open on the map, in map order."""
