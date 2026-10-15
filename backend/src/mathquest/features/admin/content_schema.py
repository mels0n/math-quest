"""Response models of the admin content preview. Admin may see answers."""

from typing import Literal

from pydantic import BaseModel, ConfigDict

from mathquest.engine.transport import PromptPartOut, VisualOut
from mathquest.engine.types import KeypadProfile


class _Frozen(BaseModel):
    model_config = ConfigDict(frozen=True)


type PromptOut = list[PromptPartOut]


class GapOut(_Frozen):
    field: str
    have: int
    want: int


class SkillCoverageOut(_Frozen):
    skill_id: str
    name: str
    tiers: int
    misconceptions: int
    feedback: int
    word_templates: int | None
    bank_items: int | None
    lesson: bool
    hints: int
    explanations: int
    gaps: list[GapOut]


class RegionCoverageOut(_Frozen):
    region_id: str
    name: str
    complete: bool
    skills: list[SkillCoverageOut]


class PackOut(_Frozen):
    id: str
    title: str
    version: str
    live: bool
    """The pack the running app serves."""
    complete_regions: list[str]
    regions: list[RegionCoverageOut]


class ContentOverview(_Frozen):
    packs: list[PackOut]
    targets: dict[str, str]
    """Each coverage target as shown, such as "3-4" for explanations."""


class LessonScreenOut(_Frozen):
    title: str
    body: PromptOut
    visual: VisualOut | None


class LessonOut(_Frozen):
    screens: list[LessonScreenOut]
    worked_prompt: PromptOut
    worked_steps: list[PromptOut]
    try_it_tier: int
    try_it_seed: int | None


class ApproachOut(_Frozen):
    style: str
    body: PromptOut
    visual: VisualOut | None


class MisconceptionOut(_Frozen):
    key: str
    answer_latex: str
    feedback: PromptOut | None
    """The feedback text for this mistake, or None when none is written."""


class ProblemPreview(_Frozen):
    """One rendered problem with its answer, or the error that stopped it rendering."""

    seed: int
    tier: int
    prompt: PromptOut
    answer_latex: str | None
    choices: list[PromptOut] | None
    correct_choice: int | None
    misconceptions: list[MisconceptionOut]
    error: str | None = None


class WordTemplateOut(_Frozen):
    id: str
    grade_band: str
    answer_from: Literal["generator_answer", "expression"]
    samples: list[ProblemPreview]


class BankItemOut(_Frozen):
    id: str
    kind: Literal["choice", "expr"]
    sample: ProblemPreview


class SkillPreview(_Frozen):
    skill_id: str
    name: str
    region: str
    grade_band: str
    keypad: KeypadProfile
    tier_labels: list[str]
    tier: int
    seeds: list[int]
    coverage: SkillCoverageOut
    problems: list[ProblemPreview]
    """The bare generated problem for each seed; hints and explanations use the first."""
    lesson: LessonOut | None
    hints: list[PromptOut] | None
    explanations: list[ApproachOut] | None
    word_templates: list[WordTemplateOut]
    bank_items: list[BankItemOut]
    errors: list[str]
    """Sections that failed to render, with the reason. Empty for a linted pack."""
