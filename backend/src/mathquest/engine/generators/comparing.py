# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false
"""Comparing generators.

The typed question of the comparing skills: name the bigger or smaller number, or the
count of the group with more or fewer. Learners type the number. Questions that need
buttons (the signs, and groups or numbers that are the same) are the skills' bank items,
served beside these. Groups here always differ in size, since the typed answer for
"the group with more" has no meaning for two equal groups; "same" is the bank's.
"""

import random

import sympy

from mathquest.engine.generators._util import Built, SkillGenerator, math, text
from mathquest.engine.types import AnswerForm

_Int = sympy.Integer

# Plural nouns a kindergartner can count, two groups at a time.
_GROUPS = (
    "apples",
    "pears",
    "cats",
    "dogs",
    "birds",
    "fish",
    "ducks",
    "frogs",
    "balls",
    "kites",
    "cubes",
    "stars",
    "shells",
    "rocks",
    "cups",
    "hats",
)
_ONES = list(range(10))
_GROUP_MAX = ((1, 5), (1, 10), (6, 10))


def _noun(count: int, plural: str) -> str:
    """The plural noun, or its singular for one (every noun here adds only an s)."""
    return plural[:-1] if count == 1 and plural.endswith("s") else plural


def _two(rng: random.Random, lo: int, hi: int, apart: tuple[int, int]) -> tuple[int, int]:
    """Two different numbers in ``lo..hi`` whose distance is within ``apart``."""
    first = rng.randint(lo, hi)
    gaps = [d for d in range(apart[0], apart[1] + 1) if lo <= first - d or first + d <= hi]
    gap = rng.choice(gaps)
    options = [n for n in (first - gap, first + gap) if lo <= n <= hi]
    return first, rng.choice(options)


def _build_compare_groups(rng: random.Random, tier: int) -> Built:
    lo, hi = _GROUP_MAX[tier]
    a, b = _two(rng, lo, hi, (1, 1) if tier == 2 else (1, hi - lo))
    first, second = rng.sample(_GROUPS, 2)
    more = rng.choice((True, False))
    big, small = max(a, b), min(a, b)
    answer = big if more else small
    other = small if more else big
    return Built(
        prompt=(
            text(
                f"There {'is' if a == 1 else 'are'} {a} {_noun(a, first)} "
                f"and {b} {_noun(b, second)}. "
                f"How many are in the group with {'more' if more else 'fewer'}?"
            ),
        ),
        answer=_Int(answer),
        wrong=(
            ("confused_more_fewer", _Int(other)),
            ("counted_both_groups", _Int(a + b)),
        ),
        values={"a": a, "b": b, "more": "more" if more else "fewer", "answer": answer},
    )


def _compare_numbers(rng: random.Random, pair: tuple[int, int], tricky: bool) -> Built:
    """Which of two numbers is bigger, or smaller. ``tricky`` pairs have the smaller
    number's ones digit higher, so comparing ones alone gives the wrong number."""
    a, b = pair
    greater = rng.choice((True, False))
    big, small = max(a, b), min(a, b)
    answer = big if greater else small
    other = small if greater else big
    word = "bigger" if greater else "smaller"
    key = "compared_ones_only" if tricky else "confused_bigger_smaller"
    return Built(
        prompt=(
            text(f"Which number is {word}, "),
            math(str(a)),
            text(" or "),
            math(str(b)),
            text("?"),
        ),
        answer=_Int(answer),
        wrong=((key, _Int(other)), ("gave_the_difference", _Int(big - small))),
        values={
            "a": a,
            "b": b,
            "bigger": "yes" if greater else "no",
            "which": word,
            "answer": answer,
        },
    )


def _build_compare_numbers_20(rng: random.Random, tier: int) -> Built:
    if tier == 0:
        pair = _two(rng, 1, 10, (1, 9))
    elif tier == 1:
        pair = _two(rng, 11, 20, (1, 9))
    else:
        pair = _two(rng, 1, 20, (1, 2))
    return _compare_numbers(rng, pair, tricky=False)


def _build_compare_numbers_100(rng: random.Random, tier: int) -> Built:
    if tier == 0:
        tens_a = rng.randint(1, 9)
        tens_b = rng.choice([t for t in range(1, 10) if abs(t - tens_a) >= 2])
        pair = (tens_a * 10 + rng.choice(_ONES), tens_b * 10 + rng.choice(_ONES))
        return _compare_numbers(rng, pair, tricky=False)
    if tier == 1:
        tens = rng.randint(1, 9)
        ones = rng.sample(_ONES, 2)
        return _compare_numbers(rng, (tens * 10 + ones[0], tens * 10 + ones[1]), tricky=False)
    # The smaller number has the higher ones digit: 29 and 31, or 47 and 74.
    while True:
        a = rng.randint(1, 9) * 10 + rng.choice(_ONES)
        b = rng.randint(1, 9) * 10 + rng.choice(_ONES)
        if a // 10 < b // 10 and a % 10 > b % 10:
            break
    pair = (a, b) if rng.choice((True, False)) else (b, a)
    return _compare_numbers(rng, pair, tricky=True)


def generators() -> list[SkillGenerator]:
    form = AnswerForm.INTEGER
    return [
        SkillGenerator(
            "compare_groups",
            -2.5,
            form,
            _build_compare_groups,
            ("confused_more_fewer", "counted_both_groups"),
        ),
        SkillGenerator(
            "compare_numbers_20",
            -2.1,
            form,
            _build_compare_numbers_20,
            ("confused_bigger_smaller", "gave_the_difference"),
        ),
        SkillGenerator(
            "compare_numbers_100",
            -1.1,
            form,
            _build_compare_numbers_100,
            ("confused_bigger_smaller", "compared_ones_only", "gave_the_difference"),
        ),
    ]
