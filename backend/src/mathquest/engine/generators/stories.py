# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false
"""Story problems within 20 (1.OA.A.1): adding to, taking from, putting together, taking
apart, comparing, and stories where the change or the start is the unknown.

The tiers are the shapes of the story. A story that adds tells ``a`` and ``b`` (``b`` is less
than ``a``, and ``a + b`` is at most 20). A story that takes away tells ``m`` and ``n`` (``n`` is
less than ``m``, and ``m`` is at most 20), so take-aways can cross ten, as 15 - 8 does. Word
templates retell one of the two pairs with their own answer, so the shape is theirs to choose.
``told1`` and ``told2`` are the pair the bare story tells, for hints.
"""

import random

import sympy

from mathquest.engine.generators._util import (
    NAMES,
    Built,
    SkillGenerator,
    named_wrongs,
    noun,
    text,
)
from mathquest.engine.types import AnswerForm

_Int = sympy.Integer

# Plural nouns that add only an s, so one of them takes the singular.
_THINGS = (
    "apples",
    "pears",
    "cats",
    "dogs",
    "birds",
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
    "books",
)
_SHAPES_BY_TIER = (
    ("add_to", "take_from"),
    ("put_together", "take_apart", "compare_more", "compare_fewer"),
    ("change_add", "change_take", "start_add", "start_take"),
)
# The shapes whose answer is the sum of the two numbers told; the rest take one from the other.
_ADDS = frozenset({"add_to", "put_together", "start_take"})


def _story(shape: str, n: str, f: str, things: str, a: int, b: int) -> tuple[str, int, str]:
    """The story text, its answer and a worked line, for ``a`` and ``b``."""
    many = f"{noun(a, things)}"
    little = f"{noun(b, things)}"
    if shape == "add_to":
        return (
            f"{n} has {a} {many}. {f} gives {n} {b} more. How many {things} does {n} have now?",
            a + b,
            f"Put {a} and {b} together. That makes {a + b}.",
        )
    if shape == "take_from":
        return (
            f"{n} has {a} {many}. {n} gives {b} to {f}. How many {things} does {n} have left?",
            a - b,
            f"Start with {a}. Take away {b}. That leaves {a - b}.",
        )
    if shape == "put_together":
        return (
            f"{n} has {a} red {many} and {b} blue {little}. "
            f"How many {things} does {n} have in all?",
            a + b,
            f"Put {a} and {b} together. That makes {a + b}.",
        )
    if shape == "take_apart":
        verb = "is" if b == 1 else "are"
        return (
            f"{n} has {a} {many}. {b} of them {verb} red. The rest are blue. How many are blue?",
            a - b,
            f"Start with {a}. Take away {b}, the red ones. That leaves {a - b}.",
        )
    if shape == "compare_more":
        return (
            f"{n} has {a} {many}. {f} has {b}. How many more {things} does {n} have?",
            a - b,
            f"Match them up. {a} is {a - b} more than {b}.",
        )
    if shape == "compare_fewer":
        return (
            f"{n} has {a} {many}. {f} has {b}. How many fewer {things} does {f} have?",
            a - b,
            f"Match them up. {b} is {a - b} fewer than {a}.",
        )
    if shape == "change_add":
        return (
            f"{n} has {b} {little}. Then {n} gets some more. Now {n} has {a}. "
            f"How many did {n} get?",
            a - b,
            f"Count up from {b} to {a}. You count {a - b}.",
        )
    if shape == "change_take":
        return (
            f"{n} has {a} {many}. {n} gives some away. Now {n} has {b}. "
            f"How many did {n} give away?",
            a - b,
            f"Count back from {a} to {b}. You count {a - b}.",
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
        f"Put back the {b} that went. {a} and {b} make {a + b}.",
    )


def _build_story(rng: random.Random, tier: int) -> Built:
    total = rng.randint(3, 20)
    b = rng.randint(1, (total - 1) // 2)
    a = total - b
    m = rng.randint(3, 20)
    n = rng.randint(1, m - 1)
    shape = rng.choice(_SHAPES_BY_TIER[tier])
    told_a, told_b = (a, b) if shape in _ADDS else (m, n)
    who, friend = rng.sample(NAMES, 2)
    things = rng.choice(_THINGS)
    story, answer, worked = _story(shape, who, friend, things, told_a, told_b)
    other = told_a - told_b if shape in _ADDS else told_a + told_b
    return Built(
        prompt=(text(story),),
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
            "word_problems_20",
            -0.6,
            AnswerForm.INTEGER,
            _build_story,
            ("used_the_other_operation", "gave_the_first_number", "gave_the_second_number"),
        )
    ]
