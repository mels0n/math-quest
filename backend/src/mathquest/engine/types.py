"""Core engine types: problems, generators and answer forms."""

from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol

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
class Problem:
    """A generated problem. `keypad` is one of "numbers", "fractions", "algebra"."""

    skill_id: str
    tier: int
    seed: int
    prompt_latex: str
    answer: sympy.Expr
    form: AnswerForm
    misconceptions: tuple[Misconception, ...]
    difficulty: float
    keypad: str


class Generator(Protocol):
    """Deterministic problem source: the same (seed, tier) yields the same Problem."""

    skill_id: str
    tier_difficulties: tuple[float, ...]

    def generate(self, seed: int, tier: int) -> Problem: ...
