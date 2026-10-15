# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false
"""Shared scaffolding for skill generators."""

import random
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass, field

import sympy

from mathquest.engine.types import (
    AnswerForm,
    MathPart,
    Misconception,
    Problem,
    Prompt,
    TextPart,
    Variant,
)


@dataclass(frozen=True)
class Built:
    """What a skill's builder returns for one (rng, tier).

    ``values`` names the numbers the builder chose, for hint and word-problem templates.
    """

    prompt: Prompt
    answer: sympy.Expr
    wrong: tuple[tuple[str, sympy.Expr], ...] = ()
    values: Mapping[str, int | str] = field(default_factory=dict[str, int | str], hash=False)


def text(words: str) -> TextPart:
    if not words.strip():
        raise ValueError("a text part needs words")
    return TextPart(words)


def math(latex: str) -> MathPart:
    if r"\text" in latex:
        raise ValueError("words belong in a text part, not in math")
    return MathPart(latex)


def math_prompt(latex: str) -> Prompt:
    """A prompt that is one math expression."""
    return (math(latex),)


Builder = Callable[[random.Random, int], Built]


def tier_difficulties(base: float) -> tuple[float, float, float]:
    return (base - 1.0, base, base + 1.0)


def distinct_misconceptions(
    answer: sympy.Expr, wrong: Iterable[tuple[str, sympy.Expr]]
) -> tuple[Misconception, ...]:
    """Drop wrong answers equal to the true answer or to an earlier wrong answer."""
    seen: list[sympy.Expr] = [answer]
    kept: list[Misconception] = []
    for key, value in wrong:
        if value in seen:
            continue
        seen.append(value)
        kept.append(Misconception(key=key, answer=value))
    return tuple(kept)


class SkillGenerator:
    """A deterministic generator for one skill, driven by a per-tier builder."""

    def __init__(
        self,
        skill_id: str,
        base_difficulty: float,
        form: AnswerForm,
        build: Builder,
    ) -> None:
        self.skill_id = skill_id
        self.tier_difficulties = tier_difficulties(base_difficulty)
        self._form = form
        self._build = build

    def generate(
        self,
        seed: int,
        tier: int,
        variant: Variant = "bare",
        template_id: str | None = None,
    ) -> Problem:
        """Build the problem for (seed, tier).

        Only the bare variant exists so far; any other variant or template falls back
        to it. The answer never depends on the variant.
        """
        del variant, template_id
        if not 0 <= tier < len(self.tier_difficulties):
            raise ValueError(f"tier {tier} out of range for {self.skill_id}")
        rng = random.Random(seed)
        built = self._build(rng, tier)
        return Problem(
            skill_id=self.skill_id,
            tier=tier,
            seed=seed,
            prompt=built.prompt,
            answer=built.answer,
            form=self._form,
            misconceptions=distinct_misconceptions(built.answer, built.wrong),
            difficulty=self.tier_difficulties[tier],
            values=dict(built.values),
        )
