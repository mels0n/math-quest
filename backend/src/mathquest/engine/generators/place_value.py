# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false
"""Place-value generator: name the digit in a given place."""

import random

import sympy

from mathquest.engine.generators._util import Built, SkillGenerator, math, text
from mathquest.engine.types import AnswerForm

_PLACES = ("ones", "tens", "hundreds", "thousands")
_DIGITS_BY_TIER = (2, 3, 4)
# Inclusive range of place indexes (0 = ones) asked at each tier; higher tiers ask higher places.
_ASKED_PLACES = ((0, 1), (1, 2), (2, 3))


def _build_place_value(rng: random.Random, tier: int) -> Built:
    size = _DIGITS_BY_TIER[tier]
    digits = [rng.randint(1, 9)] + [rng.randint(0, 9) for _ in range(size - 1)]
    number = int("".join(str(d) for d in digits))
    place = rng.randint(*_ASKED_PLACES[tier])
    answer = digits[size - 1 - place]
    wrong: tuple[tuple[str, sympy.Expr], ...] = ()
    if place in (0, 1):
        other = digits[size - 1 - (1 - place)]
        wrong = (("confused_tens_ones", sympy.Integer(other)),)
    else:
        below = digits[size - place]
        wrong = (("confused_adjacent_place", sympy.Integer(below)),)
    return Built(
        prompt=(
            text(f"Which digit is in the {_PLACES[place]} place of "),
            math(str(number)),
            text("?"),
        ),
        answer=sympy.Integer(answer),
        wrong=wrong,
        values={"number": number, "place": _PLACES[place], "digit": answer},
    )


_TEENS = ((11, 13), (14, 16), (17, 19))


def _unit(count: int, name: str) -> str:
    """``name`` agreeing with ``count``: one ten, two tens."""
    return name if count == 1 else f"{name}s"


def _build_teen_numbers(rng: random.Random, tier: int) -> Built:
    """A teen number is a ten and some ones: name the number, or the ones."""
    teen = rng.randint(*_TEENS[tier])
    ones = teen - 10
    if rng.choice((True, False)):
        return Built(
            prompt=(
                text("A ten and "),
                math(str(ones)),
                text(f" {_unit(ones, 'one')} make what number?"),
            ),
            answer=sympy.Integer(teen),
            wrong=(
                ("reversed_digits", sympy.Integer(ones * 10 + 1)),
                ("wrote_ten_then_ones", sympy.Integer(100 + ones)),
                ("said_the_ones_only", sympy.Integer(ones)),
            ),
            values={"teen": teen, "ones": ones, "asks": "number"},
        )
    return Built(
        prompt=(math(str(teen)), text(" is a ten and how many more ones?")),
        answer=sympy.Integer(ones),
        wrong=(
            ("said_the_tens_digit", sympy.Integer(1)),
            ("copied_the_number", sympy.Integer(teen)),
        ),
        values={"teen": teen, "ones": ones, "asks": "ones"},
    )


def _build_place_value_hundreds(rng: random.Random, tier: int) -> Built:
    """Bundles of ten, whole hundreds, then a number named by its hundreds, tens and ones."""
    if tier == 0:
        tens = rng.randint(2, 10)
        number = tens * 10
        return Built(
            prompt=(text("How many bundles of ten make "), math(str(number)), text("?")),
            answer=sympy.Integer(tens),
            wrong=(
                ("gave_the_number", sympy.Integer(number)),
                ("off_by_one", sympy.Integer(tens - 1)),
            ),
            values={"number": number, "tens": tens},
        )
    if tier == 1:
        hundreds = rng.randint(2, 9)
        number = hundreds * 100
        if rng.choice((True, False)):
            return Built(
                prompt=(text("How many hundreds are in "), math(str(number)), text("?")),
                answer=sympy.Integer(hundreds),
                wrong=(
                    ("gave_the_number", sympy.Integer(number)),
                    ("confused_hundreds_tens", sympy.Integer(hundreds * 10)),
                ),
                values={"number": number, "hundreds": hundreds, "asks": "hundreds"},
            )
        return Built(
            prompt=(text("How many bundles of ten make "), math(str(number)), text("?")),
            answer=sympy.Integer(hundreds * 10),
            wrong=(
                ("gave_the_number", sympy.Integer(number)),
                ("confused_hundreds_tens", sympy.Integer(hundreds)),
            ),
            values={"number": number, "hundreds": hundreds, "asks": "tens"},
        )
    hundreds = rng.randint(1, 9)
    tens = rng.choice((0, 0, *range(1, 10)))
    ones = rng.randint(0, 9) if tens else rng.randint(1, 9)
    number = hundreds * 100 + tens * 10 + ones
    return Built(
        prompt=(
            text("What number is "),
            math(str(hundreds)),
            text(f" {_unit(hundreds, 'hundred')}, "),
            math(str(tens)),
            text(f" {_unit(tens, 'ten')} and "),
            math(str(ones)),
            text(f" {_unit(ones, 'one')}?"),
        ),
        answer=sympy.Integer(number),
        wrong=(
            ("added_the_digits", sympy.Integer(hundreds + tens + ones)),
            ("swapped_tens_and_ones", sympy.Integer(hundreds * 100 + ones * 10 + tens)),
            ("left_out_the_zero", sympy.Integer(int(str(number).replace("0", "")))),
        ),
        values={"number": number, "hundreds": hundreds, "tens": tens, "ones": ones},
    )


def generators() -> list[SkillGenerator]:
    form = AnswerForm.INTEGER
    return [
        SkillGenerator(
            "place_value_tens_ones",
            -1.0,
            form,
            _build_place_value,
            ("confused_tens_ones", "confused_adjacent_place"),
        ),
        SkillGenerator(
            "teen_numbers",
            -1.7,
            form,
            _build_teen_numbers,
            (
                "reversed_digits",
                "wrote_ten_then_ones",
                "said_the_ones_only",
                "said_the_tens_digit",
                "copied_the_number",
            ),
        ),
        SkillGenerator(
            "place_value_hundreds",
            -0.6,
            form,
            _build_place_value_hundreds,
            (
                "gave_the_number",
                "off_by_one",
                "confused_hundreds_tens",
                "added_the_digits",
                "swapped_tens_and_ones",
                "left_out_the_zero",
            ),
        ),
    ]
