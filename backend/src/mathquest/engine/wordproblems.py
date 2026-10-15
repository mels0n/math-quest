"""Word problems: a generated problem retold through a content template.

A template is picked by seed, its slots are filled from the shared slot lists with a
random generator seeded by (seed, template id), and its text is rendered with the
generator's values plus the filled slots. Slots of one kind never repeat within a
problem, so two different name slots always get two different names. A ``number``
slot is a whole number from 2 to 9 for incidental quantities.

The answer stays the generator's answer, with its misconceptions. A template with
``answer_from: expression`` instead computes its answer from ``expression`` over the
generator's values and number slots; the generator's misconceptions describe a
different answer and are dropped.
"""

import dataclasses
import random
from collections.abc import Mapping

from mathquest.engine.content.schema import Slots, SlotType, WordProblems, WordTemplate
from mathquest.engine.templates import TemplateError, Value, evaluate, render
from mathquest.engine.types import Problem

NUMBER_SLOT_RANGE = (2, 9)


def pick_template(word_problems: WordProblems, seed: int) -> WordTemplate:
    """The template a seed selects."""
    return random.Random(f"{seed}:word").choice(word_problems.templates)


def find_template(word_problems: WordProblems, template_id: str) -> WordTemplate | None:
    return next((t for t in word_problems.templates if t.id == template_id), None)


def fill_slots(
    declared: Mapping[str, SlotType], lists: Slots, rng: random.Random
) -> dict[str, Value]:
    """Fill each declared slot; slots of one kind get distinct entries."""
    pools: dict[SlotType, tuple[Value, ...]] = {
        "names": lists.names,
        "objects": lists.objects,
        "units": lists.units,
        "contexts": lists.contexts,
    }
    filled: dict[str, Value] = {}
    for kind in ("names", "objects", "units", "contexts", "number"):
        slots = sorted(name for name, k in declared.items() if k == kind)
        if not slots:
            continue
        if kind == "number":
            for name in slots:
                filled[name] = rng.randint(*NUMBER_SLOT_RANGE)
            continue
        pool = pools[kind]
        if len(slots) > len(pool):
            raise TemplateError(f"{len(slots)} {kind} slots but only {len(pool)} entries")
        filled.update(zip(slots, rng.sample(pool, len(slots)), strict=True))
    return filled


def render_word(template: WordTemplate, problem: Problem, lists: Slots) -> Problem:
    """``problem`` retold as ``template``."""
    rng = random.Random(f"{problem.seed}:slots:{template.id}")
    slots = fill_slots(template.slots, lists, rng)
    clash = sorted(set(slots) & set(problem.values))
    if clash:
        raise TemplateError(f"slot names clash with generator values: {', '.join(clash)}")
    values: dict[str, Value] = {**problem.values, **slots}
    prompt = render(template.text_template, values)
    answer, misconceptions = problem.answer, problem.misconceptions
    if template.expression is not None:
        numbers = {k: v for k, v in values.items() if isinstance(v, int)}
        answer, misconceptions = evaluate(template.expression, numbers), ()
    return dataclasses.replace(
        problem,
        prompt=prompt,
        answer=answer,
        misconceptions=misconceptions,
        variant="word",
        template_id=template.id,
    )
