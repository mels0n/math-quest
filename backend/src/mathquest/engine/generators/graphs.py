# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false
"""Reading a graph (1.MD.C.4), told as a short table of numerals.

A graph here is three groups, each with how many kids chose it: "Kids chose a pet. Cats: 4.
Dogs: 7. Birds: 3." No picture is needed (counting drawn objects needs one that is not
built), and the numerals are what a bar graph's bars come to. The three counts are different,
so the biggest and the smallest group are each one group. ``a``, ``b`` and ``c`` are the
counts from biggest to smallest.

Tier 0 reads one count (a named group, the biggest or the smallest). Tier 1 compares two
groups. Tier 2 adds groups up.
"""

import random

import sympy

from mathquest.engine.generators._util import Built, SkillGenerator, named_wrongs, text
from mathquest.engine.types import AnswerForm

_Int = sympy.Integer

# What the kids chose, and the groups it can be chosen from (as they read after "chose").
_THEMES = (
    ("a pet", ("cats", "dogs", "birds", "fish", "rabbits")),
    ("a fruit", ("apples", "pears", "plums", "grapes", "peaches")),
    ("a color", ("red", "blue", "green", "yellow", "purple")),
    ("a game", ("tag", "cards", "ball", "puzzles", "chess")),
    ("a snack", ("crackers", "raisins", "popcorn", "cheese", "carrots")),
    ("a story", ("dragons", "robots", "pirates", "ponies", "wizards")),
)
_MOST = 9
_TOTAL = 20


def _counts(rng: random.Random, tier: int) -> tuple[int, int, int]:
    """Three different counts, biggest first. Tier 0 and 1 keep each count small; in tier 2
    the three add to at most 20."""
    while True:
        a, b, c = sorted(
            rng.sample(range(1, _MOST + 4 if tier == 1 else _MOST + 1), 3), reverse=True
        )
        if tier < 2 or a + b + c <= _TOTAL:
            return a, b, c


def _graph(rng: random.Random, tier: int) -> tuple[str, dict[str, int], list[str]]:
    """The graph as words, the count of each group by name, and the groups in the order the
    table lists them."""
    chose, pool = rng.choice(_THEMES)
    names = rng.sample(pool, 3)
    counts = dict(zip(names, _counts(rng, tier), strict=True))
    order = rng.sample(names, 3)
    table = " ".join(f"{name.capitalize()}: {counts[name]}." for name in order)
    return f"Kids chose {chose}. {table} ", counts, order


def _read_one(rng: random.Random, tier: int) -> Built:
    intro, counts, order = _graph(rng, tier)
    name = rng.choice(order)
    answer = counts[name]
    others = [v for k, v in counts.items() if k != name]
    return _wrap(
        f"{intro}How many kids chose {name}?",
        counts,
        answer,
        [("read_a_different_group", others[0]), ("read_a_different_group", others[1])],
        "Find the group the question names. Look at the number beside it.",
        f"The number beside {name} is {answer}.",
    )


def _read_extreme(rng: random.Random, tier: int) -> Built:
    intro, counts, _ = _graph(rng, tier)
    biggest = rng.choice((True, False))
    values = sorted(counts.values(), reverse=True)
    answer = values[0] if biggest else values[2]
    swapped = values[2] if biggest else values[0]
    which = "biggest" if biggest else "smallest"
    return _wrap(
        f"{intro}How many kids are in the {which} group?",
        counts,
        answer,
        [("confused_most_fewest", swapped), ("read_a_different_group", values[1])],
        f"Look at all the numbers. Pick the {which} one.",
        f"The {which} group is the number {answer}.",
    )


def _compare_two(rng: random.Random, tier: int) -> Built:
    intro, counts, _ = _graph(rng, tier)
    ranked = sorted(counts, key=lambda k: -counts[k])
    more_name, less_name = rng.sample(ranked, 2)
    if counts[more_name] < counts[less_name]:
        more_name, less_name = less_name, more_name
    big, small = counts[more_name], counts[less_name]
    fewer = rng.choice((True, False))
    question = (
        f"How many fewer kids chose {less_name} than {more_name}?"
        if fewer
        else f"How many more kids chose {more_name} than {less_name}?"
    )
    return _wrap(
        f"{intro}{question}",
        counts,
        big - small,
        [("added_instead", big + small), ("gave_one_count", big), ("gave_one_count", small)],
        f"Find {more_name} and {less_name}. Say both numbers.",
        f"{more_name.capitalize()}: {big}. {less_name.capitalize()}: {small}. "
        f"Match them up. The gap is {big - small}.",
        told=(big, small),
    )


def _compare_extremes(rng: random.Random, tier: int) -> Built:
    intro, counts, _ = _graph(rng, tier)
    a, _, c = sorted(counts.values(), reverse=True)
    return _wrap(
        f"{intro}How many more kids are in the biggest group than the smallest?",
        counts,
        a - c,
        [("added_instead", a + c), ("gave_one_count", a), ("gave_one_count", c)],
        "Find the biggest group and the smallest group. Say both numbers.",
        f"Biggest: {a}. Smallest: {c}. Match them up. The gap is {a - c}.",
        told=(a, c),
    )


def _total_all(rng: random.Random, tier: int) -> Built:
    intro, counts, _ = _graph(rng, tier)
    a, b, c = sorted(counts.values(), reverse=True)
    total = a + b + c
    return _wrap(
        f"{intro}How many kids are there in all?",
        counts,
        total,
        [("left_out_a_group", total - c), ("subtracted_instead", a - b - c)],
        "Look at every group in the graph. Do not leave one out.",
        f"The groups are {a}, {b} and {c}. Together that is {total}.",
        told=(a, b),
    )


def _total_two(rng: random.Random, tier: int) -> Built:
    intro, counts, order = _graph(rng, tier)
    first, second = rng.sample(order, 2)
    x, y = counts[first], counts[second]
    return _wrap(
        f"{intro}How many kids chose {first} or {second}?",
        counts,
        x + y,
        [("subtracted_instead", abs(x - y)), ("gave_one_count", max(x, y))],
        f"Find {first} and {second}. Say both numbers.",
        f"{first.capitalize()}: {x}. {second.capitalize()}: {y}. Together that is {x + y}.",
        told=(x, y),
    )


def _wrap(
    prompt: str,
    counts: dict[str, int],
    answer: int,
    wrong: list[tuple[str, int]],
    step: str,
    worked: str,
    told: tuple[int, int] | None = None,
) -> Built:
    a, b, c = sorted(counts.values(), reverse=True)
    first, second = told if told is not None else (a, b)
    return Built(
        prompt=(text(prompt),),
        answer=_Int(answer),
        wrong=named_wrongs(wrong),
        values={
            "a": a,
            "b": b,
            "c": c,
            "told1": first,
            "told2": second,
            "answer": answer,
            "step": step,
            "worked": worked,
        },
    )


_FORMS = (
    (_read_one, _read_one, _read_extreme),
    (_compare_two, _compare_two, _compare_extremes),
    (_total_all, _total_two),
)


def _build_graph(rng: random.Random, tier: int) -> Built:
    return rng.choice(_FORMS[tier])(rng, tier)


def generators() -> list[SkillGenerator]:
    return [
        SkillGenerator(
            "read_data_graphs",
            -0.9,
            AnswerForm.INTEGER,
            _build_graph,
            (
                "read_a_different_group",
                "confused_most_fewest",
                "added_instead",
                "gave_one_count",
                "left_out_a_group",
                "subtracted_instead",
            ),
            first_try_counts=True,
        )
    ]
