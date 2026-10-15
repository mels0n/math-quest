# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false
"""Word-problem and bank variants of every skill that has them.

Runs over the real pack and the test fixture pack: every word template of every skill,
for SEEDS seeds at each tier, renders with no unfilled slot and an answer that
recomputes; every bank item verifies.
"""

import random
import re
from pathlib import Path

import pytest
import sympy

from mathquest.engine.bank import expr_answer
from mathquest.engine.catalog import Catalog, SkillSource, build_catalog, load_catalog
from mathquest.engine.checker.check import Verdict, check, check_choice
from mathquest.engine.content import load_pack
from mathquest.engine.content.schema import WordTemplate
from mathquest.engine.templates import evaluate, plain
from mathquest.engine.types import MathPart, Problem, TextPart
from mathquest.engine.wordproblems import fill_slots

BACKEND = Path(__file__).resolve().parents[2]
REAL = load_catalog(BACKEND / "content", "k8-core")
FIXTURE = build_catalog(
    load_pack(BACKEND / "tests" / "fixtures" / "packs" / "test-pack"), REAL.slots
)
CATALOGS = {"k8-core": REAL, "test-pack": FIXTURE}
SEEDS = 200
_SLOT_LEFT = re.compile(r"\{[A-Za-z_][A-Za-z0-9_]*(\.one)?\}|\{\{=")


def _cases(kind: str) -> list[tuple[str, str, str]]:
    out: list[tuple[str, str, str]] = []
    for pack_id, catalog in CATALOGS.items():
        for sid, source in catalog.sources.items():
            if kind == "word" and source.word_problems is not None:
                out += [(pack_id, sid, t.id) for t in source.word_problems.templates]
            if kind == "bank" and source.bank is not None:
                out += [(pack_id, sid, i.id) for i in source.bank.items]
    return out


WORD_CASES = _cases("word")
BANK_CASES = _cases("bank")


def _source(pack_id: str, skill_id: str) -> SkillSource:
    return CATALOGS[pack_id].source(skill_id)


def _template(source: SkillSource, template_id: str) -> WordTemplate:
    assert source.word_problems is not None
    return next(t for t in source.word_problems.templates if t.id == template_id)


def _latex(value: sympy.Expr) -> str:
    assert isinstance(value, sympy.Rational)
    return str(value.p) if value.q == 1 else rf"\frac{{{value.p}}}{{{value.q}}}"


def _expected_answer(source: SkillSource, template: WordTemplate, problem: Problem) -> sympy.Expr:
    bare = source.generate(problem.seed, problem.tier)
    if template.expression is None:
        return bare.answer
    rng = random.Random(f"{problem.seed}:slots:{template.id}")
    slots = fill_slots(template.slots, source.slots, rng)
    numbers = {k: v for k, v in {**bare.values, **slots}.items() if isinstance(v, int)}
    return evaluate(template.expression, numbers)


@pytest.mark.parametrize(("pack_id", "skill_id", "template_id"), WORD_CASES)
def test_every_word_template_renders_and_recomputes(
    pack_id: str, skill_id: str, template_id: str
) -> None:
    source = _source(pack_id, skill_id)
    template = _template(source, template_id)
    for tier in range(len(source.tier_difficulties)):
        for seed in range(SEEDS):
            problem = source.generate(seed, tier, "word", template_id)
            assert (problem.variant, problem.template_id) == ("word", template_id)
            assert problem.skill_id == skill_id
            assert problem.prompt
            for part in problem.prompt:
                if isinstance(part, TextPart):
                    assert "{" not in part.text and "}" not in part.text, part.text
                else:
                    assert isinstance(part, MathPart)
                    assert not _SLOT_LEFT.search(part.latex), part.latex
            assert "—" not in plain(problem.prompt)
            assert problem.answer == _expected_answer(source, template, problem)
            if template.expression is None:
                assert problem.misconceptions == source.generate(seed, tier).misconceptions
            assert check(problem, _latex(problem.answer)).verdict is Verdict.CORRECT
            assert source.generate(seed, tier, "word", template_id) == problem


def test_template_is_picked_by_seed_and_covers_all() -> None:
    source = FIXTURE.source("story")
    assert source.word_problems is not None
    picked = {source.generate(seed, 0, "word").template_id for seed in range(300)}
    assert picked == {t.id for t in source.word_problems.templates}
    for seed in range(50):
        first = source.generate(seed, 1, "word")
        assert source.generate(seed, 1, "word", first.template_id) == first
        assert source.generate(seed, 1, "word") == first


def test_two_name_slots_never_share_a_name() -> None:
    source = FIXTURE.source("story")
    for seed in range(300):
        text = plain(source.generate(seed, 0, "word", "marbles").prompt)
        match = re.match(r"(\w+) has \d+ [\w ]+\. (\w+) gives", text)
        assert match is not None, text
        assert match.group(1) != match.group(2)


def test_singular_and_slot_lists() -> None:
    source = FIXTURE.source("story")
    singular = {o.one for o in source.slots.objects}
    text = plain(source.generate(4, 0, "word", "one_bag").prompt)
    assert any(f"Each {one} bag" in text for one in singular), text


def test_math_template_gives_a_math_part() -> None:
    problem = FIXTURE.source("story").generate(3, 0, "word", "as_math")
    a, b = problem.values["a"], problem.values["b"]
    assert problem.prompt == (TextPart("Find the sum: "), MathPart(f"{a} + {b} = ?"))


def test_expression_answers_drop_generator_misconceptions() -> None:
    problem = FIXTURE.source("story").generate(9, 2, "word", "gives_away")
    assert problem.misconceptions == ()


def test_unknown_template_or_empty_variant_falls_back_to_bare() -> None:
    story = FIXTURE.source("story")
    bare = story.generate(5, 1)
    assert story.generate(5, 1, "word", "no_such_template") == bare
    assert story.generate(5, 1, "bank", "no_such_item") == bare
    real = REAL.source("add_within_10")
    assert real.generate(5, 1, "word") == real.generate(5, 1)
    assert real.generate(5, 1, "bank") == real.generate(5, 1)


@pytest.mark.parametrize(("pack_id", "skill_id", "item_id"), BANK_CASES)
def test_every_bank_item_verifies(pack_id: str, skill_id: str, item_id: str) -> None:
    source = _source(pack_id, skill_id)
    assert source.bank is not None
    item = next(i for i in source.bank.items if i.id == item_id)
    orders: set[int] = set()
    for seed in range(SEEDS):
        problem = source.generate(seed, seed % 3, "bank", item_id)
        assert (problem.variant, problem.template_id) == ("bank", item_id)
        assert source.generate(seed, seed % 3, "bank", item_id) == problem
        if item.answer.kind == "expr":
            assert problem.choices is None
            assert problem.answer == expr_answer(item)
            assert check(problem, str(item.answer.value)).verdict is Verdict.CORRECT
            continue
        assert item.choices is not None and problem.choices is not None
        assert problem.correct_choice is not None
        assert 0 <= problem.correct_choice < len(problem.choices)
        assert len(set(problem.choices)) == len(problem.choices) == len(item.choices)
        right = item.choices[int(item.answer.value)]
        assert [p.value for p in right] == [
            p.text if isinstance(p, TextPart) else p.latex
            for p in problem.choices[problem.correct_choice]
        ]
        assert check_choice(problem, problem.correct_choice).verdict is Verdict.CORRECT
        wrong = (problem.correct_choice + 1) % len(problem.choices)
        assert check_choice(problem, wrong).verdict is Verdict.INCORRECT
        orders.add(problem.correct_choice)
    if item.answer.kind == "choice":
        assert len(orders) > 1, "choices are never shuffled"


def test_choice_on_a_typed_problem_is_unreadable() -> None:
    problem = REAL.source("add_within_10").generate(1, 0)
    assert check_choice(problem, 0).verdict is Verdict.UNREADABLE


def test_catalogs_have_cases() -> None:
    assert any(pack == "test-pack" for pack, _, _ in WORD_CASES)
    assert any(pack == "test-pack" for pack, _, _ in BANK_CASES)


def _catalog_ids(catalog: Catalog) -> list[str]:
    return list(catalog.sources)


def test_fixture_catalog_shape() -> None:
    assert _catalog_ids(FIXTURE) == ["pick", "story"]
