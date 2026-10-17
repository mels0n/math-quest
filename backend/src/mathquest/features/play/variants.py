"""How each issued problem is presented: bare, as a word problem, or from the bank.

The choice is a seeded draw, so the stored seed alone decides it: a draw ``u`` in
[0, 1) from a random generator seeded by the problem seed gives ``bank`` when
``u < bank_share``, ``word`` when ``u < bank_share + word_share``, else ``bare``. A
share only counts when the skill has that content (bank items for the problem's tier, word
templates), so a skill without any keeps every problem bare.
"""

import random

from mathquest.engine.bank import items_for_tier
from mathquest.engine.catalog import SkillSource
from mathquest.engine.types import Variant


def choose_variant(source: SkillSource, seed: int, tier: int | None = None) -> Variant:
    skill = source.skill
    has_bank = source.bank is not None and (tier is None or bool(items_for_tier(source.bank, tier)))
    bank_share = skill.bank_share if has_bank else 0.0
    word_share = skill.word_share if source.word_problems is not None else 0.0
    draw = random.Random(f"{seed}:variant").random()
    if draw < bank_share:
        return "bank"
    if draw < bank_share + word_share:
        return "word"
    return "bare"
