# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false
"""Place-value generator: name the digit in a given place."""

import random

import sympy

from mathquest.engine.generators._util import Built, SkillGenerator
from mathquest.engine.types import AnswerForm

_PLACES = ("ones", "tens", "hundreds", "thousands")
_DIGITS_BY_TIER = (2, 3, 4)


def _build_place_value(rng: random.Random, tier: int) -> Built:
    size = _DIGITS_BY_TIER[tier]
    digits = [rng.randint(1, 9)] + [rng.randint(0, 9) for _ in range(size - 1)]
    number = int("".join(str(d) for d in digits))
    place = rng.randint(0, size - 1)
    answer = digits[size - 1 - place]
    wrong: tuple[tuple[str, sympy.Expr], ...] = ()
    if place in (0, 1):
        other = digits[size - 1 - (1 - place)]
        wrong = (("confused_tens_ones", sympy.Integer(other)),)
    question = rf"\text{{Which digit is in the {_PLACES[place]} place of }}"
    return Built(
        prompt_latex=rf"{question} {number}\text{{?}}",
        answer=sympy.Integer(answer),
        wrong=wrong,
    )


def generators() -> list[SkillGenerator]:
    return [
        SkillGenerator(
            "place_value_tens_ones", -1.0, AnswerForm.INTEGER, "numbers", _build_place_value
        )
    ]
