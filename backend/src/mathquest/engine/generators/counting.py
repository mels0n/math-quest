# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false
"""Counting generators: say the next, the last and the missing number, and count by tens."""

import random

import sympy

from mathquest.engine.generators._util import Built, SkillGenerator, math, text
from mathquest.engine.types import AnswerForm

_Int = sympy.Integer

_COUNTING_KEYS = ("repeated_number", "wrong_direction", "skipped_a_number")
_COUNTING_FORMS = ("after", "before", "missing", "run")


def _wrongs(
    answer: int, pairs: list[tuple[str, int]], floor: int
) -> tuple[tuple[str, sympy.Expr], ...]:
    """The named wrong answers a child could type: at least ``floor``, never the answer."""
    return tuple((key, _Int(value)) for key, value in pairs if value >= floor and value != answer)


def _counting(
    rng: random.Random,
    lo: int,
    hi: int,
    cap: int,
    forms: tuple[str, ...],
    decade: bool,
) -> Built:
    """One counting problem whose answer is in ``lo..hi`` and whose numbers stay in
    ``1..cap``. ``decade`` asks for answers on a new ten about a third of the time."""
    tens = [n for n in range(lo, hi + 1) if n % 10 == 0]
    answer = rng.choice(tens) if decade and tens and rng.random() < 1 / 3 else rng.randint(lo, hi)
    available = [f for f in forms if _available(f, answer, cap)]
    form = rng.choice(available)
    values: dict[str, int | str] = {"answer": answer, "form": form}
    wrong: list[tuple[str, int]]
    if form == "after":
        n = answer - 1
        prompt = (text("What number comes after "), math(str(n)), text("?"))
        wrong = [("repeated_number", n), ("wrong_direction", n - 1), ("skipped_a_number", n + 2)]
        if decade and n % 10 == 9:
            wrong.append(("kept_the_tens", n // 10 * 10))
        values["n"] = n
    elif form == "before":
        n = answer + 1
        prompt = (text("What number comes before "), math(str(n)), text("?"))
        wrong = [("repeated_number", n), ("wrong_direction", n + 1), ("skipped_a_number", n - 2)]
        if decade and n % 10 == 0:
            wrong.append(("kept_the_tens", answer + 10))
        values["n"] = n
    elif form == "missing":
        lead = answer - 2 >= 1
        trail = answer + 2 <= cap
        use_lead = rng.choice((True, False)) if lead and trail else lead
        shown = [answer - 2, answer - 1, 0, answer + 1] if use_lead else [answer - 1, 0, answer + 1]
        if not use_lead and trail:
            shown.append(answer + 2)
        run = ", ".join("?" if n == 0 else str(n) for n in shown)
        prompt = (text("What number is missing? "), math(run))
        wrong = [("repeated_number", answer - 1), ("skipped_a_number", answer + 1)]
    elif form == "run":
        size = min(3, answer - 1)
        run = ", ".join([*(str(n) for n in range(answer - size, answer)), "?"])
        prompt = (text("Count on. What comes next? "), math(run))
        wrong = [("repeated_number", answer - 1), ("skipped_a_number", answer + 1)]
        if decade and answer % 10 == 0:
            wrong.append(("kept_the_tens", answer - 10))
    else:
        more = rng.randint(2, min(5, answer - 2))
        start = answer - more
        prompt = (
            text("Start at "),
            math(str(start)),
            text(". Count on "),
            math(str(more)),
            text(" more numbers. Which number do you say last?"),
        )
        wrong = [("counted_start", answer - 1), ("went_one_too_far", answer + 1)]
        values.update({"start": start, "more": more})
    return Built(prompt=prompt, answer=_Int(answer), wrong=_wrongs(answer, wrong, 1), values=values)


def _available(form: str, answer: int, cap: int) -> bool:
    if form == "before":
        return answer + 1 <= cap
    if form == "missing":
        return answer >= 2 and answer + 1 <= cap
    if form == "count_on":
        return answer >= 4
    return answer >= 2


_TEN_ANSWERS = ((1, 5), (6, 8), (9, 10))
_TWENTY_ANSWERS = ((11, 14), (15, 17), (18, 20))
_HUNDRED_ANSWERS = ((21, 50), (51, 100), (11, 100))


def _build_count_to_10(rng: random.Random, tier: int) -> Built:
    lo, hi = _TEN_ANSWERS[tier]
    return _counting(rng, lo, hi, 10, _COUNTING_FORMS, decade=False)


def _build_count_to_20(rng: random.Random, tier: int) -> Built:
    lo, hi = _TWENTY_ANSWERS[tier]
    return _counting(rng, lo, hi, 20, _COUNTING_FORMS, decade=True)


def _build_count_to_100(rng: random.Random, tier: int) -> Built:
    lo, hi = _HUNDRED_ANSWERS[tier]
    forms = (*_COUNTING_FORMS, "count_on", "count_on") if tier == 2 else _COUNTING_FORMS
    return _counting(rng, lo, hi, 100, forms, decade=True)


def _build_one_more_one_less(rng: random.Random, tier: int) -> Built:
    """``n`` is the number shown; "1 more" or "1 less" than it is the answer."""
    lo, hi = ((1, 10), (10, 20), (20, 100))[tier]
    more = rng.choice((True, False))
    step = 1 if more else -1
    if tier == 2:
        # A new ten is where "1 more" and "1 less" go wrong most: 39 and 40.
        edge = [n for n in range(lo, hi) if (n + 1 if more else n) % 10 == 0 and n + step <= hi]
        if rng.random() < 0.4:
            n = rng.choice(edge)
        else:
            n = rng.randint(lo if more else lo + 1, hi - 1 if more else hi)
    else:
        n = rng.randint(lo if more else lo + 1, hi - 1 if more else hi)
    answer = n + step
    word = "more" if more else "less"
    wrong = [
        ("wrong_direction", n - step),
        ("skipped_a_number", n + 2 * step),
    ]
    if tier >= 1:
        wrong.append(("changed_the_tens", n + 10 * step))
    if tier == 2 and n % 10 == (9 if more else 0):
        wrong.append(("kept_the_tens", n // 10 * 10 if more else n + 9))
    return Built(
        prompt=(text(f"What is 1 {word} than "), math(str(n)), text("?")),
        answer=_Int(answer),
        wrong=_wrongs(answer, wrong, 0),
        values={"n": n, "answer": answer, "direction": word},
    )


def _build_skip_count_10(rng: random.Random, tier: int) -> Built:
    """Tens in a row. ``last`` is the number just before the blank when it is the end."""
    if tier == 0:
        answer = rng.randint(3, 5) * 10
        shown = [str(n) for n in range(10, answer, 10)]
        prompt = (text("Count by tens. "), math(", ".join([*shown, "?"])))
    elif tier == 1:
        answer = rng.randint(6, 10) * 10
        first = rng.randint(1, min(3, answer // 10 - 2)) * 10
        shown = [str(n) for n in range(first, answer, 10)]
        prompt = (text("Count by tens. "), math(", ".join([*shown, "?"])))
    else:
        answer = rng.randint(2, 9) * 10
        places = [i for i in (1, 2, 3) if 10 <= answer - 10 * i <= 60]
        start = answer - 10 * rng.choice(places)
        shown = ["?" if n == answer else str(n) for n in range(start, start + 41, 10)]
        prompt = (text("Fill in the missing ten. "), math(", ".join(shown)))
    wrong = [
        ("counted_by_ones", answer - 9),
        ("said_the_tens_digit", answer // 10),
        ("skipped_a_ten", answer + 10),
    ]
    return Built(
        prompt=prompt,
        answer=_Int(answer),
        wrong=_wrongs(answer, wrong, 1),
        values={"answer": answer, "previous": answer - 10},
    )


def generators() -> list[SkillGenerator]:
    form = AnswerForm.INTEGER
    return [
        SkillGenerator("count_to_10", -2.6, form, _build_count_to_10, _COUNTING_KEYS),
        SkillGenerator(
            "count_to_20",
            -2.3,
            form,
            _build_count_to_20,
            (*_COUNTING_KEYS, "kept_the_tens"),
        ),
        SkillGenerator(
            "count_to_100",
            -1.8,
            form,
            _build_count_to_100,
            (*_COUNTING_KEYS, "kept_the_tens", "counted_start", "went_one_too_far"),
        ),
        SkillGenerator(
            "one_more_one_less",
            -1.9,
            form,
            _build_one_more_one_less,
            ("wrong_direction", "skipped_a_number", "changed_the_tens", "kept_the_tens"),
        ),
        SkillGenerator(
            "skip_count_10",
            -1.6,
            form,
            _build_skip_count_10,
            ("counted_by_ones", "said_the_tens_digit", "skipped_a_ten"),
        ),
    ]
