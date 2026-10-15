"""Bank items: precooked problems for what generators cannot make.

An item is picked by seed. A ``choice`` item shows its choices shuffled by a random
generator seeded by (seed, item id) and records the index of the right one in the
shown order; the learner answers by index, which is never parsed. An ``expr`` item's
answer is LaTeX read by the engine's own parser, checked like any typed answer.
"""

import dataclasses
import random
from typing import cast

import sympy

from mathquest.engine.checker.latex import parse
from mathquest.engine.checker.sympy_bridge import to_sympy
from mathquest.engine.content.schema import Bank, BankItem, Part
from mathquest.engine.types import MathPart, Problem, Prompt, TextPart


def pick_item(bank: Bank, seed: int) -> BankItem:
    """The item a seed selects."""
    return random.Random(f"{seed}:bank").choice(bank.items)


def find_item(bank: Bank, item_id: str) -> BankItem | None:
    return next((i for i in bank.items if i.id == item_id), None)


def to_prompt(parts: tuple[Part, ...]) -> Prompt:
    return tuple(TextPart(p.value) if p.kind == "text" else MathPart(p.value) for p in parts)


def expr_answer(item: BankItem) -> sympy.Expr:
    """The value of an ``expr`` item's answer, read by the engine's own parser."""
    return cast(sympy.Expr, to_sympy(parse(str(item.answer.value))))


def render_bank(item: BankItem, problem: Problem) -> Problem:
    """``problem`` (for its tier and difficulty) replaced by bank item ``item``."""
    shown = dataclasses.replace(
        problem,
        prompt=to_prompt(item.prompt),
        misconceptions=(),
        values={},
        variant="bank",
        template_id=item.id,
    )
    if item.answer.kind == "expr":
        return dataclasses.replace(shown, answer=expr_answer(item))
    assert item.choices is not None and isinstance(item.answer.value, int)
    order = list(range(len(item.choices)))
    random.Random(f"{problem.seed}:choices:{item.id}").shuffle(order)
    correct = order.index(item.answer.value)
    return dataclasses.replace(
        shown,
        answer=sympy.Integer(correct),
        choices=tuple(to_prompt(item.choices[i]) for i in order),
        correct_choice=correct,
    )
