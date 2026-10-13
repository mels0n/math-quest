# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false
"""Fraction generators: equivalent fractions and unlike-denominator addition."""

import math
import random

import sympy

from mathquest.engine.generators._util import Built, SkillGenerator
from mathquest.engine.types import AnswerForm

_MULTIPLIERS = ((2, 3), (4, 6), (7, 10))
# (p, q) coprime and both above 1; denominators g*p and g*q share the factor g.
_SHARED_FACTOR_PAIRS = ((2, 3), (3, 2), (2, 5), (5, 2), (3, 4), (4, 3))
_COPRIME_DENOMINATORS = ((2, 3), (2, 5), (3, 4), (3, 5), (4, 5), (2, 7), (3, 7))


def _build_equivalent(rng: random.Random, tier: int) -> Built:
    lo, hi = _MULTIPLIERS[tier]
    k = rng.randint(lo, hi)
    b = rng.randint(2, 6)
    a = rng.randint(1, b - 1)
    d = b * k
    return Built(
        prompt_latex=rf"\frac{{{a}}}{{{b}}} = \frac{{?}}{{{d}}}",
        answer=sympy.Integer(a * k),
        wrong=(
            ("added_instead_of_multiplied", sympy.Integer(a + d - b)),
            ("copied_numerator", sympy.Integer(a)),
        ),
    )


def _denominators(rng: random.Random, tier: int) -> tuple[int, int]:
    if tier == 0:
        b = rng.randint(2, 4)
        return b, b * rng.randint(2, 3)
    if tier == 1:
        b, c = rng.choice(_COPRIME_DENOMINATORS)
        return (b, c) if rng.random() < 0.5 else (c, b)
    g = rng.randint(2, 3)
    p, q = rng.choice(_SHARED_FACTOR_PAIRS)
    return g * p, g * q


def _build_add_unlike(rng: random.Random, tier: int) -> Built:
    while True:
        b, d = _denominators(rng, tier)
        a, c = rng.randint(1, b - 1), rng.randint(1, d - 1)
        total = sympy.Rational(a, b) + sympy.Rational(c, d)
        if not total.is_integer:
            break
    common = math.lcm(b, d)
    return Built(
        prompt_latex=rf"\frac{{{a}}}{{{b}}} + \frac{{{c}}}{{{d}}} = ?",
        answer=total,
        wrong=(
            ("added_denominators", sympy.Rational(a + c, b + d)),
            # Common denominator found, numerators added without rescaling.
            ("added_numerators_only", sympy.Rational(a + c, common)),
        ),
    )


def generators() -> list[SkillGenerator]:
    return [
        SkillGenerator(
            "equivalent_fractions", 0.0, AnswerForm.INTEGER, "fractions", _build_equivalent
        ),
        SkillGenerator(
            "add_fractions_unlike", 0.8, AnswerForm.LOWEST_TERMS, "fractions", _build_add_unlike
        ),
    ]
