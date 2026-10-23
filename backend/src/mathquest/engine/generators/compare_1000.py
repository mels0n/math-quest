# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false
"""Comparing numbers to 1000 (2.NBT.A.4).

Like Compare to 100, the typed question names the bigger or the smaller of two numbers. The
signs and "the same" are the skill's bank. The two numbers always differ.

Tier 0 pairs have hundreds digits at least two apart. Tier 1 pairs share the hundreds digit.
Tier 2 pairs are the tricky ones: the smaller number has the bigger last two digits (289 and
301), a zero in the tens place (405 and 450), or one of them is 1000.
"""

import random

import sympy

from mathquest.engine.generators._util import Built, SkillGenerator, math, named_wrongs, text
from mathquest.engine.types import AnswerForm

_Int = sympy.Integer

_STEPS = (
    "Look at the hundreds digit of each number first.",
    "The hundreds digits match. Look at the tens digits next, then the ones.",
)
_TRICKY_STEPS = {
    "cross": "Start with the hundreds. Do not let the last two digits fool you.",
    "zero": "Line up the places. Compare the hundreds, then the tens, then the ones.",
    "thousand": "Count the digits in each number first. A number with more digits is bigger.",
}


def _different_hundreds(rng: random.Random) -> tuple[int, int, str]:
    first = rng.randint(1, 9)
    second = rng.choice([h for h in range(1, 10) if abs(h - first) >= 2])
    return first * 100 + rng.randint(0, 99), second * 100 + rng.randint(0, 99), _STEPS[0]


def _same_hundreds(rng: random.Random) -> tuple[int, int, str]:
    hundreds = rng.randint(1, 9) * 100
    a, b = rng.sample(range(100), 2)
    return hundreds + a, hundreds + b, _STEPS[1]


def _tricky(rng: random.Random) -> tuple[int, int, str]:
    kind = rng.choice(("cross", "cross", "zero", "thousand"))
    if kind == "cross":
        while True:
            hundreds = rng.randint(1, 8) * 100
            low_end, high_end = rng.randint(10, 99), rng.randint(0, 98)
            if low_end > high_end and low_end % 10 != high_end % 10:
                return hundreds + low_end, hundreds + 100 + high_end, _TRICKY_STEPS[kind]
    if kind == "zero":
        hundreds = rng.randint(1, 9) * 100
        digit = rng.randint(1, 9)
        return hundreds + digit, hundreds + digit * 10, _TRICKY_STEPS[kind]
    return rng.randint(900, 999), 1000, _TRICKY_STEPS[kind]


_PAIRS = (_different_hundreds, _same_hundreds, _tricky)


def _build_compare_1000(rng: random.Random, tier: int) -> Built:
    a, b, step = _PAIRS[tier](rng)
    if rng.choice((True, False)):
        a, b = b, a
    greater = rng.choice((True, False))
    big, small = max(a, b), min(a, b)
    answer = big if greater else small
    other = small if greater else big
    word = "bigger" if greater else "smaller"
    if small % 10 > big % 10:
        key = "compared_ones_only"
    elif small // 10 % 10 > big // 10 % 10:
        key = "compared_tens_only"
    else:
        key = "confused_bigger_smaller"
    return Built(
        prompt=(
            text(f"Which number is {word}, "),
            math(str(a)),
            text(" or "),
            math(str(b)),
            text("?"),
        ),
        answer=_Int(answer),
        wrong=named_wrongs([(key, other), ("gave_the_difference", big - small)]),
        values={
            "a": a,
            "b": b,
            "bigger": "yes" if greater else "no",
            "which": word,
            "step": step,
            "answer": answer,
            "worked": f"Of {big} and {small}, {big} is more. So the {word} number is {answer}.",
        },
    )


def generators() -> list[SkillGenerator]:
    return [
        SkillGenerator(
            "compare_numbers_1000",
            -0.2,
            AnswerForm.INTEGER,
            _build_compare_1000,
            (
                "confused_bigger_smaller",
                "compared_ones_only",
                "compared_tens_only",
                "gave_the_difference",
            ),
            first_try_counts=True,
        )
    ]
