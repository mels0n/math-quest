"""Core engine types: problems, generators and answer forms."""

from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Literal, Protocol, get_args

import sympy


class AnswerForm(StrEnum):
    ANY = "any"
    INTEGER = "integer"
    LOWEST_TERMS = "lowest_terms"
    MIXED_NUMBER = "mixed_number"
    SIMPLIFIED_RADICAL = "simplified_radical"
    FACTORED = "factored"
    EXPANDED = "expanded"


@dataclass(frozen=True)
class Misconception:
    """A known wrong answer and the key naming the error that produces it."""

    key: str
    answer: sympy.Expr


@dataclass(frozen=True)
class TextPart:
    """Words of a prompt, shown as wrapping text. Carries its own spacing."""

    text: str


@dataclass(frozen=True)
class MathPart:
    """A math expression of a prompt, as LaTeX. Never contains ``\\text``."""

    latex: str


type PromptPart = TextPart | MathPart
type Prompt = tuple[PromptPart, ...]

Variant = Literal["bare", "word", "bank"]
VARIANTS: tuple[Variant, ...] = get_args(Variant)

KeypadProfile = Literal[
    "numpad", "numpad_neg", "fraction", "mixed", "decimal", "exponent", "algebra", "choice"
]
KEYPAD_PROFILES: tuple[KeypadProfile, ...] = get_args(KeypadProfile)


@dataclass(frozen=True)
class Problem:
    """A generated problem.

    ``values`` holds the named numbers the generator chose (for hint and word-problem
    templates). ``variant`` and ``template_id`` say how the prompt is presented: today
    every problem is the "bare" variant with no template.
    """

    skill_id: str
    tier: int
    seed: int
    prompt: Prompt
    answer: sympy.Expr
    form: AnswerForm
    misconceptions: tuple[Misconception, ...]
    difficulty: float
    keypad: str
    values: Mapping[str, int | str] = field(default_factory=dict[str, int | str], hash=False)
    variant: Variant = "bare"
    template_id: str | None = None


class Generator(Protocol):
    """Deterministic problem source.

    The same (seed, tier, variant, template_id) yields the same Problem. A variant or
    template the generator cannot produce falls back to the bare variant.
    """

    skill_id: str
    tier_difficulties: tuple[float, ...]

    def generate(
        self,
        seed: int,
        tier: int,
        variant: Variant = "bare",
        template_id: str | None = None,
    ) -> Problem: ...
