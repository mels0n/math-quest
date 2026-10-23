"""Content pack schemas.

Every file of a pack is validated against one of these models when it is loaded. All
models are frozen and reject unknown fields, so a typo in a field name is an error
rather than a silently ignored line. Checks that need more than one file (a skill's
region exists, prerequisites exist, files name known skills) live in the loader; checks
that need the generator registry (generator ids, tier counts, misconception keys) live
in ``mathquest.engine.catalog``.
"""

from typing import Annotated, Literal, Self

from pydantic import (
    AfterValidator,
    BaseModel,
    BeforeValidator,
    ConfigDict,
    Field,
    StrictInt,
    StringConstraints,
    model_validator,
)

from mathquest.engine.checker.latex import Unreadable, parse
from mathquest.engine.content.visuals import Visual
from mathquest.engine.templates import check_expression, check_template
from mathquest.engine.types import KeypadProfile


class _Model(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


Id = Annotated[str, StringConstraints(pattern=r"^[a-z][a-z0-9_]*$")]
PackId = Annotated[str, StringConstraints(pattern=r"^[a-z][a-z0-9_-]*$")]
Text = Annotated[str, StringConstraints(min_length=1)]
Template = Annotated[str, StringConstraints(min_length=1), AfterValidator(check_template)]
"""Kid-facing text in the template language of ``mathquest.engine.templates``."""
Expression = Annotated[str, StringConstraints(min_length=1), AfterValidator(check_expression)]

MIN_CHOICES = 2
"""A choice needs two answers to pick from. With exactly two, only the first try counts
(docs/adr/0023-two-option-items-count-the-first-try.md)."""

GRADE_BANDS = ("K", "1", "2", "3", "4", "5", "6", "7", "8", "A1", "A2")


def _grade_text(value: object) -> object:
    # YAML reads `grade_band: 1` as a number; the band is a label.
    return str(value) if isinstance(value, int) and not isinstance(value, bool) else value


GradeBand = Annotated[
    Literal["K", "1", "2", "3", "4", "5", "6", "7", "8", "A1", "A2"],
    BeforeValidator(_grade_text),
]
SlotType = Literal[
    "names", "objects", "length_units", "time_units", "money_units", "contexts", "number"
]  # fmt: skip
ApproachStyle = Literal["visual", "steps", "story", "worked"]


def _unique(values: list[str], what: str) -> None:
    seen: set[str] = set()
    for value in values:
        if value in seen:
            raise ValueError(f"duplicate {what}: {value}")
        seen.add(value)


class Part(_Model):
    """A prompt part written in content: words, or a LaTeX math expression."""

    kind: Literal["text", "math"]
    value: Text

    @model_validator(mode="after")
    def _no_text_in_math(self) -> Self:
        if self.kind == "math" and r"\text" in self.value:
            raise ValueError(r"words belong in a text part, not \text in a math part")
        return self


Parts = Annotated[tuple[Part, ...], Field(min_length=1)]


Standard = Annotated[
    str,
    StringConstraints(
        pattern=r"^(K|[1-8])\.(CC|OA|NBT|NF|MD|G|RP|NS|EE|F|SP)\.[A-E]\.[0-9]{1,2}[a-z]?$"
    ),
]
"""A Common Core State Standards code such as ``K.CC.A.1`` or ``2.NBT.B.5``."""


class Tier(_Model):
    id: Annotated[int, Field(ge=0)]
    label: Text


class Skill(_Model):
    id: Id
    name: Text
    region: Id
    prerequisites: tuple[Id, ...] = ()
    fluency: bool
    anchor: bool
    generator: Id
    tiers: Annotated[tuple[Tier, ...], Field(min_length=1)]
    grade_band: GradeBand
    keypad: KeypadProfile
    word_problems_fit: bool = False
    word_share: Annotated[float, Field(ge=0.0, le=1.0)] = 0.4
    banked: bool = False
    bank_share: Annotated[float, Field(ge=0.0, le=1.0)] = 0.25
    vocabulary: tuple[Annotated[str, StringConstraints(pattern=r"^[a-z][a-z']*$")], ...] = ()
    """Words the content lint accepts in this skill's early-reader text beyond the
    shared simple word list (lowercase, one word each)."""
    standards: tuple[Standard, ...] = ()
    """Common Core codes the skill covers, carried over from the planned graph."""

    @model_validator(mode="after")
    def _consistent(self) -> Self:
        ids = [t.id for t in self.tiers]
        if ids != list(range(len(ids))):
            raise ValueError("tier ids must be 0, 1, 2, ... in order")
        if self.word_share + self.bank_share > 1.0:
            raise ValueError("word_share + bank_share must not exceed 1")
        return self


class PlannedSkill(_Model):
    """A skill on the build plan: a ``Skill`` with no generator yet.

    ``batch`` is the build order. ``unlocks`` names skills (built or planned) that gain
    this one as a prerequisite when it is built; it is how a plan puts a new foundation
    under a skill that already exists.
    """

    id: Id
    name: Text
    region: Id
    prerequisites: tuple[Id, ...] = ()
    unlocks: tuple[Id, ...] = ()
    fluency: bool
    anchor: bool
    tiers: Annotated[tuple[Tier, ...], Field(min_length=1)]
    grade_band: GradeBand
    keypad: KeypadProfile
    word_problems_fit: bool = False
    banked: bool = False
    standards: Annotated[tuple[Standard, ...], Field(min_length=1)]
    batch: Annotated[int, Field(ge=1)]

    @model_validator(mode="after")
    def _consistent(self) -> Self:
        ids = [t.id for t in self.tiers]
        if ids != list(range(len(ids))):
            raise ValueError("tier ids must be 0, 1, 2, ... in order")
        if self.keypad == "choice" and not self.banked:
            raise ValueError("a choice keypad needs banked: true")
        return self


class PlanScope(_Model):
    """The part of the map a plan covers."""

    regions: Annotated[tuple[Id, ...], Field(min_length=1)]
    grade_bands: Annotated[tuple[GradeBand, ...], Field(min_length=1)]


class PlannedList(_Model):
    """``planned_skills.yaml``: skills to build, never loaded for play or placement."""

    scope: PlanScope
    planned: tuple[PlannedSkill, ...]


class Screen(_Model):
    title: Text
    body_md: Template
    visual: Visual | None = None


class WorkedExample(_Model):
    prompt: Parts
    steps: Annotated[tuple[Template, ...], Field(min_length=1)]


class TryIt(_Model):
    tier: Annotated[int, Field(ge=0)]
    seed_hint: int | None = None


class Lesson(_Model):
    skill: Id
    screens: Annotated[tuple[Screen, ...], Field(min_length=2, max_length=4)]
    worked_example: WorkedExample
    try_it: TryIt


class HintLevel(_Model):
    text_template: Template


class HintLadder(_Model):
    skill: Id
    levels: Annotated[tuple[HintLevel, ...], Field(min_length=3, max_length=3)]


class Approach(_Model):
    style: ApproachStyle
    body_md: Template
    visual: Visual | None = None


class Explanations(_Model):
    skill: Id
    approaches: Annotated[tuple[Approach, ...], Field(min_length=3, max_length=4)]
    misconceptions: dict[Id, Template] = Field(default_factory=dict[str, str])

    @model_validator(mode="after")
    def _distinct_styles(self) -> Self:
        _unique([a.style for a in self.approaches], "approach style")
        return self


class WordTemplate(_Model):
    id: Id
    text_template: Template
    slots: dict[Id, SlotType] = Field(default_factory=dict[str, SlotType])
    answer_from: Literal["generator_answer", "expression"] = "generator_answer"
    expression: Expression | None = None
    grade_band: GradeBand
    tiers: Annotated[tuple[int, ...], Field(min_length=1)] | None = None
    """The tiers this template serves; unset, every tier."""

    @model_validator(mode="after")
    def _expression_when_needed(self) -> Self:
        if (self.answer_from == "expression") != (self.expression is not None):
            raise ValueError("expression is required exactly when answer_from is expression")
        return self


class WordProblems(_Model):
    skill: Id
    templates: Annotated[tuple[WordTemplate, ...], Field(min_length=1)]

    @model_validator(mode="after")
    def _unique_ids(self) -> Self:
        _unique([t.id for t in self.templates], "template id")
        return self


class BankAnswer(_Model):
    kind: Literal["choice", "expr"]
    value: StrictInt | Text


class BankItem(_Model):
    id: Id
    tier: Annotated[int, Field(ge=0)] | None = None
    """The tier the item suits; a learner only gets items of their own tier. None suits
    every tier."""
    prompt: Parts
    answer: BankAnswer
    choices: tuple[Parts, ...] | None = None

    @model_validator(mode="after")
    def _answer_matches_kind(self) -> Self:
        value = self.answer.value
        if self.answer.kind == "expr":
            if not isinstance(value, str):
                raise ValueError("an expr answer is LaTeX text")
            if self.choices is not None:
                raise ValueError("an expr answer takes no choices")
            try:
                parse(value)
            except Unreadable as err:
                raise ValueError(f"answer does not parse: {err}") from None
            return self
        if not isinstance(value, int):
            raise ValueError("a choice answer is the index of the right choice")
        if self.choices is None or len(self.choices) < MIN_CHOICES:
            raise ValueError(f"a choice answer needs at least {MIN_CHOICES} choices")
        if not 0 <= value < len(self.choices):
            raise ValueError(f"choice index {value} is out of range")
        if len(set(self.choices)) != len(self.choices):
            raise ValueError("choices must be different from each other")
        return self


class Bank(_Model):
    skill: Id
    items: Annotated[tuple[BankItem, ...], Field(min_length=1)]

    @model_validator(mode="after")
    def _unique_ids(self) -> Self:
        _unique([i.id for i in self.items], "item id")
        return self


class Region(_Model):
    id: Id
    name: Text
    order: Annotated[int, Field(ge=1)]
    creature_family: Id
    boss_skill_set: tuple[Id, ...] = ()
    map_hint: Text


class World(_Model):
    regions: Annotated[tuple[Region, ...], Field(min_length=1)]

    @model_validator(mode="after")
    def _unique(self) -> Self:
        _unique([r.id for r in self.regions], "region id")
        _unique([str(r.order) for r in self.regions], "region order")
        return self


class PackMeta(_Model):
    """``pack.yaml``."""

    id: PackId
    title: Text
    version: Annotated[str, StringConstraints(pattern=r"^\d+\.\d+\.\d+$")]
    complete_regions: tuple[Id, ...] = ()


class SkillList(_Model):
    """``skills.yaml``."""

    skills: tuple[Skill, ...]


class Noun(_Model):
    """A countable thing: ``{obj.one}`` is the singular, ``{obj}`` the plural.

    ``article`` overrides the article ``{obj.a}`` would otherwise pick from spelling.
    """

    one: Text
    many: Text
    article: Literal["a", "an"] | None = None


class Slots(_Model):
    """``content/slots.yaml``: the shared word lists word-problem slots draw from."""

    names: Annotated[tuple[Text, ...], Field(min_length=40)]
    objects: Annotated[tuple[Noun, ...], Field(min_length=40)]
    length_units: Annotated[tuple[Noun, ...], Field(min_length=1)]
    time_units: Annotated[tuple[Noun, ...], Field(min_length=1)]
    money_units: Annotated[tuple[Noun, ...], Field(min_length=1)]
    contexts: Annotated[tuple[Text, ...], Field(min_length=1)]

    @model_validator(mode="after")
    def _no_repeats(self) -> Self:
        _unique(list(self.names), "name")
        _unique([o.many for o in self.objects], "object")
        _unique([u.many for u in (*self.length_units, *self.time_units, *self.money_units)], "unit")
        _unique(list(self.contexts), "context")
        return self


class Pack(_Model):
    """A whole loaded pack. Teaching content is keyed by skill id."""

    id: PackId
    title: Text
    version: str
    complete_regions: tuple[Id, ...]
    skills: dict[Id, Skill]
    world: World
    lessons: dict[Id, Lesson]
    hints: dict[Id, HintLadder]
    explanations: dict[Id, Explanations]
    word_problems: dict[Id, WordProblems]
    bank: dict[Id, Bank]
