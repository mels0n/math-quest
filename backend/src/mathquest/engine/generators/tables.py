# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false
"""The times tables 2 to 9 (3.OA.C.7), four skills of two tables each.

A fact is a table times another number from 2 to 10, written either way round
(``7 \times 6`` and ``6 \times 7``). Times 0, 1 and 10 are ``mult_0_1_10``, so they come
up here only as the other number. Tier 0 is the first table of the pair, tier 1 the second
and tier 2 both mixed (ADR-0030). The tiers also get harder through the form of the
question: a sentence or "What is", then "groups of", then "times" in words.

A question has two numbers underneath, ``g`` and ``s`` (``g`` groups of ``s``), as in
``mult_as_groups``, so a word template shows every number the generator holds. The hints
come from the generator, because each table has its own strategy: doubling for the 2s, 4s
and 8s, the fives and tens facts for 5s, 6s, 7s and 9s.
"""

import random
from collections.abc import Callable

import sympy

from mathquest.engine.generators._groups import (
    EACH_KEYS,
    GROUP_KEYS,
    each_wrongs,
    group_prompt,
    group_wrongs,
)
from mathquest.engine.generators._util import Built, SkillGenerator, named_wrongs
from mathquest.engine.types import AnswerForm

_Int = sympy.Integer

_OTHER = tuple(range(2, 11))
"""The number a table is multiplied by. 0 and 1 belong to ``mult_0_1_10``."""

_TABLES = {"mult_2_5": (2, 5), "mult_3_4": (3, 4), "mult_6_7": (6, 7), "mult_8_9": (8, 9)}
_BASE = {"mult_2_5": 1.0, "mult_3_4": 1.3, "mult_6_7": 1.6, "mult_8_9": 1.9}

# Per table: a nudge, the next step and the finish, each a function of the other number.
# Only the finish names the answer. No number is ever the first word of a sentence.
_Help = tuple[str, Callable[[int], str], Callable[[int], str]]
_HELP: dict[int, _Help] = {
    2: (
        "Two groups make a double. Add the number to itself.",
        lambda n: f"Add {n} and {n}. That is a double.",
        lambda n: f"Add {n} and {n} to get {2 * n}.",
    ),
    3: (
        "Three groups are a double and one more. Start with the double.",
        lambda n: f"Double {n} to get {2 * n}. Then add {n} once more.",
        lambda n: f"Add {n} to {2 * n} to get {3 * n}.",
    ),
    4: (
        "Four is double, double. Double the number, then double again.",
        lambda n: f"Double {n} to get {2 * n}. Now double that.",
        lambda n: f"Double {2 * n} to get {4 * n}.",
    ),
    5: (
        "Count by fives, or use tens. Five is half of ten.",
        lambda n: f"Ten times {n} is {10 * n}. Five times is half of that.",
        lambda n: f"Half of {10 * n} is {5 * n}.",
    ),
    6: (
        "Six is five and one more. Use the fives you know.",
        lambda n: f"Five times {n} is {5 * n}. You need one more group of {n}.",
        lambda n: f"Add {n} to {5 * n} to get {6 * n}.",
    ),
    7: (
        "Seven is five and two more. Use the fives you know.",
        lambda n: f"Five times {n} is {5 * n}. Two times {n} is {2 * n}.",
        lambda n: f"Add {5 * n} and {2 * n} to get {7 * n}.",
    ),
    8: (
        "Eight is double, double, double. Keep on doubling.",
        lambda n: f"Double {n} to get {2 * n}. Double again to get {4 * n}.",
        lambda n: f"Double {4 * n} once more to get {8 * n}.",
    ),
    9: (
        "Nine is one less than ten. Use the tens you know.",
        lambda n: f"Ten times {n} is {10 * n}. Now take away one group of {n}.",
        lambda n: f"Take {n} from {10 * n} to get {9 * n}.",
    ),
}

_FORMS_BY_TIER = (
    ("sentence", "words"),
    ("sentence", "words", "groups_of"),
    ("sentence", "words", "groups_of", "times"),
)


def _swapped(total: int) -> int:
    """The two digits of a two-digit answer the wrong way round (63 as 36), else 0."""
    if not 10 <= total <= 99 or total % 10 == 0:
        return 0
    return int(str(total)[::-1])


def _builder(skill: str) -> Callable[[random.Random, int], Built]:
    first, second = _TABLES[skill]

    def build(rng: random.Random, tier: int) -> Built:
        table = rng.choice((first, second)) if tier == 2 else (first, second)[tier]
        other = rng.choice(_OTHER)
        g, s = (table, other) if rng.random() < 0.5 else (other, table)
        total = g * s
        nudge, step, finish = _HELP[table]
        wrong = [*group_wrongs(g, s), *each_wrongs(g, s)]
        if skill == "mult_8_9" and 9 in (g, s):
            wrong.append(("digits_swapped", _swapped(total)))
        return Built(
            prompt=group_prompt(rng.choice(_FORMS_BY_TIER[tier]), g, s),
            answer=_Int(total),
            wrong=named_wrongs(wrong, floor=1),
            values={
                "g": g,
                "s": s,
                "nudge": nudge,
                "step": step(other),
                "finish": finish(other),
            },
        )

    return build


_KEYS = (*GROUP_KEYS, *EACH_KEYS)


def generators() -> list[SkillGenerator]:
    return [
        SkillGenerator(
            skill,
            _BASE[skill],
            AnswerForm.INTEGER,
            _builder(skill),
            (*_KEYS, "digits_swapped") if skill == "mult_8_9" else _KEYS,
        )
        for skill in _TABLES
    ]
