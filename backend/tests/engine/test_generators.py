# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false
import math
import re
from pathlib import Path

import pytest
import sympy
from hypothesis import given, settings
from hypothesis import strategies as st

from mathquest.engine.checker.check import Verdict, check
from mathquest.engine.content import load_pack
from mathquest.engine.generators import all_generators, get_generator
from mathquest.engine.types import Generator, MathPart, Problem, TextPart

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
    "count_to_10": -2.6,
    "count_to_20": -2.3,
    "count_to_100": -1.8,
    "compare_groups": -2.5,
    "compare_numbers_20": -2.1,
    "compare_numbers_100": -1.1,
    "one_more_one_less": -1.9,
    "skip_count_10": -1.6,
    "teen_numbers": -1.7,
    "pairs_to_10": -1.5,
    "place_value_hundreds": -0.6,
}

seeds = st.integers(0, 2**32 - 1)
tiers = st.integers(0, 2)
gens = st.sampled_from(GENERATORS)
prop = settings(max_examples=300, deadline=None)


def flatten(problem: Problem) -> str:
    """The prompt as one string, for tests that read numbers out of it."""
    return "".join(p.text if isinstance(p, TextPart) else p.latex for p in problem.prompt)


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
    assert problem.skill_id == gen.generator_id
    assert (problem.tier, problem.seed) == (tier, seed)
    assert problem.difficulty == gen.tier_difficulties[tier]
    flat = flatten(problem)
    assert "\N{EM DASH}" not in flat
    assert "\N{EN DASH}" not in flat
    assert flat.isprintable()
    assert problem.answer >= 0  # pyright: ignore[reportOperatorIssue]


@prop
@given(seed=seeds, tier=tiers)
def test_within_range(seed: int, tier: int) -> None:
    for skill, limit in (("add_within_10", 10), ("sub_within_10", 10), ("add_within_20", 20)):
        assert get_generator(skill).generate(seed, tier).answer <= limit
    sub20 = get_generator("sub_within_20").generate(seed, tier)
    assert 0 <= sub20.answer <= 19


@pytest.mark.parametrize("gen", GENERATORS, ids=lambda g: g.generator_id)
def test_prompts_are_well_formed_parts(gen: Generator) -> None:
    for tier in range(len(gen.tier_difficulties)):
        for seed in range(500):
            problem = gen.generate(seed, tier)
            assert problem.prompt, (gen.generator_id, tier, seed)
            for part in problem.prompt:
                if isinstance(part, MathPart):
                    assert part.latex.strip()
                    assert "\\text" not in part.latex
                else:
                    assert part.text.strip()
            assert problem == gen.generate(seed, tier)
            assert problem.variant == "bare"
            assert problem.template_id is None
            assert problem.values


@pytest.mark.parametrize("gen", GENERATORS, ids=lambda g: g.generator_id)
def test_unknown_variant_or_template_falls_back_to_bare(gen: Generator) -> None:
    bare = gen.generate(7, 1)
    assert gen.generate(7, 1, "word", "gone_template") == bare
    assert gen.generate(7, 1, "bank", None) == bare


def test_values_name_the_chosen_numbers() -> None:
    problem = get_generator("add_within_10").generate(3, 1)
    a, b = problem.values["a"], problem.values["b"]
    assert isinstance(a, int) and isinstance(b, int)
    assert problem.answer == a + b
    assert flatten(problem) == f"{a} + {b} = ?"
    place = get_generator("place_value_tens_ones").generate(3, 1)
    assert str(place.values["number"]) in flatten(place)
    assert f"the {place.values['place']} place" in flatten(place)


def test_place_value_prompt_is_text_math_text() -> None:
    problem = get_generator("place_value_tens_ones").generate(11, 2)
    kinds = [type(p) for p in problem.prompt]
    assert kinds == [TextPart, MathPart, TextPart]


def test_registry_covers_pack() -> None:
    assert set(PACK_SKILLS) <= set(all_generators())
    for gen_id, gen in all_generators().items():
        assert gen.generator_id == gen_id
    assert len(all_generators()) == 20


def test_unknown_skill_is_keyerror() -> None:
    with pytest.raises(KeyError):
        get_generator("nope")


@pytest.mark.parametrize("gen", GENERATORS, ids=lambda g: g.generator_id)
def test_tier_difficulties_use_declared_base(gen: Generator) -> None:
    base = BASES[gen.generator_id]
    assert gen.tier_difficulties == (base - 1.0, base, base + 1.0)


def test_seeds_vary_problems() -> None:
    for gen in GENERATORS:
        prompts = {gen.generate(seed, 1).prompt for seed in range(40)}
        assert len(prompts) > 3, gen.generator_id


def prompt(skill: str, seed: int, tier: int) -> str:
    return flatten(get_generator(skill).generate(seed, tier))


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
def test_no_regroup_mistakes_fail_and_are_matched(seed: int, tier: int) -> None:
    problem = get_generator("add_2digit_no_regroup").generate(seed, tier)
    a, b = addends("add_2digit_no_regroup", seed, tier)
    assert check(problem, str(a + b)).verdict is Verdict.CORRECT
    rules = {
        "subtracted_instead": abs(a - b),
        "added_digits": sum(int(d) for d in f"{a}{b}"),
        "left_out_tens": a + b % 10,
    }
    for key, wrong in rules.items():
        result = check(problem, str(wrong))
        assert result.verdict is Verdict.INCORRECT
        # A wrong answer shared by two mistakes is reported as the first one declared.
        assert result.misconception in rules
        if wrong not in [v for k, v in rules.items() if k != key]:
            assert result.misconception == key


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
    **{("add_within_10", t): {"subtracted_instead", "counted_start"} for t in range(3)},
    **{("sub_within_10", t): {"added_instead", "counted_start"} for t in range(3)},
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
    **{
        ("add_2digit_no_regroup", t): {"subtracted_instead", "added_digits", "left_out_tens"}
        for t in range(3)
    },
    ("place_value_tens_ones", 0): {"confused_tens_ones"},
    ("place_value_tens_ones", 1): {"confused_tens_ones", "confused_adjacent_place"},
    ("place_value_tens_ones", 2): {"confused_adjacent_place"},
    **{
        (skill, t): {"repeated_number", "wrong_direction", "skipped_a_number"}
        for skill in ("count_to_10", "count_to_20", "count_to_100")
        for t in range(3)
    },
    ("count_to_20", 2): {"repeated_number", "wrong_direction", "skipped_a_number", "kept_the_tens"},
    ("count_to_100", 0): {"repeated_number", "wrong_direction", "kept_the_tens"},
    ("count_to_100", 1): {"repeated_number", "wrong_direction", "kept_the_tens"},
    ("count_to_100", 2): {"counted_start", "went_one_too_far", "kept_the_tens"},
    **{("compare_groups", t): {"confused_more_fewer", "counted_both_groups"} for t in range(3)},
    **{
        ("compare_numbers_20", t): {"confused_bigger_smaller", "gave_the_difference"}
        for t in range(3)
    },
    ("compare_numbers_100", 0): {"confused_bigger_smaller", "gave_the_difference"},
    ("compare_numbers_100", 1): {"confused_bigger_smaller", "gave_the_difference"},
    ("compare_numbers_100", 2): {"compared_ones_only", "gave_the_difference"},
    ("one_more_one_less", 0): {"wrong_direction", "skipped_a_number"},
    ("one_more_one_less", 1): {"wrong_direction", "skipped_a_number", "changed_the_tens"},
    ("one_more_one_less", 2): {
        "wrong_direction",
        "skipped_a_number",
        "changed_the_tens",
        "kept_the_tens",
    },
    **{
        ("skip_count_10", t): {"counted_by_ones", "said_the_tens_digit", "skipped_a_ten"}
        for t in range(3)
    },
    **{
        ("teen_numbers", t): {
            "reversed_digits",
            "wrote_ten_then_ones",
            "said_the_ones_only",
            "said_the_tens_digit",
            "copied_the_number",
        }
        for t in range(3)
    },
    **{
        ("pairs_to_10", t): {"gave_the_known_number", "gave_the_total", "counted_start"}
        for t in range(3)
    },
    ("place_value_hundreds", 0): {"gave_the_number", "off_by_one"},
    ("place_value_hundreds", 1): {"gave_the_number", "confused_hundreds_tens"},
    ("place_value_hundreds", 2): {"added_the_digits", "swapped_tens_and_ones", "left_out_the_zero"},
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
def test_two_digit_values_split_the_addends_into_digits(seed: int, tier: int) -> None:
    for skill in TWO_DIGIT_SKILLS:
        values = get_generator(skill).generate(seed, tier).values
        for name in ("a", "b"):
            tens, ones = int(values[f"{name}_tens"]), int(values[f"{name}_ones"])
            assert tens * 10 + ones == values[name]


@prop
@given(seed=seeds, tier=tiers)
def test_place_value_digit_value_is_the_answer(seed: int, tier: int) -> None:
    problem = get_generator("place_value_tens_ones").generate(seed, tier)
    assert problem.values["digit"] == problem.answer


# Problems these skills gave before their teaching content was written, by (skill, tier, seed);
# the batch 1 skills are pinned from the generators' first version.
# A failure means the same seed now gives a different problem, so attempts stored under the
# old one would be checked against the wrong prompt or answer.
PINNED_PROBLEMS = (
    ("sub_within_20", 0, 1, "13 - 3 = ?", 10),
    ("sub_within_20", 0, 7, "16 - 2 = ?", 14),
    ("sub_within_20", 0, 42, "12 - 1 = ?", 11),
    ("sub_within_20", 1, 1, "12 - 7 = ?", 5),
    ("sub_within_20", 1, 7, "13 - 5 = ?", 8),
    ("sub_within_20", 1, 42, "16 - 7 = ?", 9),
    ("sub_within_20", 2, 1, "16 - 9 = ?", 7),
    ("sub_within_20", 2, 7, "17 - 8 = ?", 9),
    ("sub_within_20", 2, 42, "15 - 7 = ?", 8),
    ("add_2digit_no_regroup", 0, 1, "32 + 50 = ?", 82),
    ("add_2digit_no_regroup", 0, 7, "67 + 10 = ?", 77),
    ("add_2digit_no_regroup", 0, 42, "25 + 10 = ?", 35),
    ("add_2digit_no_regroup", 1, 1, "24 + 10 = ?", 34),
    ("add_2digit_no_regroup", 1, 7, "36 + 20 = ?", 56),
    ("add_2digit_no_regroup", 1, 42, "14 + 11 = ?", 25),
    ("add_2digit_no_regroup", 2, 1, "31 + 54 = ?", 85),
    ("add_2digit_no_regroup", 2, 7, "66 + 10 = ?", 76),
    ("add_2digit_no_regroup", 2, 42, "24 + 11 = ?", 35),
    ("add_2digit_regroup", 0, 1, "13 + 29 = ?", 42),
    ("add_2digit_regroup", 0, 7, "26 + 35 = ?", 61),
    ("add_2digit_regroup", 0, 42, "32 + 28 = ?", 60),
    ("add_2digit_regroup", 1, 1, "73 + 19 = ?", 92),
    ("add_2digit_regroup", 1, 7, "46 + 15 = ?", 61),
    ("add_2digit_regroup", 1, 42, "62 + 28 = ?", 90),
    ("add_2digit_regroup", 2, 1, "33 + 89 = ?", 122),
    ("add_2digit_regroup", 2, 7, "86 + 15 = ?", 101),
    ("add_2digit_regroup", 2, 42, "62 + 48 = ?", 110),
    ("place_value_tens_ones", 0, 1, "Which digit is in the ones place of 39?", 9),
    ("place_value_tens_ones", 0, 7, "Which digit is in the tens place of 62?", 6),
    ("place_value_tens_ones", 0, 42, "Which digit is in the tens place of 20?", 2),
    ("place_value_tens_ones", 1, 1, "Which digit is in the hundreds place of 391?", 3),
    ("place_value_tens_ones", 1, 7, "Which digit is in the tens place of 626?", 2),
    ("place_value_tens_ones", 1, 42, "Which digit is in the tens place of 204?", 0),
    ("place_value_tens_ones", 2, 1, "Which digit is in the hundreds place of 3914?", 9),
    ("place_value_tens_ones", 2, 7, "Which digit is in the hundreds place of 6260?", 2),
    ("place_value_tens_ones", 2, 42, "Which digit is in the hundreds place of 2043?", 0),
    ("count_to_10", 0, 7, "What number comes before 4?", 3),
    ("count_to_10", 0, 42, "What number comes before 2?", 1),
    ("count_to_10", 1, 7, "What number comes before 8?", 7),
    ("count_to_10", 1, 42, "What number comes after 7?", 8),
    ("count_to_10", 2, 7, "What number comes after 9?", 10),
    ("count_to_10", 2, 42, "What number comes after 8?", 9),
    ("count_to_20", 0, 7, "What number comes before 14?", 13),
    ("count_to_20", 0, 42, "What number comes after 10?", 11),
    ("count_to_20", 1, 7, "What number comes before 17?", 16),
    ("count_to_20", 1, 42, "What number comes after 16?", 17),
    ("count_to_20", 2, 7, "Count on. What comes next? 17, 18, 19, ?", 20),
    ("count_to_20", 2, 42, "What number is missing? 16, 17, ?, 19", 18),
    ("count_to_100", 0, 7, "Count on. What comes next? 27, 28, 29, ?", 30),
    ("count_to_100", 0, 42, "What number is missing? 19, 20, ?, 22", 21),
    ("count_to_100", 1, 7, "Count on. What comes next? 67, 68, 69, ?", 70),
    ("count_to_100", 1, 42, "What number is missing? 50, 51, ?, 53", 52),
    ("count_to_100", 2, 7, "Count on. What comes next? 37, 38, 39, ?", 40),
    (
        "count_to_100",
        2,
        42,
        "Start at 10. Count on 4 more numbers. Which number do you say last?",
        14,
    ),
    (
        "compare_groups",
        0,
        7,
        "There are 3 apples and 4 dogs. How many are in the group with more?",
        4,
    ),
    (
        "compare_groups",
        0,
        42,
        "There is 1 pear and 2 apples. How many are in the group with more?",
        2,
    ),
    (
        "compare_groups",
        1,
        7,
        "There are 6 apples and 8 dogs. How many are in the group with more?",
        8,
    ),
    (
        "compare_groups",
        1,
        42,
        "There are 2 pears and 3 apples. How many are in the group with more?",
        3,
    ),
    (
        "compare_groups",
        2,
        7,
        "There are 8 apples and 9 dogs. How many are in the group with more?",
        9,
    ),
    (
        "compare_groups",
        2,
        42,
        "There are 6 pears and 7 apples. How many are in the group with more?",
        7,
    ),
    ("compare_numbers_20", 0, 7, "Which number is bigger, 6 or 8?", 8),
    ("compare_numbers_20", 0, 42, "Which number is bigger, 2 or 3?", 3),
    ("compare_numbers_20", 1, 7, "Which number is bigger, 16 or 18?", 18),
    ("compare_numbers_20", 1, 42, "Which number is bigger, 12 or 13?", 13),
    ("compare_numbers_20", 2, 7, "Which number is bigger, 11 or 12?", 12),
    ("compare_numbers_20", 2, 42, "Which number is bigger, 4 or 5?", 5),
    ("one_more_one_less", 0, 7, "What is 1 less than 4?", 3),
    ("one_more_one_less", 0, 42, "What is 1 more than 1?", 2),
    ("one_more_one_less", 1, 7, "What is 1 less than 13?", 12),
    ("one_more_one_less", 1, 42, "What is 1 more than 10?", 11),
    ("one_more_one_less", 2, 7, "What is 1 less than 71?", 70),
    ("one_more_one_less", 2, 42, "What is 1 more than 69?", 70),
    ("teen_numbers", 0, 7, "A ten and 2 ones make what number?", 12),
    ("teen_numbers", 0, 42, "A ten and 3 ones make what number?", 13),
    ("teen_numbers", 1, 7, "A ten and 5 ones make what number?", 15),
    ("teen_numbers", 1, 42, "A ten and 6 ones make what number?", 16),
    ("teen_numbers", 2, 7, "A ten and 8 ones make what number?", 18),
    ("teen_numbers", 2, 42, "A ten and 9 ones make what number?", 19),
    ("pairs_to_10", 0, 7, "3 + ? = 5", 2),
    ("pairs_to_10", 0, 42, "1 + ? = 5", 4),
    ("pairs_to_10", 1, 7, "? + 2 = 8", 6),
    ("pairs_to_10", 1, 42, "? + 1 = 6", 5),
    ("pairs_to_10", 2, 7, "6 + ? = 10", 4),
    ("pairs_to_10", 2, 42, "2 + ? = 10", 8),
    ("place_value_hundreds", 0, 7, "How many bundles of ten make 70?", 7),
    ("place_value_hundreds", 0, 42, "How many bundles of ten make 30?", 3),
    ("place_value_hundreds", 1, 7, "How many hundreds are in 700?", 7),
    ("place_value_hundreds", 1, 42, "How many hundreds are in 300?", 3),
    ("place_value_hundreds", 2, 7, "What number is 6 hundreds, 1 ten and 6 ones?", 616),
    ("place_value_hundreds", 2, 42, "What number is 2 hundreds, 0 tens and 5 ones?", 205),
    ("compare_numbers_100", 0, 7, "Which number is bigger, 67 or 21?", 67),
    ("compare_numbers_100", 0, 42, "Which number is bigger, 25 or 43?", 43),
    ("compare_numbers_100", 1, 7, "Which number is bigger, 63 or 67?", 67),
    ("compare_numbers_100", 1, 42, "Which number is bigger, 21 or 25?", 25),
    ("compare_numbers_100", 2, 7, "Which number is bigger, 63 or 71?", 71),
    ("compare_numbers_100", 2, 42, "Which number is bigger, 29 or 71?", 71),
    ("skip_count_10", 0, 7, "Count by tens. 10, 20, 30, ?", 40),
    ("skip_count_10", 0, 42, "Count by tens. 10, 20, 30, 40, ?", 50),
    ("skip_count_10", 1, 7, "Count by tens. 10, 20, 30, 40, 50, 60, 70, ?", 80),
    ("skip_count_10", 1, 42, "Count by tens. 10, 20, 30, 40, 50, ?", 60),
    ("skip_count_10", 2, 7, "Fill in the missing ten. 60, ?, 80, 90, 100", 70),
    ("skip_count_10", 2, 42, "Fill in the missing ten. 20, ?, 40, 50, 60", 30),
)


@pytest.mark.parametrize(("skill", "tier", "seed", "prompt_text", "answer"), PINNED_PROBLEMS)
def test_problems_for_existing_seeds_are_unchanged(
    skill: str, tier: int, seed: int, prompt_text: str, answer: int
) -> None:
    problem = get_generator(skill).generate(seed, tier)
    assert flatten(problem) == prompt_text
    assert problem.answer == answer


def test_sub_within_20_adding_wins_when_the_column_slip_gives_the_same_number() -> None:
    gen = get_generator("sub_within_20")
    seen_zero_ones = False
    for seed in range(500):
        problem = gen.generate(seed, 2)
        a, b = addends("sub_within_20", seed, 2)
        keys = {m.key: m.answer for m in problem.misconceptions}
        if a % 10 == 0:
            seen_zero_ones = True
            assert keys == {"added_instead": a + b}
            assert check(problem, str(a + b)).misconception == "added_instead"
        else:
            assert keys["subtracted_backwards"] == a // 10 * 10 + abs(a % 10 - b)
    assert seen_zero_ones


@prop
@given(seed=seeds, tier=tiers)
def test_equivalent_fractions_takes_a_number_and_recognises_a_whole_fraction(
    seed: int, tier: int
) -> None:
    problem = get_generator("equivalent_fractions").generate(seed, tier)
    a, b, _ = fractions("equivalent_fractions", seed, tier)
    for latex in (rf"\frac{{{a}}}{{{b}}}", rf"\frac{{{2 * a}}}{{{2 * b}}}"):
        result = check(problem, latex)
        assert result.verdict is Verdict.INCORRECT
        assert result.misconception == "wrote_whole_fraction"


@pytest.mark.parametrize("gen", GENERATORS, ids=lambda g: g.generator_id)
def test_declared_misconception_keys_match_what_is_produced(gen: Generator) -> None:
    produced = {
        m.key
        for tier in range(len(gen.tier_difficulties))
        for seed in range(300)
        for m in gen.generate(seed, tier).misconceptions
    }
    assert produced == set(gen.misconception_keys)


# --- batch 1: counting, comparing, teen numbers, pairs, tens, hundreds ------------------


def numbers(skill: str, seed: int, tier: int) -> list[int]:
    return [int(n) for n in re.findall(r"\d+", prompt(skill, seed, tier))]


def wrong_answers(skill: str, seed: int, tier: int) -> dict[str, int]:
    problem = get_generator(skill).generate(seed, tier)
    return {m.key: int(m.answer) for m in problem.misconceptions}


def kept(answer: int, rules: dict[str, int], floor: int = 0) -> dict[str, int]:
    """What the generator keeps of ``rules``, in declared order: a wrong answer that is
    the answer, one below ``floor`` or one an earlier mistake already gives is dropped."""
    out: dict[str, int] = {}
    for key, value in rules.items():
        if value >= floor and value != answer and value not in out.values():
            out[key] = value
    return out


COUNTING = {
    "count_to_10": (((1, 5), (6, 8), (9, 10)), 10),
    "count_to_20": (((11, 14), (15, 17), (18, 20)), 20),
    "count_to_100": (((21, 50), (51, 100), (11, 100)), 100),
}


@prop
@given(seed=seeds, tier=tiers)
def test_counting_answers_and_numbers_stay_in_the_tier_range(seed: int, tier: int) -> None:
    for skill, (ranges, cap) in COUNTING.items():
        lo, hi = ranges[tier]
        problem = get_generator(skill).generate(seed, tier)
        assert lo <= int(problem.answer) <= hi
        assert all(1 <= n <= cap for n in numbers(skill, seed, tier))
        if skill != "count_to_100" or tier != 2:
            assert problem.values["form"] != "count_on"


@prop
@given(seed=seeds, tier=tiers)
def test_counting_mistakes_follow_their_rules(seed: int, tier: int) -> None:
    for skill in COUNTING:
        problem = get_generator(skill).generate(seed, tier)
        answer, form = int(problem.answer), str(problem.values["form"])
        tens = skill != "count_to_10"
        rules: dict[str, int]
        if form == "after":
            n = int(problem.values["n"])
            assert answer == n + 1
            rules = {"repeated_number": n, "wrong_direction": n - 1, "skipped_a_number": n + 2}
            if tens and n % 10 == 9:
                rules["kept_the_tens"] = n // 10 * 10
        elif form == "before":
            n = int(problem.values["n"])
            assert answer == n - 1
            rules = {"repeated_number": n, "wrong_direction": n + 1, "skipped_a_number": n - 2}
            if tens and n % 10 == 0:
                rules["kept_the_tens"] = answer + 10
        elif form == "count_on":
            start, more = int(problem.values["start"]), int(problem.values["more"])
            assert answer == start + more
            assert numbers(skill, seed, tier) == [start, more]
            rules = {"counted_start": answer - 1, "went_one_too_far": answer + 1}
        else:
            rules = {"repeated_number": answer - 1, "skipped_a_number": answer + 1}
            if tens and form == "run" and answer % 10 == 0:
                rules["kept_the_tens"] = answer - 10
        assert wrong_answers(skill, seed, tier) == kept(answer, rules, floor=1), (skill, form)


def test_count_to_100_tier_two_starts_from_any_number() -> None:
    starts = {
        numbers("count_to_100", seed, 2)[0]
        for seed in range(300)
        if prompt("count_to_100", seed, 2).startswith("Start at")
    }
    assert len(starts) > 10


def test_counting_crosses_a_ten_often_enough_to_practise_it() -> None:
    for skill, tier in (("count_to_20", 2), ("count_to_100", 0), ("count_to_100", 1)):
        crossing = sum(
            int(get_generator(skill).generate(seed, tier).answer) % 10 == 0 for seed in range(300)
        )
        assert crossing > 60, skill


@prop
@given(seed=seeds, tier=tiers)
def test_one_more_one_less_answer_and_ranges(seed: int, tier: int) -> None:
    problem = get_generator("one_more_one_less").generate(seed, tier)
    n, answer = int(problem.values["n"]), int(problem.answer)
    more = "1 more than" in flatten(problem)
    assert answer == n + (1 if more else -1)
    assert numbers("one_more_one_less", seed, tier)[-1] == n
    lo, hi = ((1, 10), (10, 20), (20, 100))[tier]
    assert lo <= n <= hi
    assert lo <= answer <= hi or (tier == 2 and answer == lo - 1)


@prop
@given(seed=seeds, tier=tiers)
def test_one_more_one_less_mistakes_follow_their_rules(seed: int, tier: int) -> None:
    problem = get_generator("one_more_one_less").generate(seed, tier)
    n, answer = int(problem.values["n"]), int(problem.answer)
    step = answer - n
    rules = {"wrong_direction": n - step, "skipped_a_number": n + 2 * step}
    if tier >= 1:
        rules["changed_the_tens"] = n + 10 * step
    if tier == 2 and n % 10 == (9 if step == 1 else 0):
        rules["kept_the_tens"] = n // 10 * 10 if step == 1 else n + 9
    assert wrong_answers("one_more_one_less", seed, tier) == kept(answer, rules)


def test_one_more_one_less_goes_across_a_ten_often_in_tier_two() -> None:
    edges = sum(
        int(get_generator("one_more_one_less").generate(seed, 2).answer) % 10 in (0, 9)
        for seed in range(300)
    )
    assert edges > 80


@prop
@given(seed=seeds, tier=tiers)
def test_skip_count_10_is_a_row_of_tens(seed: int, tier: int) -> None:
    answer = int(get_generator("skip_count_10").generate(seed, tier).answer)
    shown = numbers("skip_count_10", seed, tier)
    assert answer % 10 == 0
    if tier == 0:
        assert 30 <= answer <= 50
        assert shown == list(range(10, answer, 10))
    elif tier == 1:
        assert 60 <= answer <= 100
        assert shown == list(range(shown[0], answer, 10))
    else:
        words = prompt("skip_count_10", seed, tier)
        assert words.startswith("Fill in the missing ten. ")
        row = words.removeprefix("Fill in the missing ten. ").split(", ")
        assert len(row) == 5
        assert row[0] != "?" and row[-1] != "?"
        start = int(row[0])
        assert [r if r == "?" else int(r) for r in row] == [
            "?" if v == answer else v for v in range(start, start + 50, 10)
        ]
        assert start >= 10 and start + 40 <= 100


@prop
@given(seed=seeds, tier=tiers)
def test_skip_count_10_mistakes_follow_their_rules(seed: int, tier: int) -> None:
    answer = int(get_generator("skip_count_10").generate(seed, tier).answer)
    assert wrong_answers("skip_count_10", seed, tier) == {
        "counted_by_ones": answer - 9,
        "said_the_tens_digit": answer // 10,
        "skipped_a_ten": answer + 10,
    }


@prop
@given(seed=seeds, tier=tiers)
def test_teen_numbers_ranges_and_mistakes(seed: int, tier: int) -> None:
    problem = get_generator("teen_numbers").generate(seed, tier)
    teen, ones = int(problem.values["teen"]), int(problem.values["ones"])
    lo, hi = ((11, 13), (14, 16), (17, 19))[tier]
    assert lo <= teen <= hi
    assert ones == teen - 10
    if problem.values["asks"] == "number":
        assert problem.answer == teen
        assert numbers("teen_numbers", seed, tier) == [ones]
        rules = {
            "reversed_digits": ones * 10 + 1,
            "wrote_ten_then_ones": 100 + ones,
            "said_the_ones_only": ones,
        }
    else:
        assert problem.answer == ones
        assert numbers("teen_numbers", seed, tier) == [teen]
        rules = {"said_the_tens_digit": 1, "copied_the_number": teen}
    assert wrong_answers("teen_numbers", seed, tier) == kept(int(problem.answer), rules)


def test_teen_numbers_agree_with_one_one() -> None:
    texts = {prompt("teen_numbers", seed, 0) for seed in range(100)}
    assert "A ten and 1 one make what number?" in texts
    assert not any("1 ones" in t for t in texts)


@prop
@given(seed=seeds, tier=tiers)
def test_pairs_to_10_make_the_total(seed: int, tier: int) -> None:
    problem = get_generator("pairs_to_10").generate(seed, tier)
    known, total = int(problem.values["known"]), int(problem.values["total"])
    answer = int(problem.answer)
    assert known + answer == total
    assert 1 <= known < total
    assert (total == 5, 6 <= total <= 9, total == 10)[tier]
    assert flatten(problem) in (f"{known} + ? = {total}", f"? + {known} = {total}")
    rules = {
        "gave_the_known_number": known,
        "gave_the_total": total,
        "counted_start": answer + 1,
    }
    assert wrong_answers("pairs_to_10", seed, tier) == kept(answer, rules)


@prop
@given(seed=seeds, tier=tiers)
def test_place_value_hundreds_by_tier(seed: int, tier: int) -> None:
    problem = get_generator("place_value_hundreds").generate(seed, tier)
    got = wrong_answers("place_value_hundreds", seed, tier)
    answer = int(problem.answer)
    if tier == 0:
        (number,) = numbers("place_value_hundreds", seed, tier)
        assert number % 10 == 0 and 20 <= number <= 100
        assert answer == number // 10
        assert got == {"gave_the_number": number, "off_by_one": answer - 1}
    elif tier == 1:
        (number,) = numbers("place_value_hundreds", seed, tier)
        assert number % 100 == 0 and 200 <= number <= 900
        if problem.values["asks"] == "hundreds":
            assert answer == number // 100
            assert got == {"gave_the_number": number, "confused_hundreds_tens": number // 10}
        else:
            assert answer == number // 10
            assert got == {"gave_the_number": number, "confused_hundreds_tens": number // 100}
    else:
        h, t, o = numbers("place_value_hundreds", seed, tier)
        assert 1 <= h <= 9 and 0 <= t <= 9 and 0 <= o <= 9
        assert answer == h * 100 + t * 10 + o
        rules = {
            "added_the_digits": h + t + o,
            "swapped_tens_and_ones": h * 100 + o * 10 + t,
        }
        if "0" in str(answer):
            rules["left_out_the_zero"] = int(str(answer).replace("0", ""))
        assert got == kept(answer, rules)


def test_place_value_hundreds_tier_two_has_zeros_to_get_wrong() -> None:
    zero_tens = zero_ones = 0
    for seed in range(300):
        _, t, o = numbers("place_value_hundreds", seed, 2)
        zero_tens += t == 0
        zero_ones += o == 0
    assert zero_tens > 20 and zero_ones > 10


def test_place_value_hundreds_agrees_with_one() -> None:
    texts = {prompt("place_value_hundreds", seed, 2) for seed in range(300)}
    assert any(t.startswith("What number is 1 hundred, ") for t in texts)
    assert not any("1 hundreds" in t or " 1 tens" in t or " 1 ones" in t for t in texts)


@prop
@given(seed=seeds, tier=tiers)
def test_compare_groups_by_tier_and_rule(seed: int, tier: int) -> None:
    problem = get_generator("compare_groups").generate(seed, tier)
    a, b = int(problem.values["a"]), int(problem.values["b"])
    assert a != b
    lo, hi = ((1, 5), (1, 10), (6, 10))[tier]
    assert lo <= min(a, b) and max(a, b) <= hi
    if tier == 2:
        assert abs(a - b) == 1
    more = flatten(problem).endswith("with more?")
    assert problem.answer == (max(a, b) if more else min(a, b))
    assert wrong_answers("compare_groups", seed, tier) == {
        "confused_more_fewer": min(a, b) if more else max(a, b),
        "counted_both_groups": a + b,
    }


def test_compare_groups_uses_the_singular_for_one() -> None:
    texts = {prompt("compare_groups", seed, 0) for seed in range(300)}
    assert any(t.startswith("There is 1 ") for t in texts)
    for t in texts:
        for count, noun in re.findall(r"(\d+) (\w+)", t):
            assert noun.endswith("s") == (count != "1") or noun == "fish", t


@prop
@given(seed=seeds, tier=tiers)
def test_compare_numbers_20_by_tier_and_rule(seed: int, tier: int) -> None:
    problem = get_generator("compare_numbers_20").generate(seed, tier)
    a, b = numbers("compare_numbers_20", seed, tier)
    assert a != b
    if tier == 0:
        assert min(a, b) >= 1 and max(a, b) <= 10
    elif tier == 1:
        assert min(a, b) >= 11 and max(a, b) <= 20
    else:
        assert min(a, b) >= 1 and max(a, b) <= 20
        assert abs(a - b) <= 2
    bigger = "bigger" in flatten(problem)
    big, small = max(a, b), min(a, b)
    assert problem.answer == (big if bigger else small)
    rules = {
        "confused_bigger_smaller": small if bigger else big,
        "gave_the_difference": big - small,
    }
    assert wrong_answers("compare_numbers_20", seed, tier) == kept(int(problem.answer), rules)


@prop
@given(seed=seeds, tier=tiers)
def test_compare_numbers_100_by_tier_and_rule(seed: int, tier: int) -> None:
    problem = get_generator("compare_numbers_100").generate(seed, tier)
    a, b = numbers("compare_numbers_100", seed, tier)
    assert 10 <= a <= 99 and 10 <= b <= 99 and a != b
    big, small = max(a, b), min(a, b)
    if tier == 0:
        assert abs(a // 10 - b // 10) >= 2
    elif tier == 1:
        assert a // 10 == b // 10
    else:
        assert small // 10 < big // 10
        assert small % 10 > big % 10
    bigger = "bigger" in flatten(problem)
    assert problem.answer == (big if bigger else small)
    first = "compared_ones_only" if tier == 2 else "confused_bigger_smaller"
    rules = {first: small if bigger else big, "gave_the_difference": big - small}
    assert wrong_answers("compare_numbers_100", seed, tier) == kept(int(problem.answer), rules)


def test_compare_numbers_100_tier_two_has_reversed_digit_pairs() -> None:
    pairs = [numbers("compare_numbers_100", seed, 2) for seed in range(400)]
    assert any(a == int(str(b)[::-1]) for a, b in pairs)


# --- the values the batch 1 hints and explanations lean on ------------------------------


BATCH_ONE = (
    "count_to_10",
    "count_to_20",
    "count_to_100",
    "compare_groups",
    "compare_numbers_20",
    "one_more_one_less",
    "skip_count_10",
    "teen_numbers",
    "pairs_to_10",
    "place_value_hundreds",
    "compare_numbers_100",
)


@prop
@given(seed=seeds, tier=tiers)
def test_batch_one_values_name_the_answer(seed: int, tier: int) -> None:
    for skill in BATCH_ONE:
        problem = get_generator(skill).generate(seed, tier)
        assert problem.values["answer"] == problem.answer, skill


@prop
@given(seed=seeds, tier=tiers)
def test_counting_values_point_at_a_number_the_prompt_shows(seed: int, tier: int) -> None:
    for skill in COUNTING:
        problem = get_generator(skill).generate(seed, tier)
        near = int(problem.values["near"])
        assert near in numbers(skill, seed, tier)
        way = str(problem.values["dir"])
        assert way in ("up", "back")
        if problem.values["form"] == "before":
            assert (problem.values["rel"], way, near - 1) == (
                "one less than",
                "back",
                problem.answer,
            )
        elif problem.values["form"] == "count_on":
            assert problem.values["rel"] == f"{problem.values['more']} more than"
            assert near + int(problem.values["more"]) == problem.answer
        else:
            assert (problem.values["rel"], way, near + 1) == ("one more than", "up", problem.answer)


@prop
@given(seed=seeds, tier=tiers)
def test_teen_hint_values_show_the_prompts_number(seed: int, tier: int) -> None:
    problem = get_generator("teen_numbers").generate(seed, tier)
    assert int(problem.values["shown"]) in numbers("teen_numbers", seed, tier)
    assert int(problem.values["shown"]) != problem.answer


@prop
@given(seed=seeds, tier=tiers)
def test_comparing_values_name_which_is_asked(seed: int, tier: int) -> None:
    for skill in ("compare_numbers_20", "compare_numbers_100"):
        problem = get_generator(skill).generate(seed, tier)
        assert str(problem.values["which"]) in flatten(problem)
    groups = get_generator("compare_groups").generate(seed, tier)
    assert str(groups.values["more"]) in flatten(groups)
