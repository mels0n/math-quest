# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false
"""Grade 1 and 2 work with tens: ten more and ten less, subtracting tens, adding ones and
tens to a two-digit number, and counting by twos and fives.

Every tier covers the whole range of its skill and gets harder through the form of the
question, except where the skill's own cases are what the tiers are (adding ones, adding
tens, adding ones that make a new ten).
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


# --- ten_more_ten_less ------------------------------------------------------------------

_TEN_ASKS = (("What is", "?"), ("Find", "."), ("What number is", "?"))


def _build_ten_more_less(rng: random.Random, tier: int) -> Built:
    """Tier 0 asks in words, tier 1 writes a sum or take-away with ten, tier 2 hides the
    number that ten more or ten less gives the one shown. ``step`` is the move from the
    shown number to the answer."""
    prompt: Prompt
    if tier < 2:
        more = rng.choice((True, False))
        shown = rng.randint(10, 90) if more else rng.randint(20, 100)
        step = 10 if more else -10
        if tier == 0:
            word = "more" if more else "less"
            asking, end = rng.choice(_TEN_ASKS)
            prompt = (text(f"{asking} 10 {word} than "), math(str(shown)), text(end))
        else:
            prompt = math_prompt(
                rng.choice((f"{shown} + 10 = ?", f"10 + {shown} = ?"))
                if more
                else f"{shown} - 10 = ?"
            )
    else:
        if rng.choice((True, False)):
            hidden = rng.randint(10, 90)
            shown, step = hidden + 10, -10
            sentence = rng.choice((f"? + 10 = {shown}", f"10 + ? = {shown}", f"{shown} = ? + 10"))
        else:
            hidden = rng.randint(20, 100)
            shown, step = hidden - 10, 10
            sentence = rng.choice((f"? - 10 = {shown}", f"{shown} = ? - 10"))
        prompt = (text("Find the missing number. "), math(sentence))
    answer = shown + step
    return Built(
        prompt=prompt,
        answer=_Int(answer),
        wrong=named_wrongs(
            [
                ("wrong_direction", shown - step),
                ("changed_the_ones", shown + (1 if step > 0 else -1)),
                ("said_the_tens_digit", answer // 10),
            ]
        ),
        values={
            "n": shown,
            "answer": answer,
            "dir": "up" if step > 0 else "down",
            "way": "more" if step > 0 else "less",
        },
    )


# --- sub_tens_within_100 ----------------------------------------------------------------

_TENS_PAIRS = [(top, take) for top in range(20, 100, 10) for take in range(10, top, 10)]


def _build_sub_tens(rng: random.Random, tier: int) -> Built:
    """Whole tens from whole tens, 20 to 90. Tier 0 is the take-away as a sentence, tier 1
    asks it in words, tier 2 hides the amount taken or the number it was taken from."""
    top, take = rng.choice(_TENS_PAIRS)
    rest = top - take
    prompt: Prompt
    wrong: list[tuple[str, int]]
    if tier == 0:
        answer, shown = rest, (top, take)
        prompt = math_prompt(f"{top} - {take} = ?")
    elif tier == 1:
        answer, shown = rest, (top, take)
        prompt = rng.choice(
            (
                (
                    text("Take away "),
                    math(str(take)),
                    text(" from "),
                    math(str(top)),
                    text(". What is left?"),
                ),
                (text("What is "), math(str(top)), text(" minus "), math(str(take)), text("?")),
                (
                    text("You have "),
                    math(str(top)),
                    text(". You give away "),
                    math(str(take)),
                    text(". How many are left?"),
                ),
            )
        )
    elif rng.choice((True, False)):
        answer, shown = take, (top, rest)
        prompt = (text("Find the missing number. "), math(f"{top} - ? = {rest}"))
    else:
        answer, shown = top, (take, rest)
        prompt = (text("Find the missing number. "), math(f"? - {take} = {rest}"))
    wrong = [
        ("said_the_tens_digit", answer // 10),
        ("added_instead", shown[0] + shown[1]),
        ("subtracted_instead", abs(shown[0] - shown[1])),
        ("off_by_ten", answer + 10),
    ]
    return Built(
        prompt=prompt,
        answer=_Int(answer),
        wrong=named_wrongs(wrong),
        values={
            "top": top,
            "take": take,
            "rest": rest,
            "s1_tens": shown[0] // 10,
            "s2_tens": shown[1] // 10,
            "answer": answer,
        },
    )


# --- add_within_100_basic ---------------------------------------------------------------


def _build_add_ones_tens(rng: random.Random, tier: int) -> Built:
    """A two-digit number plus ones with no new ten (tier 0), plus whole tens (tier 1), or
    plus ones that make a new ten (tier 2). The answer stays within 100."""
    wrong: list[tuple[str, int]]
    if tier == 0:
        b = rng.randint(1, 9)
        a = rng.randint(1, 9) * 10 + rng.randint(0, 9 - b)
        wrong = [("added_to_the_tens", a + 10 * b), ("subtracted_instead", a - b)]
    elif tier == 1:
        b_tens = rng.randint(1, 8)
        b = b_tens * 10
        a = rng.randint(1, 9 - b_tens) * 10 + rng.randint(0, 9)
        wrong = [
            ("added_to_the_ones", a + b_tens),
            ("added_one_ten", a + 10),
            ("subtracted_instead", a - b),
        ]
    else:
        a_ones = rng.randint(1, 9)
        b = rng.randint(10 - a_ones, 9)
        a = rng.randint(1, 8) * 10 + a_ones
        total = a + b
        wrong = [
            ("forgot_the_new_ten", total - 10),
            ("wrote_the_ones_together", a // 10 * 100 + a_ones + b),
            ("added_to_the_tens", a + 10 * b),
        ]
    left, right = (b, a) if rng.choice((True, False)) else (a, b)
    ask = rng.randrange(3)
    prompt: Prompt
    if ask == 0:
        prompt = math_prompt(f"{left} + {right} = ?")
    elif ask == 1:
        prompt = (text("What is "), math(str(left)), text(" plus "), math(str(right)), text("?"))
    else:
        prompt = (text("Add. "), math(f"{left} + {right} = ?"))
    return Built(
        prompt=prompt,
        answer=_Int(a + b),
        wrong=named_wrongs(wrong),
        values={
            "a": a,
            "b": b,
            "a_tens": a // 10,
            "a_ones": a % 10,
            "b_tens": b // 10,
            "b_ones": b % 10,
        },
    )


# --- skip_count_2_5 ---------------------------------------------------------------------


def _build_skip_count_2_5(rng: random.Random, tier: int) -> Built:
    """Counting by 5s (to 100) or 2s (to 50). Tier 0 counts up from a multiple, tier 1 also
    counts back and counts the odd numbers by 2s, tier 2 hides a number inside a row.
    ``previous`` is the number before the blank and ``jump`` the signed step to the answer."""
    step = rng.choice((2, 5))
    other = 7 - step
    top = 100 if step == 5 else 50
    back = tier == 1 and rng.random() < 0.4
    odd = int(step == 2 and tier >= 1 and rng.random() < 0.4)
    prompt: Prompt
    if tier == 2:
        count = 5
        first = step * rng.randint(1, top // step - count + 1) + odd
        row = [first + step * i for i in range(count)]
        hide = rng.randint(1, 3)
        answer, previous = row[hide], row[hide - 1]
        shown = ["?" if i == hide else str(n) for i, n in enumerate(row)]
        prompt = (text("Fill in the missing number. "), math(", ".join(shown)))
    else:
        count = rng.randint(2, 4)
        reach = rng.randint(count + 1, top // step)
        if back:
            row = [step * reach + odd - step * i for i in range(count)]
            answer = row[-1] - step
            lead = rng.choice(("Count back by ", "Count down by "))
        else:
            answer = step * reach + odd
            row = [answer - step * i for i in range(count, 0, -1)]
            lead = rng.choice(("Count by ", "Keep counting by "))
        previous = row[-1]
        prompt = (text(f"{lead}{step}s. "), math(", ".join([*(str(n) for n in row), "?"])))
    sign = -1 if back else 1
    wrong = [
        ("counted_by_ones", previous + sign),
        ("used_the_other_step", previous + sign * other),
        ("skipped_a_number", answer + sign * step),
    ]
    return Built(
        prompt=prompt,
        answer=_Int(answer),
        wrong=named_wrongs(wrong),
        values={
            "previous": previous,
            "step": step,
            "jump": sign * step,
            "dir": "back" if back else "up",
            "way": "less" if back else "more",
            "answer": answer,
        },
    )


def generators() -> list[SkillGenerator]:
    form = AnswerForm.INTEGER
    return [
        SkillGenerator(
            "ten_more_ten_less",
            -1.4,
            form,
            _build_ten_more_less,
            ("wrong_direction", "changed_the_ones", "said_the_tens_digit"),
        ),
        SkillGenerator(
            "sub_tens_within_100",
            -0.8,
            form,
            _build_sub_tens,
            ("said_the_tens_digit", "added_instead", "subtracted_instead", "off_by_ten"),
        ),
        SkillGenerator(
            "add_within_100_basic",
            -0.7,
            form,
            _build_add_ones_tens,
            (
                "added_to_the_tens",
                "subtracted_instead",
                "added_to_the_ones",
                "added_one_ten",
                "forgot_the_new_ten",
                "wrote_the_ones_together",
            ),
        ),
        SkillGenerator(
            "skip_count_2_5",
            -0.8,
            form,
            _build_skip_count_2_5,
            ("counted_by_ones", "used_the_other_step", "skipped_a_number"),
        ),
    ]
