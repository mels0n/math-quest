# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false
"""Story problems to 100 (2.OA.A.1): the shapes of Story Problems to 20 with two-digit numbers.

A story that adds tells ``a`` and ``b`` (``a`` is at least ``b``, both at least 10, and
``a + b`` is at most 100). A story that takes away tells ``m`` and ``n`` (``n`` is at least
10 and at least 5 less than ``m``, and ``m`` is at most 100). Every number told is two-digit, so
a noun after one is always plural. Word templates retell one of the two pairs with their own
answer, as in Story Problems to 20 (ADR-0025). ``told1`` and ``told2`` are the pair the bare
story tells, for hints.

The tiers: stories that add to or take from; stories that put together, take apart or
compare; then a mix of those that take apart or compare with the stories where the change or
the start is the unknown.
"""

import random

import sympy

from mathquest.engine.generators._util import NAMES, Built, SkillGenerator, named_wrongs, text
from mathquest.engine.types import AnswerForm

_Int = sympy.Integer

# Plural nouns that add only an s, and that two-digit counts of make sense.
_THINGS = (
    "marbles",
    "stickers",
    "stamps",
    "beads",
    "coins",
    "cards",
    "pencils",
    "crayons",
    "buttons",
    "shells",
    "stones",
    "tickets",
    "balloons",
    "magnets",
)
_HIDDEN = ("change_add", "change_take", "start_add", "start_take")
_SHAPES_BY_TIER = (
    ("add_to", "take_from"),
    ("put_together", "take_apart", "compare_more", "compare_fewer"),
    ("take_apart", "compare_more", "compare_fewer", *_HIDDEN),
)
# The shapes whose answer is the sum of the two numbers told; the rest take one from the other.
_ADDS = frozenset({"add_to", "put_together", "start_take"})


def _story(shape: str, n: str, f: str, things: str, a: int, b: int) -> tuple[str, int, str]:
    """The story text, its answer and a worked line, for the two numbers ``a`` and ``b``."""
    if shape == "add_to":
        return (
            f"{n} collects {a} {things}. Then {n} finds {b} more. "
            f"How many {things} does {n} have now?",
            a + b,
            f"Put {a} and {b} together. That makes {a + b}.",
        )
    if shape == "take_from":
        return (
            f"{n} has {a} {things}. {n} loses {b} of them. How many {things} does {n} have left?",
            a - b,
            f"Start with {a}. Take away {b}. That leaves {a - b}.",
        )
    if shape == "put_together":
        return (
            f"{n} has {a} red {things} and {b} blue {things}. "
            f"How many {things} does {n} have in all?",
            a + b,
            f"Put {a} and {b} together. That makes {a + b}.",
        )
    if shape == "take_apart":
        return (
            f"{n} has {a} {things}. Of these, {b} are red. The rest are blue. How many are blue?",
            a - b,
            f"Start with {a}. Take away {b}, the red ones. That leaves {a - b}.",
        )
    if shape == "compare_more":
        return (
            f"{n} has {a} {things} and {f} has {b}. How many more does {n} have?",
            a - b,
            f"Match them up. The gap between {a} and {b} is {a - b}.",
        )
    if shape == "compare_fewer":
        return (
            f"{n} has {a} {things} and {f} has {b}. How many fewer does {f} have?",
            a - b,
            f"Match them up. The gap between {b} and {a} is {a - b}.",
        )
    if shape == "change_add":
        return (
            f"{n} has {b} {things}. Then {n} gets some more. Now {n} has {a}. "
            f"How many did {n} get?",
            a - b,
            f"Count up from {b} to {a}. The gap is {a - b}.",
        )
    if shape == "change_take":
        return (
            f"{n} has {a} {things}. {n} gives some away. Now {n} has {b}. "
            f"How many did {n} give away?",
            a - b,
            f"Count back from {a} to {b}. The gap is {a - b}.",
        )
    if shape == "start_add":
        return (
            f"{n} has some {things}. {f} gives {n} {b} more. Now {n} has {a}. "
            f"How many {things} did {n} have at first?",
            a - b,
            f"Take {b} from {a}. That leaves {a - b}.",
        )
    return (
        f"{n} has some {things}. {n} gives {b} to {f}. Now {n} has {a}. "
        f"How many {things} did {n} have at first?",
        a + b,
        f"Put back the {b} that went. Then {a} and {b} make {a + b}.",
    )


def _build_story(rng: random.Random, tier: int) -> Built:
    total = rng.randint(30, 100)
    b = rng.randint(10, total // 2)
    a = total - b
    m = rng.randint(30, 100)
    n = rng.randint(10, m - 5)
    shape = rng.choice(_SHAPES_BY_TIER[tier])
    told_a, told_b = (a, b) if shape in _ADDS else (m, n)
    who, friend = rng.sample(NAMES, 2)
    things = rng.choice(_THINGS)
    words, answer, worked = _story(shape, who, friend, things, told_a, told_b)
    other = told_a - told_b if shape in _ADDS else told_a + told_b
    return Built(
        prompt=(text(words),),
        answer=_Int(answer),
        wrong=named_wrongs(
            [
                ("used_the_other_operation", other),
                ("gave_the_first_number", told_a),
                ("gave_the_second_number", told_b),
            ]
        ),
        values={
            "a": a,
            "b": b,
            "told1": told_a,
            "told2": told_b,
            "m": m,
            "n": n,
            "answer": answer,
            "worked": worked,
        },
    )


def generators() -> list[SkillGenerator]:
    return [
        SkillGenerator(
            "word_problems_100",
            0.4,
            AnswerForm.INTEGER,
            _build_story,
            ("used_the_other_operation", "gave_the_first_number", "gave_the_second_number"),
        )
    ]
