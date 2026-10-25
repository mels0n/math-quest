# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false
"""Grade 2 and 3 adding and subtracting of three-digit numbers, without and with regrouping.

Each skill asks in three forms that get harder, and every tier covers the whole range of its
skill (three-digit numbers, sums to 999, differences of at least 100):

- adding: a sentence, the same in words, and the second number told in hundreds, tens and
  ones;
- subtracting: a sentence, the same in words, and a sentence with the amount taken away
  hidden.

A regrouping subtraction often has a zero in the tens place of the top number (about two
questions in five), so that borrowing across a zero (503 - 178, about one in five) comes up
in every tier.

In every form the answer is the top number worked with the other number shown beside it, so
the values name that pair: ``top`` and ``bottom``.
"""

import random

import sympy

from mathquest.engine.generators._util import (
    MISSING_LEADS,
    Built,
    SkillGenerator,
    math,
    math_prompt,
    named_wrongs,
    text,
)
from mathquest.engine.types import AnswerForm, Prompt

_Int = sympy.Integer

_ZERO_SHARE = 0.25
"""How often a draw for a regrouping subtraction starts from a top number with a zero in the
tens place. A draw that needs no borrowing is thrown away, which favours that form, so about
39% of the questions have the zero and about 19% borrow across it (the ones are too few as
well, as in 503 - 178)."""


def _split(n: int) -> tuple[int, int, int]:
    return n // 100, n // 10 % 10, n % 10


def _place_values(prefix: str, n: int) -> dict[str, int]:
    hundreds, tens, ones = _split(n)
    return {f"{prefix}_hundreds": hundreds, f"{prefix}_tens": tens, f"{prefix}_ones": ones}


def _parts(n: int) -> str:
    """``n`` told in its places, leaving out an empty place: "2 hundreds, 4 tens and 7 ones"."""
    hundreds, tens, ones = _split(n)
    told = [
        f"{count} {one}{'' if count == 1 else 's'}"
        for count, one in ((hundreds, "hundred"), (tens, "ten"), (ones, "one"))
        if count
    ]
    return told[0] if len(told) == 1 else ", ".join(told[:-1]) + " and " + told[-1]


# --- adding ----------------------------------------------------------------------------------


def _ask_add(rng: random.Random, tier: int, a: int, b: int) -> tuple[Prompt, str]:
    """The prompt for ``a + b`` and a line for the story explanation."""
    story = f"Then you add {_parts(b)}. How many beads are in the jar now?"
    if tier == 0:
        return math_prompt(f"{a} + {b} = ?"), story
    if tier == 1:
        prompt: Prompt = rng.choice(
            (
                (text("What is "), math(str(a)), text(" plus "), math(str(b)), text("?")),
                (
                    text("Add "),
                    math(str(a)),
                    text(" and "),
                    math(str(b)),
                    text(". What is the sum?"),
                ),
                (
                    text("You have "),
                    math(str(a)),
                    text(". You get "),
                    math(str(b)),
                    text(" more. How many do you have now?"),
                ),
            )
        )
        return prompt, story
    told = _parts(b)
    prompt = rng.choice(
        (
            (text("What is "), math(str(a)), text(f" plus {told}?")),
            (text(f"Add {told} to "), math(str(a)), text(". What is the total?")),
        )
    )
    return prompt, story


def _add_slips(a: int, b: int, regroup: bool) -> list[tuple[str, int]]:
    """What a child types for ``a + b``: the numbers subtracted, and (without carrying) the
    hundreds of the second number left out, or (with it) a carry forgotten or put in the
    wrong place."""
    total = a + b
    wrong = [("subtracted_instead", abs(a - b))]
    if regroup:
        ones_carry = (a % 10 + b % 10) // 10
        tens_carry = (a // 10 % 10 + b // 10 % 10 + ones_carry) // 10
        wrong += [
            ("forgot_the_carry", total - 10 * ones_carry - 100 * tens_carry),
            # The carried ten is written in the hundreds place: 478 + 256 as 4 + 2 + 1 hundreds.
            ("carried_to_the_wrong_place", total + 90 * ones_carry),
        ]
    else:
        # The second number's hundreds are left out: 342 + 125 as 342 + 25.
        wrong.append(("left_out_the_hundreds", a + b % 100))
    return wrong


def _built_add(rng: random.Random, tier: int, a: int, b: int, regroup: bool) -> Built:
    prompt, story = _ask_add(rng, tier, a, b)
    ones_total = a % 10 + b % 10
    ones_carry = ones_total // 10
    tens_total = a // 10 % 10 + b // 10 % 10 + ones_carry
    tens_carry = tens_total // 10
    hundreds_total = a // 100 + b // 100 + tens_carry
    ones_line = (
        f"The ones make {ones_total}. Write {ones_total % 10} and carry 1 ten."
        if ones_carry
        else f"The ones make {ones_total}."
    )
    tens_line = (
        f"Add the tens{' and the carried ten' if ones_carry else ''}. That makes {tens_total}."
        + (f" Write {tens_total % 10} and carry 1 hundred." if tens_carry else "")
    )
    hundreds_line = (
        f"Add the hundreds{' and the carried hundred' if tens_carry else ''}."
        f" That makes {hundreds_total}."
    )
    return Built(
        prompt=prompt,
        answer=_Int(a + b),
        wrong=named_wrongs(_add_slips(a, b, regroup), floor=1),
        values={
            "a": a,
            "b": b,
            "r": a + b,
            "top": a,
            "bottom": b,
            **_place_values("top", a),
            **_place_values("bottom", b),
            "ones_total": ones_total,
            "tens_total": tens_total,
            "hundreds_total": hundreds_total,
            "ones_line": ones_line,
            "tens_line": tens_line,
            "hundreds_line": hundreds_line,
            "parts": _parts(b),
            "answer": a + b,
            "story": story,
        },
    )


def _build_add_no_regroup(rng: random.Random, tier: int) -> Built:
    """Two three-digit numbers where no column makes ten or more."""
    a_hundreds = rng.randint(1, 8)
    b_hundreds = rng.randint(1, 9 - a_hundreds)
    a_tens, a_ones = rng.randint(0, 9), rng.randint(0, 9)
    b_tens, b_ones = rng.randint(0, 9 - a_tens), rng.randint(0, 9 - a_ones)
    a = a_hundreds * 100 + a_tens * 10 + a_ones
    b = b_hundreds * 100 + b_tens * 10 + b_ones
    return _built_add(rng, tier, a, b, regroup=False)


def _build_add_regroup(rng: random.Random, tier: int) -> Built:
    """Two three-digit numbers with a sum of at most 999 where the ones, the tens or both
    make ten or more."""
    while True:
        a = rng.randint(100, 899)
        b = rng.randint(100, 999 - a)
        ones_carry = (a % 10 + b % 10) // 10
        if ones_carry or a // 10 % 10 + b // 10 % 10 >= 10:
            return _built_add(rng, tier, a, b, regroup=True)


# --- subtracting -----------------------------------------------------------------------------


def _ask_sub(rng: random.Random, tier: int, a: int, b: int) -> tuple[Prompt, int, int, str]:
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
    story = f"You take some out. Now it holds {left}. How many did you take out?"
    return (text(rng.choice(MISSING_LEADS)), math(sentence)), b, left, story


def _sub_slips(top: int, bottom: int, regroup: bool) -> list[tuple[str, int]]:
    """What a child types for ``top - bottom``: the numbers added, or (without borrowing)
    only some places worked, or (with it) the column slips."""
    top_hundreds, top_tens, top_ones = _split(top)
    bottom_hundreds, bottom_tens, bottom_ones = _split(bottom)
    wrong = [("added_instead", top + bottom)]
    if regroup:
        left = top - bottom
        wrong += [
            # The smaller digit taken from the bigger in every column: 503 - 178 as 5 - 1,
            # 7 - 0 and 8 - 3.
            (
                "subtracted_backwards",
                abs(top_hundreds - bottom_hundreds) * 100
                + abs(top_tens - bottom_tens) * 10
                + abs(top_ones - bottom_ones),
            ),
            # A ten or a hundred is borrowed but the next place is not lowered: 452 - 178 as
            # 12 - 8, 15 - 7 and 4 - 1.
            (
                "forgot_to_lower_the_next_place",
                left + 10 * (top_ones < bottom_ones) + 100 * (top_tens < bottom_tens),
            ),
        ]
    else:
        wrong += [
            (
                "left_out_the_ones",
                (top_hundreds - bottom_hundreds) * 100 + (top_tens - bottom_tens) * 10,
            ),
            ("left_out_the_hundreds", top % 100 - bottom % 100),
        ]
    return wrong


def _borrowing(top: int, bottom: int) -> tuple[str, str, str, str]:
    """The three columns of ``top - bottom`` worked as a child writes it, and a line that
    names the first place that is borrowed from (or none)."""
    hundreds, tens, ones = _split(top)
    bottom_hundreds, bottom_tens, bottom_ones = _split(bottom)
    first = "The ones are enough. Start there."
    borrowed_ones = ones < bottom_ones
    if ones < bottom_ones and tens == 0:
        first = "The ones are too few and the tens place is a zero. Borrow a hundred first."
        ones_line = (
            "The ones are too few and the tens place is a zero. Borrow a hundred."
            f" It makes 10 tens. Borrow a ten from them. The ones become {ones + 10}."
            f" Take {bottom_ones} from {ones + 10} to leave {ones + 10 - bottom_ones}."
        )
        hundreds, tens, ones = hundreds - 1, 9, ones + 10
    elif ones < bottom_ones:
        first = "The ones are too few, so borrow a ten."
        ones_line = (
            f"The ones are too few. Borrow a ten. The ones become {ones + 10}."
            f" Take {bottom_ones} from {ones + 10} to leave {ones + 10 - bottom_ones}."
        )
        tens, ones = tens - 1, ones + 10
    else:
        ones_line = (
            f"Take {bottom_ones} from {ones} in the ones place. That leaves {ones - bottom_ones}."
        )
    if tens < bottom_tens:
        if not borrowed_ones:
            first = "The ones are enough. The tens are too few, so borrow a hundred."
        tens_line = (
            f"The tens are too few. Borrow a hundred. The tens become {tens + 10}."
            f" Take {bottom_tens} from {tens + 10} to leave {tens + 10 - bottom_tens}."
        )
        hundreds, tens = hundreds - 1, tens + 10
    else:
        tens_line = (
            f"Take {bottom_tens} from {tens} in the tens place. That leaves {tens - bottom_tens}."
        )
    hundreds_line = (
        f"Take {bottom_hundreds} from {hundreds} in the hundreds place."
        f" That leaves {hundreds - bottom_hundreds}."
    )
    return first, ones_line, tens_line, hundreds_line


def _built_sub(rng: random.Random, tier: int, a: int, b: int, regroup: bool) -> Built:
    prompt, answer, shown, story = _ask_sub(rng, tier, a, b)
    first, ones_line, tens_line, hundreds_line = _borrowing(a, shown)
    top_hundreds, top_tens, top_ones = _split(a)
    bottom_hundreds, bottom_tens, bottom_ones = _split(shown)
    look = (
        f"Think of the missing number as {a} less {shown}."
        if tier == 2
        else f"Look at {a} and {shown}."
    )
    return Built(
        prompt=prompt,
        answer=_Int(answer),
        wrong=named_wrongs(_sub_slips(a, shown, regroup), floor=1),
        values={
            "a": a,
            "b": b,
            "r": a - b,
            "top": a,
            "bottom": shown,
            **_place_values("top", a),
            **_place_values("bottom", shown),
            "ones_diff": top_ones - bottom_ones,
            "tens_diff": top_tens - bottom_tens,
            "hundreds_diff": top_hundreds - bottom_hundreds,
            "look": look,
            "first_borrow": first,
            "ones_line": ones_line,
            "tens_line": tens_line,
            "hundreds_line": hundreds_line,
            "answer": answer,
            "story": story,
        },
    )


def _build_sub_no_regroup(rng: random.Random, tier: int) -> Built:
    """Two three-digit numbers where no column needs a borrowed ten or hundred."""
    top_hundreds = rng.randint(2, 9)
    bottom_hundreds = rng.randint(1, top_hundreds - 1)
    top_tens, top_ones = rng.randint(0, 9), rng.randint(0, 9)
    bottom_tens, bottom_ones = rng.randint(0, top_tens), rng.randint(0, top_ones)
    a = top_hundreds * 100 + top_tens * 10 + top_ones
    b = bottom_hundreds * 100 + bottom_tens * 10 + bottom_ones
    return _built_sub(rng, tier, a, b, regroup=False)


def _build_sub_regroup(rng: random.Random, tier: int) -> Built:
    """Two three-digit numbers, a difference of at least 100, where the ones or the tens of
    the top number are too few (a zero in the tens place among them)."""
    while True:
        if rng.random() < _ZERO_SHARE:
            a = rng.randint(2, 9) * 100 + rng.randint(0, 9)
        else:
            a = rng.randint(200, 999)
        b = rng.randint(100, a - 100)
        if a % 10 < b % 10 or a // 10 % 10 < b // 10 % 10:
            return _built_sub(rng, tier, a, b, regroup=True)


def generators() -> list[SkillGenerator]:
    form = AnswerForm.INTEGER
    return [
        SkillGenerator(
            "add_3digit_no_regroup",
            0.5,
            form,
            _build_add_no_regroup,
            ("subtracted_instead", "left_out_the_hundreds"),
        ),
        SkillGenerator(
            "sub_3digit_no_regroup",
            0.6,
            form,
            _build_sub_no_regroup,
            ("added_instead", "left_out_the_ones", "left_out_the_hundreds"),
        ),
        SkillGenerator(
            "add_3digit_regroup",
            0.9,
            form,
            _build_add_regroup,
            ("subtracted_instead", "forgot_the_carry", "carried_to_the_wrong_place"),
        ),
        SkillGenerator(
            "sub_3digit_regroup",
            1.1,
            form,
            _build_sub_regroup,
            ("added_instead", "subtracted_backwards", "forgot_to_lower_the_next_place"),
        ),
    ]
