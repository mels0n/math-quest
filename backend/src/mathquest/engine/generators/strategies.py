# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false
"""Grade 1 addition strategies and number sentences within 20.

Counting on, making a ten, adding three numbers, doubles, finding the missing number of a
sentence, the four facts of a fact family and a true equation with a sum on each side.
Every tier covers the whole range of its skill and gets harder through the form of the
question, not by narrowing the numbers.
"""

import random

import sympy

from mathquest.engine.generators._util import (
    MISSING_LEADS,
    NAMES,
    Built,
    SkillGenerator,
    math,
    math_prompt,
    named_wrongs,
    noun,
    text,
)
from mathquest.engine.types import AnswerForm, Prompt

_Int = sympy.Integer


def _shown_wrongs(
    first: int, second: int, *, biggest_key: str = "gave_a_shown_number"
) -> list[tuple[str, int]]:
    """What a child types when the answer is the third number of a family: the two numbers
    shown added, taken apart, or the bigger of them copied."""
    return [
        ("added_the_shown", first + second),
        ("subtracted_the_shown", abs(first - second)),
        (biggest_key, max(first, second)),
    ]


# --- count_on ---------------------------------------------------------------------------

_COUNT_ON_ASKS = (
    ("Start at ", ". Count on ", " more. Where do you stop?"),
    ("Say ", ". Then count on ", " more. What is the last number you say?"),
    ("You are on ", ". Jump on ", " more. Which number do you reach?"),
)


def _build_count_on(rng: random.Random, tier: int) -> Built:
    """Tier 0 tells it in words (start, then count on), tier 1 writes the sum with the
    bigger number first, tier 2 with the bigger number second. The count is 1 to 5 and the
    total 2 to 20 in every tier."""
    more = rng.randint(1, 5)
    start = rng.randint(1, 20 - more) if tier == 0 else rng.randint(more + 1, 20 - more)
    total = start + more
    prompt: Prompt
    if tier == 0:
        lead, middle, end = rng.choice(_COUNT_ON_ASKS)
        prompt = (text(lead), math(str(start)), text(middle), math(str(more)), text(end))
    elif tier == 1:
        prompt = (text("Count on. "), math(f"{start} + {more} = ?"))
    else:
        prompt = (text("Count on from the bigger number. "), math(f"{more} + {start} = ?"))
    return Built(
        prompt=prompt,
        answer=_Int(total),
        wrong=named_wrongs(
            [
                ("counted_start", total - 1),
                ("went_one_too_far", total + 1),
                ("subtracted_instead", abs(start - more)),
            ]
        ),
        values={"start": start, "more": more},
    )


# --- make_ten_strategy ------------------------------------------------------------------


_TEN_CROSSING = [(a, b) for a in range(2, 10) for b in range(2, 10) if a + b >= 11]


def _build_make_ten(rng: random.Random, tier: int) -> Built:
    """A sum that crosses ten (11 to 18) with both addends 2 to 9. Tier 0 is the sum, tier 1
    splits it as ``8 + 5 = 10 + ?``, tier 2 hides one addend. ``first`` is the number the
    hints start from, always one the prompt shows."""
    left, right = rng.choice(_TEN_CROSSING)
    a, b = left, right
    total = a + b
    big = max(a, b)
    wrong: list[tuple[str, int]]
    if tier == 0:
        first, answer = big, total
        prompt: Prompt = (text("Make a ten first. "), math(f"{left} + {right} = ?"))
        wrong = [
            ("counted_start", total - 1),
            ("subtracted_instead", abs(a - b)),
            ("gave_the_leftover", total - 10),
        ]
    elif tier == 1:
        first, answer = big, total - 10
        prompt = math_prompt(f"{left} + {right} = 10 + ?")
        wrong = [
            ("gave_the_total", total),
            ("gave_the_gap_to_ten", 10 - first),
            ("subtracted_instead", abs(a - b)),
        ]
    else:
        first, answer = left, right
        prompt = math_prompt(f"{left} + ? = {total}")
        wrong = [
            ("gave_the_total", total),
            ("counted_start", answer + 1),
            ("added_instead", first + total),
        ]
    return Built(
        prompt=prompt,
        answer=_Int(answer),
        wrong=named_wrongs(wrong),
        values={
            "first": first,
            "to_ten": 10 - first,
            "past_ten": total - 10,
            "answer": answer,
        },
    )


# --- add_three_numbers ------------------------------------------------------------------

_THREES = (
    ("ducks", "frogs", "fish", "animals"),
    ("apples", "pears", "plums", "fruits"),
    ("balls", "kites", "drums", "toys"),
    ("roses", "tulips", "violets", "flowers"),
    ("cats", "dogs", "birds", "pets"),
    ("cups", "plates", "spoons", "things"),
)
_THREE_VERBS = (("has", "have"), ("sees", "see"), ("finds", "find"))


def _build_add_three(rng: random.Random, tier: int) -> Built:
    """Tier 0 is a plain sum of three numbers, tier 1 hides a pair that makes ten (the
    first and last number), tier 2 tells it as a story about three kinds of thing."""
    if tier == 1:
        x = rng.randint(1, 9)
        mid = rng.randint(1, 10)
        a, b, c = (x, mid, 10 - x) if rng.choice((True, False)) else (10 - x, mid, x)
        p, q, r = a, c, b
    else:
        total = rng.randint(3, 20)
        a = rng.randint(1, total - 2)
        b = rng.randint(1, total - a - 1)
        c = total - a - b
        p, q, r = a, b, c
    total = a + b + c
    prompt: Prompt
    if tier < 2:
        prompt = math_prompt(f"{a} + {b} + {c} = ?")
    else:
        n1, n2, n3, kind = rng.choice(_THREES)
        name = rng.choice(NAMES)
        does, do = rng.choice(_THREE_VERBS)
        prompt = (
            text(
                f"{name} {does} {a} {noun(a, n1)}, {b} {noun(b, n2)} "
                f"and {c} {noun(c, n3)}. How many {kind} does {name} {do} in all?"
            ),
        )
    return Built(
        prompt=prompt,
        answer=_Int(total),
        wrong=named_wrongs(
            [
                ("left_out_the_last", a + b),
                ("left_out_the_first", b + c),
                ("left_out_the_middle", a + c),
            ]
        ),
        values={"a": a, "b": b, "c": c, "p": p, "q": q, "r": r},
    )


# --- missing_number_20 ------------------------------------------------------------------

# The eight ways to hide one number of x + y = z, with the numbers shown, in order, and the
# one that is found: (sentence, shown, answer).
_MISSING_FORMS = {
    "A": ("{x} + ? = {z}", ("x", "z"), "y"),
    "B": ("? + {y} = {z}", ("y", "z"), "x"),
    "C": ("{z} - ? = {x}", ("z", "x"), "y"),
    "D": ("? - {y} = {x}", ("y", "x"), "z"),
    "E": ("{z} = {x} + ?", ("z", "x"), "y"),
    "F": ("{z} = ? + {y}", ("z", "y"), "x"),
    "G": ("{x} = {z} - ?", ("x", "z"), "y"),
    "H": ("{x} = ? - {y}", ("x", "y"), "z"),
}
_MISSING_BY_TIER = ("AB", "ABCEF", "DGHFC")


def _build_missing_number(rng: random.Random, tier: int) -> Built:
    """One number of ``x + y = z`` (z within 20) is hidden. Tier 0 hides an addend in a
    sum, tier 1 adds a take-away and the equals sign first, tier 2 hides the start of a
    take-away or the whole, and writes the answer on the right of the equals sign."""
    z = rng.randint(3, 20)
    x = rng.randint(1, z - 1)
    y = z - x
    nums = {"x": x, "y": y, "z": z}
    sentence, shown, hidden = _MISSING_FORMS[rng.choice(_MISSING_BY_TIER[tier])]
    first, second = nums[shown[0]], nums[shown[1]]
    return Built(
        prompt=(text(rng.choice(MISSING_LEADS)), math(sentence.format(**nums))),
        answer=_Int(nums[hidden]),
        wrong=named_wrongs(_shown_wrongs(first, second)),
        values={"x": x, "y": y, "z": z, "s1": first, "s2": second, "answer": nums[hidden]},
    )


# --- fact_families_20 -------------------------------------------------------------------


def _build_fact_family(rng: random.Random, tier: int) -> Built:
    """Three numbers ``x``, ``y`` and ``z = x + y`` (x and y differ). Tier 0 gives an addition
    fact and asks the same sum the other way round, tier 1 asks the related subtraction (or
    the addition that goes with a subtraction fact), tier 2 gives only a sentence to finish.
    Tiers 0 and 1 show the whole family, so their answer is one of the
    numbers on the page; tier 2 shows only the two numbers of its sentence."""
    z = rng.randint(3, 20)
    x = rng.choice([n for n in range(1, z) if 2 * n != z])
    y = z - x
    lo, hi = min(x, y), max(x, y)
    prompt: Prompt
    if tier == 0:
        answer, shown = z, (y, x)
        prompt = (
            text("You know that "),
            math(f"{x} + {y} = {z}"),
            text(". What is "),
            math(f"{y} + {x}"),
            text("?"),
        )
    elif tier == 1:
        take = rng.choice((x, y))
        left = z - take
        if rng.choice((True, False)):
            answer, shown = left, (z, take)
            known, ask = f"{x} + {y} = {z}", f"{z} - {take}"
        else:
            answer, shown = z, (take, left)
            known, ask = f"{z} - {take} = {left}", f"{take} + {left}"
        prompt = (text("You know that "), math(known), text(". What is "), math(ask), text("?"))
    else:
        # Only the two numbers of the sentence are shown, so the answer is not on the page.
        sentence, answer, shown = rng.choice(
            (
                (f"{x} + {y} = ?", z, (x, y)),
                (f"{y} + {x} = ?", z, (y, x)),
                (f"{z} - {x} = ?", y, (z, x)),
                (f"{z} - {y} = ?", x, (z, y)),
                (f"{x} + ? = {z}", y, (x, z)),
                (f"{z} - ? = {y}", x, (z, y)),
            )
        )
        prompt = (text("Finish the fact family. "), math(sentence))
    return Built(
        prompt=prompt,
        answer=_Int(answer),
        wrong=named_wrongs(_shown_wrongs(*shown)),
        values={
            "lo": lo,
            "hi": hi,
            "total": z,
            "answer": answer,
            "s1": shown[0],
            "s2": shown[1],
            "role": "the whole, the biggest of the three" if answer == z else "a part of the whole",
        },
    )


# --- doubles_near_doubles ---------------------------------------------------------------


def _build_doubles(rng: random.Random, tier: int) -> Built:
    """Tier 0 is a double, tier 1 a near double (the numbers are one apart), tier 2 finds
    the number that is added to itself to make a given total. ``shown`` is a number the
    prompt shows, for hints that must not give the answer away."""
    prompt: Prompt
    wrong: list[tuple[str, int]]
    if tier == 0:
        n = rng.randint(1, 10)
        answer, shown = 2 * n, n
        ask = rng.randrange(3)
        if ask == 0:
            prompt = math_prompt(f"{n} + {n} = ?")
        elif ask == 1:
            prompt = (text("What is double "), math(str(n)), text("?"))
        else:
            prompt = (text("Add "), math(str(n)), text(" to itself. What do you get?"))
        wrong = [
            ("gave_the_number", n),
            ("counted_start", 2 * n - 1),
            ("went_one_too_far", 2 * n + 1),
        ]
        step = f"Picture {n} on one side and {n} on the other."
        worked = f"Double {n} is {2 * n}. So the answer is {2 * n}."
    elif tier == 1:
        n = rng.randint(1, 9)
        answer, shown = 2 * n + 1, n
        left, right = (n, n + 1) if rng.choice((True, False)) else (n + 1, n)
        if rng.choice((True, False)):
            prompt = math_prompt(f"{left} + {right} = ?")
        else:
            prompt = (
                text("What is "),
                math(str(left)),
                text(" plus "),
                math(str(right)),
                text("?"),
            )
        wrong = [("doubled_the_smaller", 2 * n), ("doubled_the_bigger", 2 * n + 2)]
        step = f"One of the numbers is {n}. Is there a double close by?"
        worked = f"Double {n} is {2 * n}. One more makes {2 * n + 1}. So the answer is {2 * n + 1}."
    else:
        n = rng.randint(1, 10)
        answer, shown = n, 2 * n
        ask = rng.randrange(3)
        if ask == 0:
            prompt = (text("Both numbers are the same. "), math(f"? + ? = {2 * n}"))
        elif ask == 1:
            prompt = (
                text("Two same numbers make "),
                math(str(2 * n)),
                text(". What is the number?"),
            )
        else:
            prompt = (text("Half of "), math(str(2 * n)), text(" is which number?"))
        wrong = [("gave_the_total", 2 * n), ("doubled_instead", 4 * n)]
        step = "The two parts are the same size. What could one part be?"
        worked = f"{n} and {n} make {2 * n}. So the number is {n}."
    return Built(
        prompt=prompt,
        answer=_Int(answer),
        wrong=named_wrongs(wrong),
        values={"shown": shown, "step": step, "worked": worked, "answer": answer},
    )


# --- equal_or_not -----------------------------------------------------------------------

_EQUAL_LAYOUTS = (
    "{side} = {beside} + ?",
    "{side} = ? + {beside}",
    "{beside} + ? = {side}",
    "? + {beside} = {side}",
)
_EQUAL_LAYOUTS_BY_TIER = (1, 4, 4)


def _build_equal(rng: random.Random, tier: int) -> Built:
    """Make both sides equal: one side is a sum (tiers 0 and 1) or a take-away (tier 2) and
    the other is a number and a blank. ``side`` is what the whole side makes; the blank
    is what ``beside`` needs to match it."""
    side_value = rng.randint(4, 19 if tier == 2 else 20)
    parts: tuple[int, ...]
    if tier == 2 and rng.choice((True, False)):
        y = rng.randint(1, 20 - side_value)
        side, parts = f"{side_value + y} - {y}", (side_value + y, y)
    else:
        left = rng.randint(1, side_value - 1)
        side, parts = f"{left} + {side_value - left}", (left, side_value - left)
    beside = rng.choice([n for n in range(1, side_value) if n not in parts])
    answer = side_value - beside
    layout = _EQUAL_LAYOUTS[rng.randrange(_EQUAL_LAYOUTS_BY_TIER[tier])]
    return Built(
        prompt=math_prompt(layout.format(side=side, beside=beside)),
        answer=_Int(answer),
        wrong=named_wrongs(
            [
                ("gave_the_total", side_value),
                ("copied_a_number", beside),
                ("added_all_the_numbers", sum(parts) + beside),
            ]
        ),
        values={"side": side_value, "beside": beside, "answer": answer},
    )


def generators() -> list[SkillGenerator]:
    form = AnswerForm.INTEGER
    shown_keys = ("added_the_shown", "subtracted_the_shown", "gave_a_shown_number")
    return [
        SkillGenerator(
            "count_on",
            -1.8,
            form,
            _build_count_on,
            ("counted_start", "went_one_too_far", "subtracted_instead"),
        ),
        SkillGenerator(
            "make_ten_strategy",
            -0.9,
            form,
            _build_make_ten,
            (
                "counted_start",
                "subtracted_instead",
                "gave_the_leftover",
                "gave_the_total",
                "gave_the_gap_to_ten",
                "added_instead",
            ),
        ),
        SkillGenerator(
            "add_three_numbers",
            -1.1,
            form,
            _build_add_three,
            ("left_out_the_last", "left_out_the_first", "left_out_the_middle"),
        ),
        SkillGenerator("missing_number_20", -0.9, form, _build_missing_number, shown_keys),
        SkillGenerator(
            "fact_families_20",
            -0.7,
            form,
            _build_fact_family,
            shown_keys,
            first_try_counts=True,
        ),
        SkillGenerator(
            "doubles_near_doubles",
            -1.3,
            form,
            _build_doubles,
            (
                "gave_the_number",
                "counted_start",
                "went_one_too_far",
                "doubled_the_smaller",
                "doubled_the_bigger",
                "gave_the_total",
                "doubled_instead",
            ),
        ),
        SkillGenerator(
            "equal_or_not",
            -1.0,
            form,
            _build_equal,
            ("gave_the_total", "copied_a_number", "added_all_the_numbers"),
        ),
    ]
