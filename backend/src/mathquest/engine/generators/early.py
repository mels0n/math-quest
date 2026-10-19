# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false
"""Whole-number addition and subtraction generators."""

import random

import sympy

from mathquest.engine.generators._util import Built, SkillGenerator, math_prompt, text
from mathquest.engine.types import AnswerForm, Prompt

_Int = sympy.Integer

_ADD10_TOTALS = ((2, 5), (6, 8), (9, 10))
_ADD20_TOTALS = ((10, 14), (12, 17), (15, 20))
_SUB10_TOP = ((2, 5), (6, 8), (9, 10))


def _digits(a: int, b: int) -> dict[str, int | str]:
    """The tens and ones of two two-digit addends, for place-value hints."""
    return {
        "a": a,
        "b": b,
        "a_tens": a // 10,
        "a_ones": a % 10,
        "b_tens": b // 10,
        "b_ones": b % 10,
    }


def _add(a: int, b: int) -> Built:
    """``big`` and ``small`` name the addends by size, for count-on hints."""
    return Built(
        prompt=math_prompt(f"{a} + {b} = ?"),
        answer=_Int(a + b),
        wrong=(
            ("subtracted_instead", _Int(abs(a - b))),
            # Counting on from the start number counts it again: 8 + 5 as "8, 9, 10, 11, 12".
            ("counted_start", _Int(a + b - 1)),
        ),
        values={"a": a, "b": b, "big": max(a, b), "small": min(a, b)},
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
        wrong=(
            ("added_instead", _Int(a + b)),
            # Counting back from the start number counts it again: 7 - 3 as "7, 6, 5".
            ("counted_start", _Int(a - b + 1)),
        ),
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
    backwards = a // 10 * 10 + ones_apart
    # With no ones (20 - 8) the column slip and adding give the same number; adding is the
    # likelier cause, so that one is left to the other mistake.
    wrong = [("subtracted_backwards", _Int(backwards))] if backwards != a + b else []
    return Built(
        prompt=math_prompt(f"{a} - {b} = ?"),
        answer=_Int(a - b),
        wrong=(*wrong, ("added_instead", _Int(a + b))),
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
    digit_total = sum(int(d) for d in f"{a}{b}")
    return Built(
        prompt=math_prompt(f"{a} + {b} = ?"),
        answer=_Int(a + b),
        wrong=(
            ("subtracted_instead", _Int(abs(a - b))),
            # Every digit counted as a one: 34 + 25 as 3 + 4 + 2 + 5.
            ("added_digits", _Int(digit_total)),
            # The second number's tens are left out: 34 + 25 as 34 + 5.
            ("left_out_tens", _Int(a + b % 10)),
        ),
        values=_digits(a, b),
    )


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
        values=_digits(a, b),
    )


_PAIR_TOTALS = ((4, 6), (5, 9), (6, 10))
_PAIR_LAYOUTS = (2, 4, 5)
"""How many of the five layouts each tier may use: known first or second, the total first,
then the question in words."""


def _build_pairs_to_10(rng: random.Random, tier: int) -> Built:
    """A number and the one that goes with it to make the total: ``3 + ? = 5``. Totals
    overlap across tiers; the layouts get harder (the unknown second, then first, then the
    total first, then in words)."""
    total = rng.randint(*_PAIR_TOTALS[tier])
    known = rng.randint(1, total - 1)
    answer = total - known
    layout = rng.randrange(_PAIR_LAYOUTS[tier])
    prompt: Prompt
    if layout == 4:
        prompt = (text(f"You have {known}. How many more make {total}?"),)
    else:
        prompt = math_prompt(
            (
                f"{known} + ? = {total}",
                f"? + {known} = {total}",
                f"{total} = {known} + ?",
                f"{total} = ? + {known}",
            )[layout]
        )
    return Built(
        prompt=prompt,
        answer=_Int(answer),
        wrong=(
            ("gave_the_known_number", _Int(known)),
            ("gave_the_total", _Int(total)),
            # Counting up from the known number counts it again: 7 + ? = 10 as "7, 8, 9, 10".
            ("counted_start", _Int(answer + 1)),
        ),
        values={"known": known, "total": total, "answer": answer},
    )


_ADD_MISTAKES = ("subtracted_instead", "counted_start")


def generators() -> list[SkillGenerator]:
    form = AnswerForm.INTEGER
    return [
        SkillGenerator("add_within_10", -2.0, form, _build_add_within_10, _ADD_MISTAKES),
        SkillGenerator(
            "sub_within_10", -1.8, form, _build_sub_within_10, ("added_instead", "counted_start")
        ),
        SkillGenerator("add_within_20", -1.2, form, _build_add_within_20, _ADD_MISTAKES),
        SkillGenerator(
            "sub_within_20",
            -1.0,
            form,
            _build_sub_within_20,
            ("subtracted_backwards", "added_instead"),
        ),
        SkillGenerator(
            "add_2digit_no_regroup",
            -0.5,
            form,
            _build_add_2digit_no_regroup,
            ("subtracted_instead", "added_digits", "left_out_tens"),
        ),
        SkillGenerator(
            "add_2digit_regroup",
            0.0,
            form,
            _build_add_2digit_regroup,
            ("forgot_carry", "added_carry_twice"),
        ),
        SkillGenerator(
            "pairs_to_10",
            -1.5,
            form,
            _build_pairs_to_10,
            ("gave_the_known_number", "gave_the_total", "counted_start"),
        ),
    ]
