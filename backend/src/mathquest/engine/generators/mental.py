# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false
"""Grade 2 mental arithmetic: adding several two-digit numbers, ten or a hundred more or
less, and quick facts within 20."""

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


# --- add_several_2digit -----------------------------------------------------------------

_SEVERAL_LEADS = ("", "Add all the numbers. ", "Find the total. ")
_COUNT_WORDS = {3: "three", 4: "four"}
_SEVERAL_SUMS = ((40, 99), (50, 99), (101, 297))
_SEVERAL_BIGGEST = (60, 45, 99)
"""The sums a tier may make, and the biggest number drawn for it (so that four numbers can
still stay under 100)."""


def _draw_numbers(rng: random.Random, tier: int, count: int) -> list[int]:
    """``count`` two-digit numbers whose sum is one the tier allows."""
    low, high = _SEVERAL_SUMS[tier]
    while True:
        numbers = [rng.randint(10, _SEVERAL_BIGGEST[tier]) for _ in range(count)]
        if low <= sum(numbers) <= high:
            return numbers


def _plural(count: int, one: str) -> str:
    return f"{count} {one}" if count == 1 else f"{count} {one}s"


def _hundreds_note(tens_total: int) -> str:
    """Tens that make a hundred or more, in words; empty when they do not."""
    if tens_total < 10:
        return ""
    hundreds, tens = divmod(tens_total, 10)
    spoken = _plural(hundreds, "hundred")
    if tens:
        spoken += f" and {_plural(tens, 'ten')}"
    return f"That is {spoken}. "


def _build_add_several(rng: random.Random, tier: int) -> Built:
    """Three numbers under 100 (tier 0), four numbers under 100 (tier 1), or three numbers
    that pass 100 (tier 2). The ones are added first, then the tens and what they carry."""
    count = 4 if tier == 1 else 3
    numbers = _draw_numbers(rng, tier, count)
    total = sum(numbers)
    sentence = " + ".join(str(n) for n in numbers) + " = ?"
    lead = rng.choice(_SEVERAL_LEADS)
    prompt: Prompt = (text(lead), math(sentence)) if lead else math_prompt(sentence)
    ones_total = sum(n % 10 for n in numbers)
    carry, ones_left = divmod(ones_total, 10)
    tens_total = sum(n // 10 for n in numbers) + carry
    carry_note = (
        f"Keep {ones_left} in the ones place. Carry {carry} to the tens place. " if carry else ""
    )
    values: dict[str, int | str] = {
        "count": _COUNT_WORDS[count],
        "ones_total": str(ones_total),
        "carry_note": carry_note,
        "tens_line": f"The tens{' and the carry' if carry else ''} make {tens_total} tens.",
        "hundreds_note": _hundreds_note(tens_total),
        "nums": ", ".join(str(n) for n in numbers[:-1]) + f" and {numbers[-1]}",
        "first_tens": numbers[0] // 10,
        "first_ones": numbers[0] % 10,
        "total": str(total),
        # Only the four-number tier has a fourth number; no template that asks for it is
        # served to a tier without one.
        "d": "0",
    }
    for name, number in zip("abcd", numbers, strict=False):
        values[name] = number
    return Built(
        prompt=prompt,
        answer=_Int(total),
        wrong=named_wrongs(
            [
                # The last number is left out of the sum.
                ("left_out_the_last", total - numbers[-1]),
                # The carried tens are lost: 28 + 15 + 19 as 4 tens and 2 ones.
                ("forgot_the_carry", total - 10 * carry),
                # The ones make two or more tens but only one is carried.
                ("carried_one_ten", total - 10 * (carry - 1) if carry >= 2 else total),
                # The hundred is dropped from a sum that passes 100.
                ("dropped_the_hundred", total - 100),
            ],
            floor=1,
        ),
        values=values,
    )


# --- mental_add_10_100 ------------------------------------------------------------------

_MENTAL_ASKS = (("What is", "?"), ("Find", "."), ("What number is", "?"))
_STEP_WORDS = {10: "ten", 100: "hundred"}
_PLACES = {10: "tens", 100: "hundreds"}


def _build_mental(rng: random.Random, tier: int) -> Built:
    """Ten more or less (tier 0), a hundred more or less (tier 1), or either, also hiding
    the number that the shown one is ten or a hundred more or less than (tier 2). Numbers
    run from 100 to 1000. ``move`` is the signed step from the shown number to the answer."""
    step = 100 if tier == 1 or (tier == 2 and rng.choice((True, False))) else 10
    hidden = tier == 2 and rng.choice((True, False))
    up = rng.choice((True, False))
    prompt: Prompt
    if hidden:
        if up:
            answer = rng.randint(100, 1000 - step)
            shown = answer + step
            sentence = rng.choice((f"? + {step} = {shown}", f"{step} + ? = {shown}"))
        else:
            answer = rng.randint(100 + step, 999)
            shown = answer - step
            sentence = rng.choice((f"? - {step} = {shown}", f"{shown} = ? - {step}"))
        # The shown number is ``step`` more than the answer when the answer is found by
        # taking away, and the other way round.
        move = -step if up else step
        prompt = (text("Find the missing number. "), math(sentence))
    else:
        shown = rng.randint(100, 1000 - step) if up else rng.randint(100 + step, 999)
        move = step if up else -step
        answer = shown + move
        if rng.choice((True, False)):
            asking, end = rng.choice(_MENTAL_ASKS)
            word = "more" if up else "less"
            prompt = (text(f"{asking} {step} {word} than "), math(str(shown)), text(end))
        elif up:
            prompt = math_prompt(rng.choice((f"{shown} + {step} = ?", f"{step} + {shown} = ?")))
        else:
            prompt = math_prompt(f"{shown} - {step} = ?")
    sign = 1 if move > 0 else -1
    other = 110 - step
    place = (shown // step) % 10
    return Built(
        prompt=prompt,
        answer=_Int(answer),
        wrong=named_wrongs(
            [
                ("wrong_direction", shown - move),
                ("used_the_other_step", shown + sign * other),
                ("changed_the_ones", shown + sign),
            ],
            floor=1,
        ),
        values={
            "n": shown,
            "answer": answer,
            "dir": "up" if move > 0 else "down",
            "way": "more" if move > 0 else "less",
            "step_word": _STEP_WORDS[step],
            "place": _PLACES[step],
            "other_place": _PLACES[other],
            "digit": place,
            "step_say": "ten" if step == 10 else "one hundred",
            "n_hundreds": shown // 100,
            "n_tens": shown // 10 % 10,
            "n_ones": shown % 10,
            # Only a digit that wraps past 9 or 0 changes the place beside it too.
            "wrap_note": (
                "Watch out, the next place changes too. "
                if (place == 9 and move > 0) or (place == 0 and move < 0)
                else ""
            ),
        },
    )


# --- fluency_within_20 ------------------------------------------------------------------


def _add_worked(a: int, b: int) -> str:
    total = a + b
    big, small = max(a, b), min(a, b)
    if a == b:
        return f"This is a double. Double {a} is {total}."
    if big - small == 1:
        return f"Double {small}, then add one. Double {small} is {2 * small}."
    if big == 10:
        return f"Ten and {small} make {total}."
    if total > 10:
        gap = 10 - big
        return (
            f"Make ten with {big} and {gap}. Take {gap} from {small}. "
            f"Now ten and {small - gap} make {total}."
        )
    return f"Start at {big} and count on {small}."


def _sub_worked(top: int, take: int) -> str:
    ones = top % 10
    if take == 10:
        return f"Ten less than {top} is {top - 10}."
    if 10 < top < 20 and ones < take < 10:
        return f"Count back {ones} to reach ten. Then count back {take - ones} more."
    return f"Think about {take} and {top - take}. They make {top}."


def _build_fluency(rng: random.Random, tier: int) -> Built:
    """Addition facts (tier 0), take-away facts (tier 1), or either (tier 2), all within 20
    and all asked as a plain sentence."""
    adding = tier == 0 or (tier == 2 and rng.choice((True, False)))
    wrong: list[tuple[str, int]]
    if adding:
        total = rng.randint(2, 20)
        a = rng.randint(max(1, total - 10), min(10, total - 1))
        b = total - a
        left, right = (a, b) if rng.choice((True, False)) else (b, a)
        prompt = math_prompt(f"{left} + {right} = ?")
        answer, worked = total, _add_worked(a, b)
        wrong = [("subtracted_instead", abs(a - b))]
        top, take = a, b
    else:
        top = rng.randint(2, 20)
        take = rng.randint(1, top - 1)
        prompt = math_prompt(f"{top} - {take} = ?")
        answer, worked = top - take, _sub_worked(top, take)
        wrong = [("added_instead", top + take)]
        a, b = top, take
    wrong += [("one_too_few", answer - 1), ("one_too_many", answer + 1)]
    return Built(
        prompt=prompt,
        answer=_Int(answer),
        wrong=named_wrongs(wrong, floor=1),
        values={"a": a, "b": b, "top": top, "take": take, "answer": answer, "worked": worked},
    )


def generators() -> list[SkillGenerator]:
    form = AnswerForm.INTEGER
    return [
        SkillGenerator(
            "add_several_2digit",
            0.2,
            form,
            _build_add_several,
            ("left_out_the_last", "forgot_the_carry", "carried_one_ten", "dropped_the_hundred"),
        ),
        SkillGenerator(
            "mental_add_10_100",
            -0.2,
            form,
            _build_mental,
            ("wrong_direction", "used_the_other_step", "changed_the_ones"),
        ),
        SkillGenerator(
            "fluency_within_20",
            -0.4,
            form,
            _build_fluency,
            ("subtracted_instead", "added_instead", "one_too_few", "one_too_many"),
        ),
    ]
