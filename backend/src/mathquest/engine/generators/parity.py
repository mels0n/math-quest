# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false
"""Even and odd numbers (2.OA.C.3).

Learners type the number the question asks for: the even or odd one of two or three numbers,
the next even or odd number, or how many are left over when things are put in pairs. Naming
a number even or odd is a button question, served from the skill's bank.

Tier 0 uses numbers to 20, tier 1 to 100 and tier 2 to 1000. In tier 2 the numbers of a
pair often share every digit but the last, so only the ones digit tells them apart.
"""

import random
from collections.abc import Callable

import sympy

from mathquest.engine.generators._util import (
    NAMES,
    Built,
    SkillGenerator,
    math,
    named_wrongs,
    noun,
    text,
)
from mathquest.engine.types import AnswerForm, PromptPart

_Int = sympy.Integer

_RANGES = ((1, 20), (21, 100), (101, 1000))
_THINGS = ("shells", "stones", "cubes", "socks", "shoes", "cups", "hats", "beads", "stars")
_ENDINGS = {
    "even": "Even numbers end in zero, two, four, six or eight.",
    "odd": "Odd numbers end in one, three, five, seven or nine.",
}
_NUDGE = "Even numbers pair up with none left over. Odd numbers always have one left over."


def _of_kind(rng: random.Random, lo: int, hi: int, kind: str) -> int:
    """A number in ``lo..hi`` of the kind ``even`` or ``odd``."""
    parity = 0 if kind == "even" else 1
    while True:
        n = rng.randint(lo, hi)
        if n % 2 == parity:
            return n


def _other(kind: str) -> str:
    return "odd" if kind == "even" else "even"


def _pick(rng: random.Random, tier: int, count: int) -> tuple[str, int, list[int]]:
    """The kind asked for, the one number of that kind, and the ``count`` numbers shown in
    a random order (the rest are of the other kind)."""
    lo, hi = _RANGES[tier]
    kind = rng.choice(("even", "odd"))
    right = _of_kind(rng, lo, hi, kind)
    shown = [right]
    while len(shown) < count:
        if tier == 2 and len(shown) == 1 and rng.choice((True, False)):
            # Same digits but the last: only the ones digit tells them apart.
            near = right + rng.choice((-1, 1))
            candidate = near if lo <= near <= hi else _of_kind(rng, lo, hi, _other(kind))
        else:
            candidate = _of_kind(rng, lo, hi, _other(kind))
        if candidate not in shown:
            shown.append(candidate)
    rng.shuffle(shown)
    return kind, right, shown


def _which(rng: random.Random, tier: int, count: int) -> Built:
    kind, right, shown = _pick(rng, tier, count)
    prompt: list[PromptPart] = [
        text(f"Which number is {kind}, " if count == 2 else f"Which is {kind}, ")
    ]
    for i, n in enumerate(shown):
        if i:
            prompt.append(text(" or " if i == count - 1 else ", "))
        prompt.append(math(str(n)))
    prompt.append(text("?"))
    others = [n for n in shown if n != right]
    return Built(
        prompt=tuple(prompt),
        answer=_Int(right),
        wrong=named_wrongs([("picked_the_other_kind", n) for n in others]),
        values={
            "kind": kind,
            "n": right,
            "answer": right,
            "step": f"Look at the ones digit of each number. {_ENDINGS[kind]}",
            "worked": f"Look at {right}. It ends in {right % 10}. So {right} is {kind}.",
        },
    )


def _which_of_two(rng: random.Random, tier: int) -> Built:
    return _which(rng, tier, 2)


def _which_of_three(rng: random.Random, tier: int) -> Built:
    return _which(rng, tier, 3)


def _next_number(rng: random.Random, tier: int) -> Built:
    lo, hi = _RANGES[tier]
    n = rng.randint(lo, hi - 2)
    kind = rng.choice(("even", "odd"))
    answer = n + 1 if (n + 1) % 2 == (0 if kind == "even" else 1) else n + 2
    return Built(
        prompt=(text(f"What is the next {kind} number after "), math(str(n)), text("?")),
        answer=_Int(answer),
        wrong=named_wrongs(
            [
                ("gave_the_other_kind", answer + 1),
                ("skipped_one", answer + 2),
                ("gave_the_other_kind", answer - 1),
            ]
        ),
        values={
            "kind": kind,
            "n": n,
            "answer": answer,
            "step": f"Count on from {n}. Check the ones digit of each number you say.",
            "worked": f"After {n}, the next {kind} number is {answer}.",
        },
    )


def _pairs(rng: random.Random, tier: int) -> Built:
    lo, hi = _RANGES[tier]
    n = rng.randint(max(lo, 2), hi)
    who = rng.choice(NAMES)
    things = rng.choice(_THINGS)
    left = n % 2
    return Built(
        prompt=(
            text(
                f"{who} has {n} {noun(n, things)}. {who} puts them in pairs. "
                "How many are left over?"
            ),
        ),
        answer=_Int(left),
        wrong=named_wrongs([("counted_the_pairs", n // 2), ("mixed_up_left_over", 1 - left)]),
        values={
            "n": n,
            "answer": left,
            "step": f"Make pairs of {things}. See if one has no partner.",
            "worked": f"Make pairs of the {n} {things}. The number left over is {left}.",
        },
    )


_FORMS: tuple[tuple[Callable[[random.Random, int], Built], ...], ...] = (
    (_which_of_two, _which_of_two, _which_of_three, _next_number, _pairs),
    (_which_of_two, _which_of_three, _next_number, _next_number, _pairs),
    (_which_of_two, _which_of_two, _which_of_three, _next_number, _next_number),
)


def _build_even_odd(rng: random.Random, tier: int) -> Built:
    return rng.choice(_FORMS[tier])(rng, tier)


def generators() -> list[SkillGenerator]:
    return [
        SkillGenerator(
            "even_odd",
            -0.7,
            AnswerForm.INTEGER,
            _build_even_odd,
            (
                "picked_the_other_kind",
                "gave_the_other_kind",
                "skipped_one",
                "counted_the_pairs",
                "mixed_up_left_over",
            ),
            first_try_counts=True,
        )
    ]
