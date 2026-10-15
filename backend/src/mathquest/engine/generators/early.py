# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false
"""Whole-number addition and subtraction generators."""

import random

import sympy

from mathquest.engine.generators._util import Built, SkillGenerator, math_prompt
from mathquest.engine.types import AnswerForm

_Int = sympy.Integer

_ADD10_TOTALS = ((2, 5), (6, 8), (9, 10))
_ADD20_TOTALS = ((10, 14), (12, 17), (15, 20))
_SUB10_TOP = ((2, 5), (6, 8), (9, 10))


def _sum(a: int, b: int) -> Built:
    return Built(prompt=math_prompt(f"{a} + {b} = ?"), answer=_Int(a + b), values={"a": a, "b": b})


def _add(a: int, b: int) -> Built:
    return Built(
        prompt=math_prompt(f"{a} + {b} = ?"),
        answer=_Int(a + b),
        wrong=(("subtracted_instead", _Int(abs(a - b))),),
        values={"a": a, "b": b},
    )


def _build_add_within_10(rng: random.Random, tier: int) -> Built:
    lo, hi = _ADD10_TOTALS[tier]
    total = rng.randint(lo, hi)
    a = rng.randint(1, total - 1)
    return _add(a, total - a)


def _build_add_within_20(rng: random.Random, tier: int) -> Built:
    lo, hi = _ADD20_TOTALS[tier]
    total = rng.randint(lo, hi)
    a = rng.randint(2, total - 2)
    return _add(a, total - a)


def _build_sub_within_10(rng: random.Random, tier: int) -> Built:
    lo, hi = _SUB10_TOP[tier]
    a = rng.randint(lo, hi)
    b = rng.randint(1, a - 1)
    return Built(
        prompt=math_prompt(f"{a} - {b} = ?"),
        answer=_Int(a - b),
        wrong=(("added_instead", _Int(a + b)),),
        values={"a": a, "b": b},
    )


def _build_sub_within_20(rng: random.Random, tier: int) -> Built:
    if tier == 0:
        a = rng.randint(11, 19)
        b = rng.randint(1, a % 10)
    elif tier == 1:
        a = rng.randint(11, 16)
        b = rng.randint(a % 10 + 1, 9)
    else:
        a = rng.choice((15, 16, 17, 18, 20))
        b = rng.choice([n for n in (7, 8, 9) if n > a % 10])
    # Column-wise "smaller minus larger" error: ones digits subtracted the wrong way round.
    ones_apart = abs(a % 10 - b)
    return Built(
        prompt=math_prompt(f"{a} - {b} = ?"),
        answer=_Int(a - b),
        wrong=(
            ("subtracted_backwards", _Int(a // 10 * 10 + ones_apart)),
            ("added_instead", _Int(a + b)),
        ),
        values={"a": a, "b": b},
    )


def _build_add_2digit_no_regroup(rng: random.Random, tier: int) -> Built:
    if tier == 0:
        a_tens = rng.randint(1, 8)
        b_tens = rng.randint(1, 9 - a_tens)
        a, b = a_tens * 10 + rng.randint(1, 9), b_tens * 10
    else:
        top = 4 if tier == 1 else 8
        a_tens = rng.randint(1, top)
        b_tens = rng.randint(1, min(top, 9 - a_tens))
        a_ones = rng.randint(0, 9)
        b_ones = rng.randint(0, 9 - a_ones)
        a, b = a_tens * 10 + a_ones, b_tens * 10 + b_ones
    return _sum(a, b)


def _build_add_2digit_regroup(rng: random.Random, tier: int) -> Built:
    a_ones = rng.randint(1, 9)
    b_ones = rng.randint(10 - a_ones, 9)
    if tier == 0:
        a_tens, b_tens = rng.randint(1, 3), rng.randint(1, 3)
    elif tier == 1:
        a_tens = rng.randint(1, 7)
        b_tens = rng.randint(max(1, 5 - a_tens), 8 - a_tens)
    else:
        a_tens = rng.randint(2, 9)
        b_tens = rng.randint(max(1, 9 - a_tens), 9)
    a, b = a_tens * 10 + a_ones, b_tens * 10 + b_ones
    total = a + b
    return Built(
        prompt=math_prompt(f"{a} + {b} = ?"),
        answer=_Int(total),
        wrong=(
            ("forgot_carry", _Int(total - 10)),
            ("added_carry_twice", _Int(total + 10)),
        ),
        values={"a": a, "b": b},
    )


def generators() -> list[SkillGenerator]:
    form = AnswerForm.INTEGER
    return [
        SkillGenerator("add_within_10", -2.0, form, _build_add_within_10, ("subtracted_instead",)),
        SkillGenerator("sub_within_10", -1.8, form, _build_sub_within_10, ("added_instead",)),
        SkillGenerator("add_within_20", -1.2, form, _build_add_within_20, ("subtracted_instead",)),
        SkillGenerator(
            "sub_within_20",
            -1.0,
            form,
            _build_sub_within_20,
            ("subtracted_backwards", "added_instead"),
        ),
        SkillGenerator("add_2digit_no_regroup", -0.5, form, _build_add_2digit_no_regroup),
        SkillGenerator(
            "add_2digit_regroup",
            0.0,
            form,
            _build_add_2digit_regroup,
            ("forgot_carry", "added_carry_twice"),
        ),
    ]
