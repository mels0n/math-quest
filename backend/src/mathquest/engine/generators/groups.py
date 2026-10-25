# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false
"""Equal groups, arrays and the first multiplying (2.OA.C.4, 3.OA.A.1, 3.OA.A.3, 3.OA.C.7).

The questions are told in words and numerals, because a prompt cannot carry a picture
(ADR-0029). Every question has the same two numbers underneath, named for what they count:

- ``equal_groups`` (grade 2): ``g`` groups of ``s`` things. The total is found by adding
  the group again and again or by skip counting, and the times sign is not used. A tier
  narrows the group sizes (groups of 2, then of 3, 4 or 5); the top tier mixes sizes (and 10)
  and sometimes gives the repeated addition as a sum.
- ``arrays`` (grade 2): ``r`` rows of ``c``. The tiers get harder by form: rows of, rows and
  columns, then an array that gains or loses a row.
- ``mult_as_groups`` (grade 3): the same groups, now written with the times sign, in a
  story, as "groups of" and as ``g \\times s``. A tier raises the number of groups.
- ``mult_0_1_10`` (grade 3): a number times 0, 1 or 10, in either order.

The two skills that tell stories (``equal_groups`` and ``mult_as_groups``) give only ``g`` and
``s`` as numbers, so that a word template shows every number the generator holds.
"""

import random

import sympy

from mathquest.engine.generators._groups import GROUP_KEYS, group_prompt, group_wrongs
from mathquest.engine.generators._util import (
    NAMES,
    Built,
    SkillGenerator,
    math,
    math_prompt,
    named_wrongs,
    text,
)
from mathquest.engine.types import AnswerForm, Prompt

_Int = sympy.Integer

# (one, many, what it holds, whether a person can own it): a container and the plural of what an
# equal group of it holds. Every count a story draws is at least 2, so the plurals always agree.
# A table holds kids but nobody has tables of kids, so it is only ever told with "There are".
_CONTAINERS = (
    ("bag", "bags", "apples", True),
    ("box", "boxes", "crayons", True),
    ("plate", "plates", "cookies", True),
    ("basket", "baskets", "eggs", True),
    ("jar", "jars", "marbles", True),
    ("vase", "vases", "flowers", True),
    ("tray", "trays", "muffins", True),
    ("shelf", "shelves", "books", True),
    ("pot", "pots", "seeds", True),
    ("bucket", "buckets", "shells", True),
    ("pack", "packs", "stickers", True),
    ("table", "tables", "kids", False),
)
_STORY_NAMES = NAMES[:4]
"""A few names, picked by the numbers, so that a tier's questions can all be listed."""
_ROW_THINGS = (
    "chairs",
    "desks",
    "plants",
    "tiles",
    "stickers",
    "cupcakes",
    "books",
    "buttons",
    "seeds",
    "stones",
    "cards",
    "blocks",
)


def _groups_story(rng: random.Random, g: int, s: int) -> tuple[Prompt, dict[str, int | str]]:
    """``g`` equal groups of ``s``, told in words, and the nouns it used."""
    one, many, items, owned = rng.choice(_CONTAINERS)
    who = _STORY_NAMES[g * s % len(_STORY_NAMES)]
    tells = [
        f"There are {g} {many}. Each {one} has {s} {items}. How many {items} are there in all?"
    ]
    if owned:
        tells.append(
            f"{who} has {g} {many}. Each {one} holds {s} {items}. How many {items} does {who} have?"
        )
    return (text(rng.choice(tells)),), {"group": one, "groups": many, "items": items}


# --- equal groups ----------------------------------------------------------------------------

_GROUPS_BY_TIER = (
    ((2,), tuple(range(2, 10))),
    ((3, 4, 5), tuple(range(2, 7))),
    ((2, 3, 4, 5, 10), tuple(range(2, 9))),
)
"""Per tier: the sizes of a group, and how many groups there are."""
_SUM_SHARE = 0.3
"""How often the top tier of equal groups gives the repeated addition itself."""


def _build_equal_groups(rng: random.Random, tier: int) -> Built:
    sizes, counts = _GROUPS_BY_TIER[tier]
    s, g = rng.choice(sizes), rng.choice(counts)
    story, nouns = _groups_story(rng, g, s)
    as_sum = tier == 2 and rng.random() < _SUM_SHARE
    prompt: Prompt = math_prompt(" + ".join([str(s)] * g) + " = ?") if as_sum else story
    return Built(
        prompt=prompt,
        answer=_Int(g * s),
        wrong=named_wrongs(group_wrongs(g, s), floor=1),
        values={"g": g, "s": s, **nouns},
    )


# --- arrays ----------------------------------------------------------------------------------

_RANGE = tuple(range(2, 6))
_ARRAY_NUDGE = (
    "Picture the rows. Every row has the same number.",
    "Picture the rows and the columns. Each row has one for every column.",
    "First find how many rows there are after the change.",
)


def _build_arrays(rng: random.Random, tier: int) -> Built:
    things = rng.choice(_ROW_THINGS)
    who = rng.choice(NAMES)
    if tier < 2:
        r, c = rng.choice(_RANGE), rng.choice(_RANGE)
        if tier == 0:
            prompt = (
                text(
                    rng.choice(
                        (
                            f"{things.capitalize()} are in {r} rows of {c}. "
                            f"How many {things} are there?",
                            f"{who} puts {things} in {r} rows. Each row has {c}. "
                            f"How many {things} are there?",
                        )
                    )
                ),
            )
        else:
            prompt = (
                text(
                    rng.choice(
                        (
                            f"{things.capitalize()} are lined up in {r} rows and {c} columns. "
                            f"How many {things} are there?",
                            f"{who} sets out {things} in {r} rows and {c} columns. "
                            f"How many {things} does {who} set out?",
                        )
                    )
                ),
            )
        total = r * c
        wrong = [
            ("added_rows_and_columns", r + c),
            ("counted_one_row", c),
            ("one_row_short", total - c),
        ]
        return Built(
            prompt=prompt,
            answer=_Int(total),
            wrong=named_wrongs(wrong, floor=1),
            values={
                "r": r,
                "c": c,
                "rows": r,
                "total": total,
                "answer": total,
                "things": things,
                "nudge": _ARRAY_NUDGE[tier],
                "rows_are": "There are",
                "change": "changes",
            },
        )
    adds = rng.random() < 0.5
    r = rng.choice((2, 3, 4)) if adds else rng.choice((3, 4, 5))
    c = rng.choice(_RANGE)
    now = r + 1 if adds else r - 1
    start = f"{who} sets out {things} in {r} rows of {c}."
    ask = (
        f"Then {who} adds one more row. How many {things} are there now?"
        if adds
        else f"Then {who} takes away one row. How many {things} are left?"
    )
    wrong = [
        ("forgot_the_change", r * c),
        ("changed_the_total_by_one", r * c + 1 if adds else r * c - 1),
        ("wrong_direction", (r - 1 if adds else r + 1) * c),
    ]
    return Built(
        prompt=(text(f"{start} {ask}"),),
        answer=_Int(now * c),
        wrong=named_wrongs(wrong, floor=1),
        values={
            "r": r,
            "c": c,
            "now": now,
            "rows": now,
            "nudge": _ARRAY_NUDGE[2],
            "rows_are": "Now there are",
            "total": r * c,
            "answer": now * c,
            "things": things,
            "change": "adds" if adds else "takes away",
            "more": "one more row" if adds else "one row fewer",
        },
    )


# --- multiplying groups ----------------------------------------------------------------------

_TIMES_BY_TIER = (
    ((2,), tuple(range(2, 10))),
    (tuple(range(2, 6)), tuple(range(2, 9))),
    (tuple(range(3, 11)), tuple(range(2, 7))),
)
"""Per tier: how many groups there are, and the size of a group."""


def _times_prompt(rng: random.Random, tier: int, g: int, s: int, story: Prompt) -> Prompt:
    form = rng.choice(("story", "groups_of") if tier == 0 else ("story", "groups_of", "sentence"))
    if form == "story":
        return story
    if form == "sentence":
        form = rng.choice(("sentence", "words"))
    return group_prompt(form, g, s)


def _build_mult_as_groups(rng: random.Random, tier: int) -> Built:
    counts, sizes = _TIMES_BY_TIER[tier]
    g, s = rng.choice(counts), rng.choice(sizes)
    story, nouns = _groups_story(rng, g, s)
    return Built(
        prompt=_times_prompt(rng, tier, g, s, story),
        answer=_Int(g * s),
        wrong=named_wrongs(group_wrongs(g, s), floor=1),
        values={"g": g, "s": s, **nouns},
    )


# --- times 0, 1 and 10 -----------------------------------------------------------------------

_KINDS = ("zero", "one", "ten")
_KIND_WEIGHTS = ((0.25, 0.75, 0.0), (0.0, 0.0, 1.0), (0.2, 0.3, 0.5))
"""Per tier: how often the question is a times 0, a times 1 or a times 10 fact. Times 0 is
a fifth to a quarter of the draws, so that no one answer (0) is a third of them."""
_SPECIAL = {"zero": 0, "one": 1, "ten": 10}
_HELP = {
    "zero": (
        "Picture the groups. Is anything inside them?",
        "Find the zero in the fact. Does it count the groups, or what is in each?",
        "Zero groups hold nothing. Groups of zero hold nothing too.",
    ),
    "one": (
        "Picture the groups. How many are in each group?",
        "Find the 1 in the fact. Does it count the groups, or what is in each?",
        "One group of a number is just that number. Groups of one count one each.",
    ),
    "ten": (
        "Think about tens. One group of ten is 10.",
        "Find the 10 in the fact. It is ten groups, or groups of ten.",
        "Ten groups of a number end in a zero. So does a number of tens. "
        "Write the number, then a zero.",
    ),
}
"""Per kind of fact: a nudge, a step and the rule, true whichever factor is the special one.
Only the rule says what the product is, and it is the last hint."""


def _groups_line(a: int, b: int) -> str:
    return f"There is 1 group of {b}." if a == 1 else f"There are {a} groups of {b}."


def _build_zero_one_ten(rng: random.Random, tier: int) -> Built:
    kind = rng.choices(_KINDS, weights=_KIND_WEIGHTS[tier])[0]
    special, n = _SPECIAL[kind], rng.randint(2, 10)
    a, b = (n, special) if rng.random() < 0.5 else (special, n)
    forms = ("sentence", "words") if tier == 0 else ("sentence", "words", "groups")
    form = rng.choice(forms)
    if form == "sentence":
        prompt = math_prompt(rf"{a} \times {b} = ?")
    elif form == "words":
        prompt = (text("What is "), math(rf"{a} \times {b}"), text("?"))
    else:
        prompt = (text(f"{_groups_line(a, b)} How many are there in all?"),)
    answer = n * special
    wrong = {
        "zero": [("answered_the_other_number", n)],
        "one": [("added_one", n + 1), ("answered_zero", 0)],
        "ten": [("dropped_the_zero", n), ("put_on_two_zeros", n * 100), ("added_ten", n + 10)],
    }[kind]
    nudge, step, rule = _HELP[kind]
    return Built(
        prompt=prompt,
        answer=_Int(answer),
        wrong=named_wrongs(wrong),
        values={
            "a": a,
            "b": b,
            "n": n,
            "kind": kind,
            "answer": answer,
            "nudge": nudge,
            "step": step,
            "rule": rule,
        },
    )


def generators() -> list[SkillGenerator]:
    form = AnswerForm.INTEGER
    return [
        SkillGenerator(
            "equal_groups",
            0.3,
            form,
            _build_equal_groups,
            GROUP_KEYS,
        ),
        SkillGenerator(
            "arrays",
            0.4,
            form,
            _build_arrays,
            (
                "added_rows_and_columns",
                "counted_one_row",
                "one_row_short",
                "forgot_the_change",
                "changed_the_total_by_one",
                "wrong_direction",
            ),
        ),
        SkillGenerator(
            "mult_as_groups",
            0.8,
            form,
            _build_mult_as_groups,
            GROUP_KEYS,
        ),
        SkillGenerator(
            "mult_0_1_10",
            0.9,
            form,
            _build_zero_one_ten,
            (
                "answered_the_other_number",
                "added_one",
                "answered_zero",
                "dropped_the_zero",
                "put_on_two_zeros",
                "added_ten",
            ),
        ),
    ]
