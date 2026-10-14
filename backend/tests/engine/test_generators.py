# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false
import math
import re
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
gens = st.sampled_from(GENERATORS)
prop = settings(max_examples=300, deadline=None)


def render(value: sympy.Basic) -> str:
    """LaTeX for an integer or rational, the only answer shapes these skills produce."""
    assert isinstance(value, sympy.Rational)
    if value.is_integer:
        return str(int(value))
    return rf"\frac{{{value.p}}}{{{value.q}}}"


@prop
@given(gen=gens, seed=seeds, tier=tiers)
def test_deterministic(gen: Generator, seed: int, tier: int) -> None:
    assert gen.generate(seed, tier) == gen.generate(seed, tier)


@prop
@given(gen=gens, seed=seeds, tier=tiers)
def test_answer_passes_own_checker(gen: Generator, seed: int, tier: int) -> None:
    problem = gen.generate(seed, tier)
    assert check(problem, render(problem.answer)).verdict is Verdict.CORRECT


@prop
@given(gen=gens, seed=seeds, tier=tiers)
def test_misconceptions_fail_and_match(gen: Generator, seed: int, tier: int) -> None:
    problem = gen.generate(seed, tier)
    for m in problem.misconceptions:
        result = check(problem, render(m.answer))
        assert result.verdict is Verdict.INCORRECT
        assert result.misconception == m.key


@prop
@given(gen=gens, seed=seeds, tier=tiers)
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


def prompt(skill: str, seed: int, tier: int) -> str:
    return get_generator(skill).generate(seed, tier).prompt_latex


def addends(skill: str, seed: int, tier: int) -> tuple[int, int]:
    a, b = map(int, re.findall(r"\d+", prompt(skill, seed, tier))[:2])
    return a, b


def fractions(skill: str, seed: int, tier: int) -> list[int]:
    return [int(n) for n in re.findall(r"\d+", prompt(skill, seed, tier))]


TWO_DIGIT_SKILLS = ("add_2digit_no_regroup", "add_2digit_regroup")


@prop
@given(seed=seeds, tier=tiers)
def test_two_digit_addends_are_two_digit(seed: int, tier: int) -> None:
    for skill in TWO_DIGIT_SKILLS:
        a, b = addends(skill, seed, tier)
        assert 10 <= a <= 99
        assert 10 <= b <= 99


@prop
@given(seed=seeds, tier=tiers)
def test_no_regroup_never_carries(seed: int, tier: int) -> None:
    a, b = addends("add_2digit_no_regroup", seed, tier)
    assert a % 10 + b % 10 <= 9
    assert a // 10 + b // 10 <= 9


@prop
@given(seed=seeds, tier=tiers)
def test_regroup_always_carries(seed: int, tier: int) -> None:
    a, b = addends("add_2digit_regroup", seed, tier)
    assert a % 10 + b % 10 >= 10
    tens_carries = a // 10 + b // 10 + 1 >= 10
    assert tens_carries == (tier == 2)


@prop
@given(seed=seeds, tier=tiers)
def test_sub_within_20_borrow_by_tier(seed: int, tier: int) -> None:
    a, b = addends("sub_within_20", seed, tier)
    assert (b > a % 10) == (tier >= 1)


@prop
@given(seed=seeds, tier=tiers)
def test_unlike_denominator_relationship_by_tier(seed: int, tier: int) -> None:
    _, b, _, d = fractions("add_fractions_unlike", seed, tier)
    divides = b % d == 0 or d % b == 0
    if tier == 0:
        assert divides and b != d
    elif tier == 1:
        assert math.gcd(b, d) == 1
    else:
        assert math.gcd(b, d) > 1
        assert not divides


@prop
@given(seed=seeds, tier=tiers)
def test_equivalent_multiplier_by_tier(seed: int, tier: int) -> None:
    _, b, d = fractions("equivalent_fractions", seed, tier)
    lo, hi = ((2, 3), (4, 6), (7, 10))[tier]
    assert d % b == 0
    assert lo <= d // b <= hi


@prop
@given(seed=seeds, tier=tiers)
def test_place_value_digits_and_place_by_tier(seed: int, tier: int) -> None:
    text = prompt("place_value_tens_ones", seed, tier)
    number = re.findall(r"\d+", text)[0]
    assert len(number) == tier + 2
    place = re.search(r"in the (\w+) place", text)
    assert place is not None
    allowed = (("ones", "tens"), ("tens", "hundreds"), ("hundreds", "thousands"))[tier]
    assert place.group(1) in allowed


EXPECTED_KEYS: dict[tuple[str, int], set[str]] = {
    **{("sub_within_10", t): {"added_instead"} for t in range(3)},
    **{("sub_within_20", t): {"added_instead"} for t in range(3)},
    ("sub_within_20", 1): {"added_instead", "subtracted_backwards"},
    ("sub_within_20", 2): {"added_instead", "subtracted_backwards"},
    **{("add_2digit_regroup", t): {"forgot_carry", "added_carry_twice"} for t in range(3)},
    **{
        ("add_fractions_unlike", t): {"added_denominators", "added_numerators_only"}
        for t in range(3)
    },
    **{
        ("equivalent_fractions", t): {
            "added_instead_of_multiplied",
            "copied_numerator",
            "wrote_whole_fraction",
        }
        for t in range(3)
    },
    ("place_value_tens_ones", 0): {"confused_tens_ones"},
    ("place_value_tens_ones", 1): {"confused_tens_ones", "confused_adjacent_place"},
    ("place_value_tens_ones", 2): {"confused_adjacent_place"},
}


@pytest.mark.parametrize(("skill", "tier"), sorted(EXPECTED_KEYS))
def test_expected_misconceptions_are_produced(skill: str, tier: int) -> None:
    gen = get_generator(skill)
    seen = {m.key for seed in range(200) for m in gen.generate(seed, tier).misconceptions}
    assert EXPECTED_KEYS[(skill, tier)] <= seen


def test_sub_within_20_no_borrow_tier_has_no_backwards_misconception() -> None:
    gen = get_generator("sub_within_20")
    keys = {m.key for seed in range(200) for m in gen.generate(seed, 0).misconceptions}
    assert "subtracted_backwards" not in keys


@prop
@given(seed=seeds, tier=tiers)
def test_equivalent_fractions_takes_a_number_and_recognises_a_whole_fraction(
    seed: int, tier: int
) -> None:
    problem = get_generator("equivalent_fractions").generate(seed, tier)
    assert problem.keypad == "numbers"
    a, b, _ = fractions("equivalent_fractions", seed, tier)
    for latex in (rf"\frac{{{a}}}{{{b}}}", rf"\frac{{{2 * a}}}{{{2 * b}}}"):
        result = check(problem, latex)
        assert result.verdict is Verdict.INCORRECT
        assert result.misconception == "wrote_whole_fraction"
