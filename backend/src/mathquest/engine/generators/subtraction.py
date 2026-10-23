# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false
"""Grade 2 subtraction of two-digit numbers, without and with borrowing.

Both skills ask in three forms that get harder: a sentence, the same take-away in words,
and a sentence with the amount taken away hidden. Every tier covers the whole range of its
skill (a top number from 20 to 99).

In every form the answer is the top number less the other number shown beside it, so the
values name that pair: ``top`` and ``bottom``.
"""

import random

import sympy

from mathquest.engine.generators._util import (
    Built,
    SkillGenerator,
    math,
    math_prompt,
    named_wrongs,
    text,
)
from mathquest.engine.types import AnswerForm, Prompt

_Int = sympy.Integer

_LEADS = ("Find the missing number. ", "What number is missing? ")


def _ask(rng: random.Random, tier: int, a: int, b: int) -> tuple[Prompt, int, int, str]:
    """The prompt for ``a - b`` and what it asks for: (prompt, answer, the number shown
    beside ``a``, a line for the story explanation)."""
    left = a - b
    if tier == 0:
        story = f"You take {b} out. How many are left?"
        return math_prompt(f"{a} - {b} = ?"), left, b, story
    if tier == 1:
        prompt: Prompt = rng.choice(
            (
                (
                    text("Take away "),
                    math(str(b)),
                    text(" from "),
                    math(str(a)),
                    text(". What is left?"),
                ),
                (text("What is "), math(str(a)), text(" minus "), math(str(b)), text("?")),
                (
                    text("You have "),
                    math(str(a)),
                    text(". You give away "),
                    math(str(b)),
                    text(". How many are left?"),
                ),
            )
        )
        return prompt, left, b, f"You take {b} out. How many are left?"
    sentence = rng.choice((f"{a} - ? = {left}", f"{left} = {a} - ?"))
    story = f"You take some out. Now the jar holds {left}. How many did you take out?"
    return (text(rng.choice(_LEADS)), math(sentence)), b, left, story


def _slips(top: int, bottom: int, regroup: bool) -> list[tuple[str, int]]:
    """What a child types for ``top - bottom``: the numbers added, or (without borrowing)
    only the tens or only the ones worked, or (with it) the column slips."""
    top_tens, top_ones = divmod(top, 10)
    bottom_tens, bottom_ones = divmod(bottom, 10)
    wrong = [("added_instead", top + bottom)]
    if regroup:
        wrong += [
            # The smaller ones taken from the bigger: 62 - 28 as 6 - 2 tens and 8 - 2 ones.
            ("subtracted_backwards", (top_tens - bottom_tens) * 10 + (bottom_ones - top_ones)),
            # A ten is borrowed but the tens are not lowered: 62 - 28 as 12 - 8 and 6 - 2.
            ("forgot_to_lower_the_tens", top - bottom + 10),
        ]
    else:
        wrong += [
            ("left_out_the_ones", (top_tens - bottom_tens) * 10),
            ("left_out_the_tens", top_ones - bottom_ones),
        ]
    return wrong


def _built(rng: random.Random, tier: int, a: int, b: int, regroup: bool) -> Built:
    prompt, answer, shown, story = _ask(rng, tier, a, b)
    return Built(
        prompt=prompt,
        answer=_Int(answer),
        wrong=named_wrongs(_slips(a, shown, regroup), floor=1),
        values={
            "a": a,
            "b": b,
            "r": a - b,
            "top": a,
            "bottom": shown,
            "top_tens": a // 10,
            "top_ones": a % 10,
            "bottom_tens": shown // 10,
            "bottom_ones": shown % 10,
            "answer": answer,
            "story": story,
        },
    )


def _build_sub_no_regroup(rng: random.Random, tier: int) -> Built:
    """Two two-digit numbers where no column needs a borrowed ten."""
    while True:
        top_tens = rng.randint(2, 9)
        bottom_tens = rng.randint(1, top_tens)
        top_ones = rng.randint(0, 9)
        bottom_ones = rng.randint(0, top_ones)
        a, b = top_tens * 10 + top_ones, bottom_tens * 10 + bottom_ones
        if a != b:
            return _built(rng, tier, a, b, regroup=False)


def _build_sub_regroup(rng: random.Random, tier: int) -> Built:
    """Two two-digit numbers where the ones of the top number are too few, so a ten is
    borrowed (a zero in the ones place among them)."""
    top_tens = rng.randint(2, 9)
    bottom_tens = rng.randint(1, top_tens - 1)
    bottom_ones = rng.randint(1, 9)
    top_ones = rng.randint(0, bottom_ones - 1)
    return _built(rng, tier, top_tens * 10 + top_ones, bottom_tens * 10 + bottom_ones, True)


def generators() -> list[SkillGenerator]:
    form = AnswerForm.INTEGER
    return [
        SkillGenerator(
            "sub_2digit_no_regroup",
            -0.3,
            form,
            _build_sub_no_regroup,
            ("added_instead", "left_out_the_ones", "left_out_the_tens"),
        ),
        SkillGenerator(
            "sub_2digit_regroup",
            0.3,
            form,
            _build_sub_regroup,
            ("added_instead", "subtracted_backwards", "forgot_to_lower_the_tens"),
        ),
    ]
