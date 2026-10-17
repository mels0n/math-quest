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
    """A deterministic generator, driven by a per-tier builder.

    ``misconception_keys`` declares every misconception key the builder can produce, so
    content (misconception feedback) can be checked against it without sampling.
    ``first_try_counts`` marks a question with only two likely answers: a wrong try before
    the solve scores as a miss (``engine.mastery.scores_as_correct``).
    """

    def __init__(
        self,
        generator_id: str,
        base_difficulty: float,
        form: AnswerForm,
        build: Builder,
        misconception_keys: tuple[str, ...] = (),
        *,
        first_try_counts: bool = False,
    ) -> None:
        self.generator_id = generator_id
        self.first_try_counts = first_try_counts
        self.tier_difficulties = tier_difficulties(base_difficulty)
        self.misconception_keys = misconception_keys
        self._form = form
        self._build = build

    def generate(
        self,
        seed: int,
        tier: int,
        variant: Variant = "bare",
        template_id: str | None = None,
    ) -> Problem:
        """Build the bare problem for (seed, tier).

        A generator only knows the bare variant; word and bank variants are built on
        top of it from content (``mathquest.engine.catalog``), so any other variant or
        template falls back to bare here. ``skill_id`` is the generator id until a
        catalog source names the skill.
        """
        del variant, template_id
        if not 0 <= tier < len(self.tier_difficulties):
            raise ValueError(f"tier {tier} out of range for {self.generator_id}")
        rng = random.Random(seed)
        built = self._build(rng, tier)
        return Problem(
            skill_id=self.generator_id,
            tier=tier,
            seed=seed,
            prompt=built.prompt,
            answer=built.answer,
            form=self._form,
            misconceptions=distinct_misconceptions(built.answer, built.wrong),
            difficulty=self.tier_difficulties[tier],
            values=dict(built.values),
        )
