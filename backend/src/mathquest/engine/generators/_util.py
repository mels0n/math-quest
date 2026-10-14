# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false
"""Shared scaffolding for skill generators."""

import random
from collections.abc import Callable, Iterable
from dataclasses import dataclass

import sympy

from mathquest.engine.types import AnswerForm, Misconception, Problem


@dataclass(frozen=True)
class Built:
    """What a skill's builder returns for one (rng, tier)."""

    prompt_latex: str
    answer: sympy.Expr
    wrong: tuple[tuple[str, sympy.Expr], ...] = ()


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
        keypad: str,
        build: Builder,
    ) -> None:
        self.skill_id = skill_id
        self.tier_difficulties = tier_difficulties(base_difficulty)
        self._form = form
        self._keypad = keypad
        self._build = build

    def generate(self, seed: int, tier: int) -> Problem:
        if not 0 <= tier < len(self.tier_difficulties):
            raise ValueError(f"tier {tier} out of range for {self.skill_id}")
        rng = random.Random(seed)
        built = self._build(rng, tier)
        return Problem(
            skill_id=self.skill_id,
            tier=tier,
            seed=seed,
            prompt_latex=built.prompt_latex,
            answer=built.answer,
            form=self._form,
            misconceptions=distinct_misconceptions(built.answer, built.wrong),
            difficulty=self.tier_difficulties[tier],
            keypad=self._keypad,
        )
