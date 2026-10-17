# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false
"""Counting generators: say the next, the last and the missing number, and count by tens."""

import random

import sympy

from mathquest.engine.generators._util import Built, SkillGenerator, math, text
from mathquest.engine.types import AnswerForm

_Int = sympy.Integer

_AFTER_ASKS = (
    ("What number comes after ", "?"),
    ("What comes right after ", "?"),
    ("Say the number after ", "."),
)
_BEFORE_ASKS = (
    ("What number comes before ", "?"),
    ("What comes right before ", "?"),
    ("Say the number before ", "."),
)
_COUNTING_KEYS = ("repeated_number", "wrong_direction", "skipped_a_number")
_COUNT_ON_KEYS = ("counted_start", "went_one_too_far")
_COUNTING_FORMS = ("after", "before", "missing", "run", "count_on")


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
    decade_share: float = 1 / 3,
) -> Built:
    """One counting problem whose answer is in ``lo..hi`` and whose numbers stay in
    ``1..cap``. ``decade`` asks for answers on a new ten ``decade_share`` of the time."""
    tens = [n for n in range(lo, hi + 1) if n % 10 == 0]
    answer = (
        rng.choice(tens) if decade and tens and rng.random() < decade_share else rng.randint(lo, hi)
    )
    available = [f for f in forms if _available(f, answer, cap)]
    form = rng.choice(available)
    values: dict[str, int | str] = {"answer": answer, "form": form}
    wrong: list[tuple[str, int]]
    if form == "after":
        n = answer - 1
        asking, end = rng.choice(_AFTER_ASKS)
        prompt = (text(asking), math(str(n)), text(end))
        wrong = [("repeated_number", n), ("wrong_direction", n - 1), ("skipped_a_number", n + 2)]
        if decade and n % 10 == 9:
            wrong.append(("kept_the_tens", n // 10 * 10))
        values["n"] = n
        near, rel, way = n, "one more than", "up"
    elif form == "before":
        n = answer + 1
        asking, end = rng.choice(_BEFORE_ASKS)
        prompt = (text(asking), math(str(n)), text(end))
        wrong = [("repeated_number", n), ("wrong_direction", n + 1), ("skipped_a_number", n - 2)]
        if decade and n % 10 == 0:
            wrong.append(("kept_the_tens", answer + 10))
        values["n"] = n
        near, rel, way = n, "one less than", "back"
    elif form == "missing":
        # Numbers either side of the blank: up to two more before it and two after it.
        before = rng.randint(0, min(2, answer - 2))
        after = rng.randint(0, min(2, cap - answer - 1))
        shown = [str(n) for n in range(answer - 1 - before, answer)]
        shown += ["?", *(str(n) for n in range(answer + 1, answer + 2 + after))]
        prompt = (text("What number is missing? "), math(", ".join(shown)))
        wrong = [("repeated_number", answer - 1), ("skipped_a_number", answer + 1)]
        near, rel, way = answer - 1, "one more than", "up"
    elif form == "run":
        size = min(rng.randint(2, 4), answer - 1)
        run = ", ".join([*(str(n) for n in range(answer - size, answer)), "?"])
        prompt = (text("Count on. What comes next? "), math(run))
        wrong = [("repeated_number", answer - 1), ("skipped_a_number", answer + 1)]
        if decade and answer % 10 == 0:
            wrong.append(("kept_the_tens", answer - 10))
        near, rel, way = answer - 1, "one more than", "up"
    elif form == "count_on":
        more = rng.randint(1, min(5, answer - 1))
        start = answer - more
        prompt = (
            text("Start at "),
            math(str(start)),
            text(". Count on "),
            math(str(more)),
            text(" more number." if more == 1 else " more numbers."),
            text(" Which number do you say last?"),
        )
        wrong = [("counted_start", answer - 1), ("went_one_too_far", answer + 1)]
        values.update({"start": start, "more": more})
        near, rel, way = start, ("one" if more == 1 else str(more)) + " more than", "up"
    else:
        raise ValueError(f"unknown counting form {form}")
    # What every hint can lean on, whatever the form: a number the prompt shows to count
    # from (``near``), how the answer relates to it (``rel``) and which way to count (``dir``).
    values.update({"near": near, "rel": rel, "dir": way})
    return Built(prompt=prompt, answer=_Int(answer), wrong=_wrongs(answer, wrong, 1), values=values)


def _available(form: str, answer: int, cap: int) -> bool:
    if form == "before":
        return answer + 1 <= cap
    if form == "missing":
        return answer >= 2 and answer + 1 <= cap
    return answer >= 2


# The first two tiers are narrow, the rest span the range; difficulty comes from the form of
# the question: after and before, then a missing number or a run, then counting on.
_TEN_ANSWERS = ((1, 6), (2, 10), (2, 10))
_TWENTY_ANSWERS = ((11, 16), (11, 20), (11, 20))
_FORMS_BY_TIER = (
    ("after", "before"),
    ("after", "before", "missing", "run"),
    ("before", "missing", "run", "count_on"),
)
_HUNDRED_ANSWERS = ((21, 50), (51, 100), (11, 100))


def _build_count_to_10(rng: random.Random, tier: int) -> Built:
    lo, hi = _TEN_ANSWERS[tier]
    return _counting(rng, lo, hi, 10, _FORMS_BY_TIER[tier], decade=False)


def _build_count_to_20(rng: random.Random, tier: int) -> Built:
    lo, hi = _TWENTY_ANSWERS[tier]
    return _counting(rng, lo, hi, 20, _FORMS_BY_TIER[tier], decade=True, decade_share=0.2)


def _build_count_to_100(rng: random.Random, tier: int) -> Built:
    lo, hi = _HUNDRED_ANSWERS[tier]
    return _counting(rng, lo, hi, 100, _COUNTING_FORMS, decade=True)


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
    asking = rng.choice(("What is", "What number is", "Find"))
    wrong = [
        ("wrong_direction", n - step),
        ("skipped_a_number", n + 2 * step),
    ]
    if tier >= 1:
        wrong.append(("changed_the_tens", n + 10 * step))
    # Going up past a nine is where the tens digit is forgotten (39 then 30); going down
    # past a ten has no such slip children make often, so it has no mistake of its own.
    if tier == 2 and more and n % 10 == 9:
        wrong.append(("kept_the_tens", n // 10 * 10))
    return Built(
        prompt=(text(f"{asking} 1 {word} than "), math(str(n)), text("?")),
        answer=_Int(answer),
        wrong=_wrongs(answer, wrong, 0),
        values={
            "n": n,
            "answer": answer,
            "direction": word,
            "dir": "up" if more else "back",
        },
    )


def _build_skip_count_10(rng: random.Random, tier: int) -> Built:
    """Tens in a row, counting up or (tiers 0 and 1) back. ``previous`` is the number just
    before the blank; ``tens_way``, ``dir`` and ``jump`` say how the blank follows from it."""
    back = tier < 2 and rng.random() < 0.4
    if tier == 2:
        answer = rng.randint(2, 9) * 10
        places = [i for i in (1, 2, 3) if 10 <= answer - 10 * i <= 60]
        start = answer - 10 * rng.choice(places)
        shown = ["?" if n == answer else str(n) for n in range(start, start + 41, 10)]
        prompt = (
            text(rng.choice(("Fill in the missing ten. ", "Find the missing ten. "))),
            math(", ".join(shown)),
        )
    elif back:
        top = 5 if tier == 0 else 10
        floor = 1 if tier == 0 else 5
        first = rng.randint(floor + 2, top) * 10
        count = rng.randint(2, min(4, first // 10 - floor))
        shown = [str(first - 10 * k) for k in range(count)]
        answer = first - 10 * count
        prompt = (
            text(rng.choice(("Count back by tens. ", "Count down by tens. "))),
            math(", ".join([*shown, "?"])),
        )
    else:
        top = (5, 10)[tier]
        answer = rng.randint(3 if tier == 0 else 6, top) * 10
        first = rng.randint(1, min(4, answer // 10 - 2)) * 10
        shown = [str(n) for n in range(first, answer, 10)]
        asking = ("Count by tens. ", "Count up by tens. ", "Keep counting by tens. ")
        prompt = (text(rng.choice(asking)), math(", ".join([*shown, "?"])))
    step = -10 if back else 10
    wrong = [
        ("counted_by_ones", answer - step + (-1 if back else 1)),
        ("said_the_tens_digit", answer // 10),
        ("skipped_a_ten", answer + step),
    ]
    return Built(
        prompt=prompt,
        answer=_Int(answer),
        wrong=_wrongs(answer, wrong, 1),
        values={
            "answer": answer,
            "previous": answer - step,
            "jump": step,
            "tens_way": "less" if back else "more",
            "dir": "back" if back else "up",
        },
    )


def generators() -> list[SkillGenerator]:
    form = AnswerForm.INTEGER
    return [
        SkillGenerator(
            "count_to_10", -2.6, form, _build_count_to_10, (*_COUNTING_KEYS, *_COUNT_ON_KEYS)
        ),
        SkillGenerator(
            "count_to_20",
            -2.3,
            form,
            _build_count_to_20,
            (*_COUNTING_KEYS, "kept_the_tens", *_COUNT_ON_KEYS),
        ),
        SkillGenerator(
            "count_to_100",
            -1.8,
            form,
            _build_count_to_100,
            (*_COUNTING_KEYS, "kept_the_tens", *_COUNT_ON_KEYS),
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
