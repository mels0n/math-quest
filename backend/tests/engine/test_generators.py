# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false
from pathlib import Path

import pytest
import sympy
from hypothesis import given, settings
from hypothesis import strategies as st

from mathquest.engine.checker.check import Verdict, check
from mathquest.engine.generators import all_generators, get_generator
from mathquest.engine.skillgraph import load_pack
from mathquest.engine.types import Generator

PACK = Path(__file__).resolve().parents[2] / "content" / "packs" / "k8-core"
PACK_SKILLS = tuple(load_pack(PACK).skills)
GENERATORS: tuple[Generator, ...] = tuple(all_generators().values())
BASES = {
    "add_within_10": -2.0,
    "sub_within_10": -1.8,
    "add_within_20": -1.2,
    "sub_within_20": -1.0,
    "place_value_tens_ones": -1.0,
    "add_2digit_no_regroup": -0.5,
    "add_2digit_regroup": 0.0,
    "equivalent_fractions": 0.0,
    "add_fractions_unlike": 0.8,
}

seeds = st.integers(0, 2**32 - 1)
tiers = st.integers(0, 2)
generators = st.sampled_from(GENERATORS)
prop = settings(max_examples=300, deadline=None)


def render(value: sympy.Basic) -> str:
    """LaTeX for an integer or rational, the only answer shapes these skills produce."""
    assert isinstance(value, sympy.Rational)
    if value.is_integer:
        return str(int(value))
    return rf"\frac{{{value.p}}}{{{value.q}}}"


@prop
@given(gen=generators, seed=seeds, tier=tiers)
def test_deterministic(gen: Generator, seed: int, tier: int) -> None:
    assert gen.generate(seed, tier) == gen.generate(seed, tier)


@prop
@given(gen=generators, seed=seeds, tier=tiers)
def test_answer_passes_own_checker(gen: Generator, seed: int, tier: int) -> None:
    problem = gen.generate(seed, tier)
    assert check(problem, render(problem.answer)).verdict is Verdict.CORRECT


@prop
@given(gen=generators, seed=seeds, tier=tiers)
def test_misconceptions_fail_and_match(gen: Generator, seed: int, tier: int) -> None:
    problem = gen.generate(seed, tier)
    for m in problem.misconceptions:
        if m.answer == problem.answer:
            continue
        result = check(problem, render(m.answer))
        assert result.verdict is Verdict.INCORRECT
        assert result.misconception == m.key


@prop
@given(gen=generators, seed=seeds, tier=tiers)
def test_problem_metadata(gen: Generator, seed: int, tier: int) -> None:
    problem = gen.generate(seed, tier)
    assert problem.skill_id == gen.skill_id
    assert (problem.tier, problem.seed) == (tier, seed)
    assert problem.difficulty == gen.tier_difficulties[tier]
    assert "—" not in problem.prompt_latex
    assert problem.prompt_latex.isprintable()
    assert problem.answer >= 0  # pyright: ignore[reportOperatorIssue]


@prop
@given(seed=seeds, tier=tiers)
def test_within_range(seed: int, tier: int) -> None:
    for skill, limit in (("add_within_10", 10), ("sub_within_10", 10), ("add_within_20", 20)):
        assert get_generator(skill).generate(seed, tier).answer <= limit
    sub20 = get_generator("sub_within_20").generate(seed, tier)
    assert 0 <= sub20.answer <= 19


def test_registry_covers_pack() -> None:
    assert set(PACK_SKILLS) <= set(all_generators())
    assert len(all_generators()) == 9


def test_unknown_skill_is_keyerror() -> None:
    with pytest.raises(KeyError):
        get_generator("nope")


@pytest.mark.parametrize("gen", GENERATORS, ids=lambda g: g.skill_id)
def test_tier_difficulties_use_declared_base(gen: Generator) -> None:
    base = BASES[gen.skill_id]
    assert gen.tier_difficulties == (base - 1.0, base, base + 1.0)


def test_seeds_vary_problems() -> None:
    for gen in GENERATORS:
        prompts = {gen.generate(seed, 1).prompt_latex for seed in range(40)}
        assert len(prompts) > 3, gen.skill_id
