"""What the groups skills and the times tables share: the named mistakes for ``g`` groups of
``s`` and the forms a multiplication question is asked in (ADR-0029, ADR-0030)."""

from mathquest.engine.generators._util import math, math_prompt, text
from mathquest.engine.types import Prompt

GROUP_KEYS = ("added_instead", "one_group_too_few", "one_group_too_many")
"""The mistakes for ``g`` groups of ``s`` that change the answer by the group size."""
EACH_KEYS = ("one_each_too_few", "one_each_too_many")
"""The mistakes of a neighbouring fact: the answer changed by the number of groups."""


def group_wrongs(g: int, s: int) -> list[tuple[str, int]]:
    """What a child types for ``g`` groups of ``s``: the two numbers added, or one group left
    out or counted twice."""
    total = g * s
    return list(zip(GROUP_KEYS, (g + s, total - s, total + s), strict=True))


def each_wrongs(g: int, s: int) -> list[tuple[str, int]]:
    """What a child types for the fact next door to ``g`` times ``s``: one less or one more
    in every group."""
    total = g * s
    return list(zip(EACH_KEYS, (total - g, total + g), strict=True))


def group_prompt(form: str, g: int, s: int) -> Prompt:
    """``g`` groups of ``s`` asked as a ``sentence``, in ``words`` ("What is"), as
    ``groups_of`` or in ``times`` words."""
    if form == "sentence":
        return math_prompt(rf"{g} \times {s} = ?")
    if form == "words":
        return (text("What is "), math(rf"{g} \times {s}"), text("?"))
    if form == "groups_of":
        return (text(f"There are {g} groups of {s}. How many are there in all?"),)
    return (text(f"What is {g} times {s}?"),)
