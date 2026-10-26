# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false
import itertools
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
    "count_on": -1.8,
    "make_ten_strategy": -0.9,
    "add_three_numbers": -1.1,
    "missing_number_20": -0.9,
    "fact_families_20": -0.7,
    "doubles_near_doubles": -1.3,
    "ten_more_ten_less": -1.4,
    "sub_tens_within_100": -0.8,
    "add_within_100_basic": -0.7,
    "equal_or_not": -1.0,
    "skip_count_2_5": -0.8,
    "word_problems_20": -0.6,
    "sub_2digit_no_regroup": -0.3,
    "sub_2digit_regroup": 0.3,
    "add_several_2digit": 0.2,
    "mental_add_10_100": -0.2,
    "fluency_within_20": -0.4,
    "clock_hours": -1.5,
    "read_data_graphs": -0.9,
    "even_odd": -0.7,
    "compare_numbers_1000": -0.2,
    "word_problems_100": 0.4,
    "add_3digit_no_regroup": 0.5,
    "sub_3digit_no_regroup": 0.6,
    "add_3digit_regroup": 0.9,
    "sub_3digit_regroup": 1.1,
    "equal_groups": 0.3,
    "arrays": 0.4,
    "mult_as_groups": 0.8,
    "mult_0_1_10": 0.9,
    "mult_2_5": 1.0,
    "mult_3_4": 1.3,
    "mult_6_7": 1.6,
    "mult_8_9": 1.9,
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
    assert len(all_generators()) == 54


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
    **{
        (skill, 2): {"counted_start", "went_one_too_far"}
        for skill in ("count_to_10", "count_to_20")
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
        ("teen_numbers", t): {"reversed_digits", "wrote_ten_then_ones", "said_the_ones_only"}
        for t in range(2)
    },
    ("teen_numbers", 2): {"said_the_tens_digit", "copied_the_number"},
    **{
        ("pairs_to_10", t): {"gave_the_known_number", "gave_the_total", "counted_start"}
        for t in range(3)
    },
    ("place_value_hundreds", 0): {"gave_the_number", "off_by_one"},
    ("place_value_hundreds", 1): {"gave_the_number", "confused_hundreds_tens"},
    ("place_value_hundreds", 2): {"added_the_digits", "swapped_tens_and_ones", "left_out_the_zero"},
    **{
        ("count_on", t): {"counted_start", "went_one_too_far", "subtracted_instead"}
        for t in range(3)
    },
    ("make_ten_strategy", 0): {"counted_start", "subtracted_instead", "gave_the_leftover"},
    ("make_ten_strategy", 1): {"gave_the_total", "gave_the_gap_to_ten", "subtracted_instead"},
    ("make_ten_strategy", 2): {"gave_the_total", "counted_start", "added_instead"},
    **{
        ("add_three_numbers", t): {"left_out_the_last", "left_out_the_first", "left_out_the_middle"}
        for t in range(3)
    },
    ("missing_number_20", 0): {"added_the_shown", "gave_a_shown_number"},
    ("missing_number_20", 1): {"added_the_shown", "gave_a_shown_number"},
    ("missing_number_20", 2): {"added_the_shown", "subtracted_the_shown", "gave_a_shown_number"},
    ("fact_families_20", 0): {"subtracted_the_shown", "gave_a_shown_number"},
    **{
        ("fact_families_20", t): {"added_the_shown", "subtracted_the_shown", "gave_a_shown_number"}
        for t in (1, 2)
    },
    ("doubles_near_doubles", 0): {"gave_the_number", "counted_start", "went_one_too_far"},
    ("doubles_near_doubles", 1): {"doubled_the_smaller", "doubled_the_bigger"},
    ("doubles_near_doubles", 2): {"gave_the_total", "doubled_instead"},
    **{
        ("ten_more_ten_less", t): {"wrong_direction", "changed_the_ones", "said_the_tens_digit"}
        for t in range(3)
    },
    ("sub_tens_within_100", 0): {"said_the_tens_digit", "added_instead", "off_by_ten"},
    ("sub_tens_within_100", 1): {"said_the_tens_digit", "added_instead", "off_by_ten"},
    ("sub_tens_within_100", 2): {
        "said_the_tens_digit",
        "added_instead",
        "subtracted_instead",
        "off_by_ten",
    },
    ("add_within_100_basic", 0): {"added_to_the_tens", "subtracted_instead"},
    ("add_within_100_basic", 1): {"added_to_the_ones", "added_one_ten", "subtracted_instead"},
    ("add_within_100_basic", 2): {
        "forgot_the_new_ten",
        "wrote_the_ones_together",
        "added_to_the_tens",
    },
    **{
        ("equal_or_not", t): {"gave_the_total", "copied_a_number", "added_all_the_numbers"}
        for t in range(3)
    },
    **{
        ("skip_count_2_5", t): {"counted_by_ones", "used_the_other_step", "skipped_a_number"}
        for t in range(3)
    },
    **{
        ("word_problems_20", t): {
            "used_the_other_operation",
            "gave_the_first_number",
            "gave_the_second_number",
        }
        for t in range(3)
    },
    **{
        ("sub_2digit_no_regroup", t): {"added_instead", "left_out_the_ones", "left_out_the_tens"}
        for t in range(3)
    },
    **{
        ("sub_2digit_regroup", t): {
            "added_instead",
            "subtracted_backwards",
            "forgot_to_lower_the_tens",
        }
        for t in range(3)
    },
    **{
        ("add_several_2digit", t): {"left_out_the_last", "forgot_the_carry", "carried_one_ten"}
        for t in range(3)
    },
    ("add_several_2digit", 2): {
        "left_out_the_last",
        "forgot_the_carry",
        "carried_one_ten",
        "dropped_the_hundred",
    },
    **{
        ("mental_add_10_100", t): {"wrong_direction", "used_the_other_step", "changed_the_ones"}
        for t in range(3)
    },
    ("fluency_within_20", 0): {"subtracted_instead", "one_too_few", "one_too_many"},
    ("fluency_within_20", 1): {"added_instead", "one_too_few", "one_too_many"},
    ("fluency_within_20", 2): {
        "subtracted_instead",
        "added_instead",
        "one_too_few",
        "one_too_many",
    },
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
# the batch 1 and batch 2 skills are pinned from the generators' first version.
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
    ("count_to_10", 0, 7, "What comes right after 2?", 3),
    ("count_to_10", 0, 42, "What number comes after 5?", 6),
    ("count_to_10", 1, 7, "What comes right before 8?", 7),
    ("count_to_10", 1, 42, "Say the number after 2.", 3),
    ("count_to_10", 2, 7, "What number is missing? 5, 6, ?, 8, 9, 10", 7),
    ("count_to_10", 2, 42, "Say the number before 4.", 3),
    ("count_to_20", 0, 7, "What comes right after 12?", 13),
    ("count_to_20", 0, 42, "What number comes after 15?", 16),
    ("count_to_20", 1, 7, "Count on. What comes next? 9, 10, 11, 12, ?", 13),
    ("count_to_20", 1, 42, "What number is missing? 10, ?, 12", 11),
    ("count_to_20", 2, 7, "Start at 12. Count on 1 more number. Which number do you say last?", 13),
    ("count_to_20", 2, 42, "Count on. What comes next? 9, 10, ?", 11),
    ("count_to_100", 0, 7, "Count on. What comes next? 26, 27, 28, 29, ?", 30),
    ("count_to_100", 0, 42, "What number is missing? 20, ?, 22", 21),
    ("count_to_100", 1, 7, "Count on. What comes next? 66, 67, 68, 69, ?", 70),
    ("count_to_100", 1, 42, "What number is missing? 51, ?, 53", 52),
    ("count_to_100", 2, 7, "Count on. What comes next? 36, 37, 38, 39, ?", 40),
    ("count_to_100", 2, 42, "What number is missing? 13, ?, 15", 14),
    (
        "compare_groups",
        0,
        7,
        "There are 3 pears and 4 hats. How many are in the group with more?",
        4,
    ),
    (
        "compare_groups",
        0,
        42,
        "There is 1 frog and 2 dogs. How many are in the group with more?",
        2,
    ),
    (
        "compare_groups",
        1,
        7,
        "There are 6 pears and 8 hats. How many are in the group with more?",
        8,
    ),
    (
        "compare_groups",
        1,
        42,
        "There are 2 frogs and 3 dogs. How many are in the group with more?",
        3,
    ),
    (
        "compare_groups",
        2,
        7,
        "There are 8 pears and 9 hats. How many are in the group with more?",
        9,
    ),
    (
        "compare_groups",
        2,
        42,
        "There are 6 frogs and 7 dogs. How many are in the group with more?",
        7,
    ),
    ("compare_numbers_20", 0, 7, "Which number is bigger, 6 or 8?", 8),
    ("compare_numbers_20", 0, 42, "Which number is bigger, 2 or 3?", 3),
    ("compare_numbers_20", 1, 7, "Which number is bigger, 16 or 18?", 18),
    ("compare_numbers_20", 1, 42, "Which number is bigger, 12 or 13?", 13),
    ("compare_numbers_20", 2, 7, "Which number is bigger, 11 or 12?", 12),
    ("compare_numbers_20", 2, 42, "Which number is bigger, 4 or 5?", 5),
    ("one_more_one_less", 0, 7, "What number is 1 less than 4?", 3),
    ("one_more_one_less", 0, 42, "Find 1 more than 1?", 2),
    ("one_more_one_less", 1, 7, "What number is 1 less than 13?", 12),
    ("one_more_one_less", 1, 42, "Find 1 more than 10?", 11),
    ("one_more_one_less", 2, 7, "Find 1 less than 71?", 70),
    ("one_more_one_less", 2, 42, "What is 1 more than 69?", 70),
    ("teen_numbers", 0, 7, "A ten and 6 ones make what number?", 16),
    ("teen_numbers", 0, 42, "A ten and 2 ones make what number?", 12),
    ("teen_numbers", 1, 7, "10 + 6 = ?", 16),
    ("teen_numbers", 1, 42, "10 + 2 = ?", 12),
    ("teen_numbers", 2, 7, "How many ones are in 16 after you take out the ten?", 6),
    ("teen_numbers", 2, 42, "12 is a ten and how many more ones?", 2),
    ("pairs_to_10", 0, 7, "? + 2 = 5", 3),
    ("pairs_to_10", 0, 42, "1 + ? = 6", 5),
    ("pairs_to_10", 1, 7, "7 = ? + 2", 5),
    ("pairs_to_10", 1, 42, "5 = 1 + ?", 4),
    ("pairs_to_10", 2, 7, "8 = ? + 2", 6),
    ("pairs_to_10", 2, 42, "6 = 1 + ?", 5),
    ("place_value_hundreds", 0, 7, "How many bundles of ten make 70?", 7),
    ("place_value_hundreds", 0, 42, "How many bundles of ten make 30?", 3),
    ("place_value_hundreds", 1, 7, "How many hundreds make 700?", 7),
    ("place_value_hundreds", 1, 42, "How many hundreds make 300?", 3),
    ("place_value_hundreds", 2, 7, "What number is 6 hundreds, 1 ten and 6 ones?", 616),
    ("place_value_hundreds", 2, 42, "What number is 2 hundreds, 0 tens and 5 ones?", 205),
    ("compare_numbers_100", 0, 7, "Which number is bigger, 66 or 20?", 66),
    ("compare_numbers_100", 0, 42, "Which number is bigger, 24 or 43?", 43),
    ("compare_numbers_100", 1, 7, "Which number is bigger, 62 or 66?", 66),
    ("compare_numbers_100", 1, 42, "Which number is bigger, 20 or 24?", 24),
    ("compare_numbers_100", 2, 7, "Which number is bigger, 62 or 70?", 70),
    ("compare_numbers_100", 2, 42, "Which number is bigger, 29 or 70?", 70),
    ("skip_count_10", 0, 7, "Count back by tens. 30, 20, ?", 10),
    ("skip_count_10", 0, 42, "Count by tens. 10, 20, ?", 30),
    ("skip_count_10", 1, 7, "Count back by tens. 80, 70, 60, ?", 50),
    ("skip_count_10", 1, 42, "Count by tens. 30, 40, 50, ?", 60),
    ("skip_count_10", 2, 7, "Find the missing ten. 60, ?, 80, 90, 100", 70),
    ("skip_count_10", 2, 42, "Find the missing ten. 20, ?, 40, 50, 60", 30),
    ("count_on", 0, 7, "Say 5. Then count on 3 more. What is the last number you say?", 8),
    ("count_on", 0, 42, "You are on 1. Jump on 1 more. Which number do you reach?", 2),
    ("count_on", 1, 7, "Count on. 6 + 3 = ?", 9),
    ("count_on", 1, 42, "Count on. 2 + 1 = ?", 3),
    ("count_on", 2, 7, "Count on from the bigger number. 3 + 6 = ?", 9),
    ("count_on", 2, 42, "Count on from the bigger number. 1 + 2 = ?", 3),
    ("make_ten_strategy", 0, 7, "Make a ten first. 7 + 9 = ?", 16),
    ("make_ten_strategy", 0, 42, "Make a ten first. 5 + 7 = ?", 12),
    ("make_ten_strategy", 1, 7, "7 + 9 = 10 + ?", 6),
    ("make_ten_strategy", 1, 42, "5 + 7 = 10 + ?", 2),
    ("make_ten_strategy", 2, 7, "7 + ? = 16", 9),
    ("make_ten_strategy", 2, 42, "5 + ? = 12", 7),
    ("add_three_numbers", 0, 7, "3 + 7 + 3 = ?", 13),
    ("add_three_numbers", 0, 42, "1 + 3 + 2 = ?", 6),
    ("add_three_numbers", 1, 7, "4 + 3 + 6 = ?", 13),
    ("add_three_numbers", 1, 42, "8 + 1 + 2 = ?", 11),
    (
        "add_three_numbers",
        2,
        7,
        "Mia has 3 cups, 7 plates and 3 spoons. How many things does Mia have in all?",
        13,
    ),
    (
        "add_three_numbers",
        2,
        42,
        "Sam has 1 apple, 3 pears and 2 plums. How many fruits does Sam have in all?",
        6,
    ),
    ("missing_number_20", 0, 7, "Find the missing number. ? + 10 = 13", 3),
    ("missing_number_20", 0, 42, "Find the missing number. ? + 5 = 6", 1),
    ("missing_number_20", 1, 7, "Find the missing number. 13 = 3 + ?", 10),
    ("missing_number_20", 1, 42, "Find the missing number. 6 - ? = 1", 5),
    ("missing_number_20", 2, 7, "Find the missing number. 13 = ? + 10", 3),
    ("missing_number_20", 2, 42, "Find the missing number. 1 = ? - 5", 6),
    ("fact_families_20", 0, 7, "You know that 3 + 10 = 13. What is 10 + 3?", 13),
    ("fact_families_20", 0, 42, "You know that 1 + 5 = 6. What is 5 + 1?", 6),
    ("fact_families_20", 1, 7, "You know that 3 + 10 = 13. What is 13 - 10?", 3),
    ("fact_families_20", 1, 42, "You know that 1 + 5 = 6. What is 6 - 5?", 1),
    ("fact_families_20", 2, 7, "Finish the fact family. 13 - 10 = ?", 3),
    ("fact_families_20", 2, 42, "Finish the fact family. 6 - ? = 5", 1),
    ("doubles_near_doubles", 0, 7, "6 + 6 = ?", 12),
    ("doubles_near_doubles", 0, 42, "2 + 2 = ?", 4),
    ("doubles_near_doubles", 1, 7, "What is 6 plus 7?", 13),
    ("doubles_near_doubles", 1, 42, "What is 2 plus 3?", 5),
    ("doubles_near_doubles", 2, 7, "Both numbers are the same. ? + ? = 12", 6),
    ("doubles_near_doubles", 2, 42, "Both numbers are the same. ? + ? = 4", 2),
    ("ten_more_ten_less", 0, 7, "Find 10 less than 39.", 29),
    ("ten_more_ten_less", 0, 42, "What number is 10 more than 13?", 23),
    ("ten_more_ten_less", 1, 7, "39 - 10 = ?", 29),
    ("ten_more_ten_less", 1, 42, "10 + 13 = ?", 23),
    ("ten_more_ten_less", 2, 7, "Find the missing number. 29 = ? - 10", 39),
    ("ten_more_ten_less", 2, 42, "Find the missing number. 23 = ? + 10", 13),
    ("sub_tens_within_100", 0, 7, "70 - 60 = ?", 10),
    ("sub_tens_within_100", 0, 42, "50 - 20 = ?", 30),
    ("sub_tens_within_100", 1, 7, "Take away 60 from 70. What is left?", 10),
    ("sub_tens_within_100", 1, 42, "Take away 20 from 50. What is left?", 30),
    ("sub_tens_within_100", 2, 7, "Find the missing number. 70 - ? = 10", 60),
    ("sub_tens_within_100", 2, 42, "Find the missing number. 50 - ? = 30", 20),
    ("add_within_100_basic", 0, 7, "6 + 33 = ?", 39),
    ("add_within_100_basic", 0, 42, "2 + 14 = ?", 16),
    ("add_within_100_basic", 1, 7, "60 + 16 = ?", 76),
    ("add_within_100_basic", 1, 42, "20 + 14 = ?", 34),
    ("add_within_100_basic", 2, 7, "5 + 76 = ?", 81),
    ("add_within_100_basic", 2, 42, "8 + 52 = ?", 60),
    ("equal_or_not", 0, 7, "3 + 11 = 8 + ?", 6),
    ("equal_or_not", 0, 42, "1 + 6 = 4 + ?", 3),
    ("equal_or_not", 1, 7, "3 + 11 = 8 + ?", 6),
    ("equal_or_not", 1, 42, "1 + 6 = ? + 4", 3),
    ("equal_or_not", 2, 7, "18 - 4 = 12 + ?", 2),
    ("equal_or_not", 2, 42, "19 - 12 = ? + 3", 4),
    ("skip_count_2_5", 0, 7, "Count by 5s. 65, 70, ?", 75),
    ("skip_count_2_5", 0, 42, "Count by 2s. 18, 20, ?", 22),
    ("skip_count_2_5", 1, 7, "Count by 5s. 10, 15, 20, ?", 25),
    ("skip_count_2_5", 1, 42, "Count back by 2s. 15, 13, ?", 11),
    ("skip_count_2_5", 2, 7, "Fill in the missing number. 25, 30, ?, 40, 45", 35),
    ("skip_count_2_5", 2, 42, "Fill in the missing number. 19, ?, 23, 25, 27", 21),
    (
        "word_problems_20",
        0,
        7,
        "Leo has 11 dogs. Nora gives Leo 2 more. How many dogs does Leo have now?",
        13,
    ),
    (
        "word_problems_20",
        0,
        42,
        "Ava has 5 cats. Leo gives Ava 1 more. How many cats does Ava have now?",
        6,
    ),
    (
        "word_problems_20",
        1,
        7,
        "Leo has 11 red dogs and 2 blue dogs. How many dogs does Leo have in all?",
        13,
    ),
    (
        "word_problems_20",
        1,
        42,
        "Ava has 11 cats. 4 of them are red. The rest are blue. How many are blue?",
        7,
    ),
    (
        "word_problems_20",
        2,
        7,
        "Leo has 11 dogs. Then Leo gets some more. Now Leo has 15. How many did Leo get?",
        4,
    ),
    (
        "word_problems_20",
        2,
        42,
        "Ava has 11 cats. Ava gives some away. Now Ava has 4. How many did Ava give away?",
        7,
    ),
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
    "count_to_10": (((1, 6), (2, 10), (2, 10)), 10),
    "count_to_20": (((11, 16), (11, 20), (11, 20)), 20),
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
    if tier == 2 and step == 1 and n % 10 == 9:
        rules["kept_the_tens"] = n // 10 * 10
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
    problem = get_generator("skip_count_10").generate(seed, tier)
    answer = int(problem.answer)
    shown = numbers("skip_count_10", seed, tier)
    assert answer % 10 == 0
    back = problem.values["dir"] == "back"
    assert problem.values["jump"] == (-10 if back else 10)
    assert problem.values["tens_way"] == ("less" if back else "more")
    if tier == 2:
        assert not back
        words = prompt("skip_count_10", seed, tier)
        row = re.sub(r"^[A-Za-z ]+\. ", "", words).split(", ")
        assert len(row) == 5
        assert row[0] != "?" and row[-1] != "?"
        start = int(row[0])
        assert [r if r == "?" else int(r) for r in row] == [
            "?" if v == answer else v for v in range(start, start + 50, 10)
        ]
        assert start >= 10 and start + 40 <= 100
        return
    assert len(shown) >= 2
    assert int(problem.values["previous"]) == shown[-1]
    if back:
        assert shown == list(range(shown[0], answer, -10))
        assert answer >= (10 if tier == 0 else 50) and shown[0] <= (50, 100)[tier]
        assert "back" in prompt("skip_count_10", seed, tier) or "down" in prompt(
            "skip_count_10", seed, tier
        )
    else:
        assert shown == list(range(shown[0], answer, 10))
        assert (30, 60)[tier] <= answer <= (50, 100)[tier]


@prop
@given(seed=seeds, tier=tiers)
def test_skip_count_10_mistakes_follow_their_rules(seed: int, tier: int) -> None:
    problem = get_generator("skip_count_10").generate(seed, tier)
    answer, step = int(problem.answer), int(problem.values["jump"])
    rules = {
        "counted_by_ones": answer - step + (-1 if step < 0 else 1),
        "said_the_tens_digit": answer // 10,
        "skipped_a_ten": answer + step,
    }
    assert wrong_answers("skip_count_10", seed, tier) == kept(answer, rules, floor=1)


def test_skip_count_10_counts_back_in_the_first_two_tiers_only() -> None:
    for tier, back in ((0, True), (1, True), (2, False)):
        directions = {
            get_generator("skip_count_10").generate(seed, tier).values["dir"] for seed in range(200)
        }
        assert ("back" in directions) is back
        assert "up" in directions


@prop
@given(seed=seeds, tier=tiers)
def test_teen_numbers_ranges_and_mistakes(seed: int, tier: int) -> None:
    problem = get_generator("teen_numbers").generate(seed, tier)
    teen, ones = int(problem.values["teen"]), int(problem.values["ones"])
    assert 11 <= teen <= 19
    assert ones == teen - 10
    shown = numbers("teen_numbers", seed, tier)
    if "10" in prompt("teen_numbers", seed, tier).replace(str(teen), ""):
        shown.remove(10)  # the ten of "10 + 4 = ?" is part of the sum, not a number to read
    if problem.values["asks"] == "number":
        assert problem.answer == teen
        assert shown == [ones]
        rules = {
            "reversed_digits": ones * 10 + 1,
            "wrote_ten_then_ones": 100 + ones,
            "said_the_ones_only": ones,
        }
    else:
        assert problem.answer == ones
        assert shown == [teen]
        rules = {"said_the_tens_digit": 1, "copied_the_number": teen}
    assert problem.values["shown"] == shown[0]
    assert wrong_answers("teen_numbers", seed, tier) == kept(int(problem.answer), rules)


def test_teen_numbers_get_harder_by_form_and_share_the_range() -> None:
    def prompts(tier: int) -> set[str]:
        return {prompt("teen_numbers", seed, tier) for seed in range(600)}

    easy, middle, hard = prompts(0), prompts(1), prompts(2)
    assert all(not t.startswith("10 + ") and "10 plus" not in t for t in easy)
    assert any(t.startswith("A ten and ") for t in easy)
    assert any(t.startswith("10 + ") and t.endswith("= ?") for t in middle)
    assert any(" + 10 = ?" in t for t in middle)
    assert any("10 plus" in t for t in middle)
    assert any(t.endswith("= 10 + ?") for t in hard)
    assert any(t.endswith("after you take out the ten?") for t in hard)
    for tier in range(3):
        teens = {
            int(get_generator("teen_numbers").generate(s, tier).values["teen"]) for s in range(300)
        }
        assert teens == set(range(11, 20))


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
    assert ((4, 6), (5, 9), (6, 10))[tier][0] <= total <= ((4, 6), (5, 9), (6, 10))[tier][1]
    assert flatten(problem) in (
        f"{known} + ? = {total}",
        f"? + {known} = {total}",
        f"{total} = {known} + ?",
        f"{total} = ? + {known}",
        f"You have {known}. How many more make {total}?",
    )
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
            more = int(problem.values["more"])
            assert problem.values["rel"] == ("one" if more == 1 else str(more)) + " more than"
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


@pytest.mark.parametrize("skill", BATCH_ONE)
def test_no_batch_one_tier_runs_out_of_problems(skill: str) -> None:
    """A learner works a tier for a while, so every tier has a few dozen different
    problems (the floor here is about twenty)."""
    gen = get_generator(skill)
    for tier in range(3):
        assert len({flatten(gen.generate(seed, tier)) for seed in range(5000)}) >= 20, (skill, tier)


def test_count_on_is_one_form_in_five_in_every_tier_of_count_to_100() -> None:
    gen = get_generator("count_to_100")
    for tier in range(3):
        forms = [gen.generate(seed, tier).values["form"] for seed in range(1000)]
        assert 0.14 <= forms.count("count_on") / 1000 <= 0.26, tier


def test_only_generators_with_few_candidate_answers_count_the_first_try_only() -> None:
    """The comparing skills (two numbers to pick from), fact families (the answer is always
    one of the numbers shown) and four batch 3 skills whose answer is, in most forms, one of
    two or three numbers the question shows: clock hours, reading a graph, even or odd."""
    flagged = {
        gid for gid, gen in all_generators().items() if getattr(gen, "first_try_counts", False)
    }
    assert flagged == {
        "compare_groups",
        "compare_numbers_20",
        "compare_numbers_100",
        "compare_numbers_1000",
        "fact_families_20",
        "clock_hours",
        "read_data_graphs",
        "even_odd",
    }


def test_pair_layouts_get_harder_by_tier() -> None:
    def layouts(tier: int) -> set[str]:
        return {re.sub(r"\d+", "#", prompt("pairs_to_10", seed, tier)) for seed in range(600)}

    assert layouts(0) == {"# + ? = #", "? + # = #"}
    assert layouts(1) == layouts(0) | {"# = # + ?", "# = ? + #"}
    assert layouts(2) == layouts(1) | {"You have #. How many more make #?"}


@pytest.mark.parametrize("skill", BATCH_ONE)
def test_every_batch_one_tier_has_a_spread_of_answers(skill: str) -> None:
    """Tiers span the range and get harder through the form of the question, so none may
    shrink to a handful of answers, and no one answer may be a third of the draws."""
    gen = get_generator(skill)
    for tier in range(3):
        answers = [int(gen.generate(seed, tier).answer) for seed in range(3000)]
        distinct = set(answers)
        assert len(distinct) >= 5, (skill, tier, sorted(distinct))
        top = max(answers.count(a) for a in distinct) / len(answers)
        assert top <= 0.35, (skill, tier, top)


# --- batch 2: strategies, number sentences, tens and stories ----------------------------

BATCH_TWO = (
    "count_on",
    "make_ten_strategy",
    "add_three_numbers",
    "missing_number_20",
    "fact_families_20",
    "doubles_near_doubles",
    "ten_more_ten_less",
    "sub_tens_within_100",
    "add_within_100_basic",
    "equal_or_not",
    "skip_count_2_5",
    "word_problems_20",
)


def side_value(side: str) -> int:
    """A side of a number sentence of whole numbers joined by + and -, worked left to right."""
    tokens = side.split()
    total = int(tokens[0])
    for op, number in zip(tokens[1::2], tokens[2::2], strict=True):
        total += int(number) if op == "+" else -int(number)
    return total


def holds(sentence: str, fill: int) -> bool:
    """``sentence`` is true when every ``?`` in it is ``fill``."""
    left, right = sentence.replace("?", str(fill)).split("=")
    return side_value(left) == side_value(right)


def maths(skill: str, seed: int, tier: int) -> list[str]:
    problem = get_generator(skill).generate(seed, tier)
    return [p.latex for p in problem.prompt if isinstance(p, MathPart)]


def shape(sentence: str) -> str:
    return re.sub(r"\d+", "#", sentence)


@prop
@given(seed=seeds, tier=tiers)
def test_count_on_numbers_forms_and_mistakes(seed: int, tier: int) -> None:
    problem = get_generator("count_on").generate(seed, tier)
    start, more = int(problem.values["start"]), int(problem.values["more"])
    total = start + more
    assert 1 <= more <= 5 and start >= 1 and total <= 20
    assert problem.answer == total
    shown = numbers("count_on", seed, tier)
    if tier == 0:
        assert shown == [start, more]
    else:
        assert start > more
        assert shown == ([start, more] if tier == 1 else [more, start])
        assert shape(maths("count_on", seed, tier)[0]) == "# + # = ?"
        assert ("bigger number" in prompt("count_on", seed, tier)) == (tier == 2)
    rules = {
        "counted_start": total - 1,
        "went_one_too_far": total + 1,
        "subtracted_instead": abs(start - more),
    }
    assert wrong_answers("count_on", seed, tier) == kept(total, rules)


@prop
@given(seed=seeds, tier=tiers)
def test_make_ten_crosses_ten_in_every_form(seed: int, tier: int) -> None:
    problem = get_generator("make_ten_strategy").generate(seed, tier)
    values = problem.values
    first, answer = int(values["first"]), int(problem.answer)
    shown = numbers("make_ten_strategy", seed, tier)
    assert values["to_ten"] == 10 - first and 1 <= int(values["to_ten"]) <= 8
    assert first in shown and answer == values["answer"]
    rules: dict[str, int]
    if tier == 2:
        known, total = shown
        assert first == known and 2 <= known <= 9 and 11 <= total <= 18
        assert 2 <= answer <= 9 and known + answer == total
        rules = {
            "gave_the_total": total,
            "counted_start": answer + 1,
            "added_instead": known + total,
        }
    else:
        a, b = shown[:2]
        total = a + b
        assert 2 <= a <= 9 and 2 <= b <= 9 and 11 <= total <= 18
        assert first == max(a, b)
        if tier == 0:
            assert answer == total
            rules = {
                "counted_start": total - 1,
                "subtracted_instead": abs(a - b),
                "gave_the_leftover": total - 10,
            }
        else:
            assert shown[2] == 10 and answer == total - 10
            rules = {
                "gave_the_total": total,
                "gave_the_gap_to_ten": 10 - first,
                "subtracted_instead": abs(a - b),
            }
    assert values["past_ten"] == total - 10
    assert wrong_answers("make_ten_strategy", seed, tier) == kept(answer, rules)


@prop
@given(seed=seeds, tier=tiers)
def test_add_three_numbers_by_tier(seed: int, tier: int) -> None:
    problem = get_generator("add_three_numbers").generate(seed, tier)
    v = {k: int(x) for k, x in problem.values.items()}
    a, b, c = v["a"], v["b"], v["c"]
    assert min(a, b, c) >= 1 and a + b + c <= 20
    assert problem.answer == a + b + c
    assert numbers("add_three_numbers", seed, tier) == [a, b, c]
    assert v["p"] + v["q"] + v["r"] == a + b + c
    if tier == 1:
        assert a + c == 10 and (v["p"], v["q"], v["r"]) == (a, c, b)
    else:
        assert (v["p"], v["q"], v["r"]) == (a, b, c)
    assert (tier == 2) == ("in all?" in prompt("add_three_numbers", seed, tier))
    rules = {
        "left_out_the_last": a + b,
        "left_out_the_first": b + c,
        "left_out_the_middle": a + c,
    }
    assert wrong_answers("add_three_numbers", seed, tier) == kept(a + b + c, rules)


def test_add_three_numbers_story_agrees_with_one() -> None:
    texts = {prompt("add_three_numbers", seed, 2) for seed in range(600)}
    assert any(" 1 " in t for t in texts)
    for t in texts:
        for count, noun in re.findall(r"(\d+) ([a-z]+)", t):
            assert noun.endswith("s") == (count != "1") or noun == "fish", t


MISSING_SHAPES = (
    {"# + ? = #", "? + # = #"},
    {"# + ? = #", "? + # = #", "# - ? = #", "# = # + ?", "# = ? + #"},
    {"? - # = #", "# = # - ?", "# = ? - #", "# = ? + #", "# - ? = #"},
)


@prop
@given(seed=seeds, tier=tiers)
def test_missing_number_sentence_is_true_with_the_answer(seed: int, tier: int) -> None:
    problem = get_generator("missing_number_20").generate(seed, tier)
    (sentence,) = maths("missing_number_20", seed, tier)
    answer = int(problem.answer)
    assert holds(sentence, answer)
    assert shape(sentence) in MISSING_SHAPES[tier]
    first, second = numbers("missing_number_20", seed, tier)
    assert (problem.values["s1"], problem.values["s2"]) == (first, second)
    assert 1 <= answer <= 20 and max(first, second) <= 20
    assert problem.values["answer"] == answer
    x, y, z = (int(problem.values[k]) for k in "xyz")
    assert x + y == z <= 20
    rules = {
        "added_the_shown": first + second,
        "subtracted_the_shown": abs(first - second),
        "gave_a_shown_number": max(first, second),
    }
    assert wrong_answers("missing_number_20", seed, tier) == kept(answer, rules)


def test_missing_number_tiers_use_the_forms_they_name() -> None:
    for tier in (0, 2):
        seen = {shape(maths("missing_number_20", seed, tier)[0]) for seed in range(400)}
        assert seen == MISSING_SHAPES[tier]
    seen = {shape(maths("missing_number_20", seed, 1)[0]) for seed in range(400)}
    assert seen == MISSING_SHAPES[1]


@prop
@given(seed=seeds, tier=tiers)
def test_fact_family_prompts_show_the_family_until_tier_two_hides_the_answer(
    seed: int, tier: int
) -> None:
    problem = get_generator("fact_families_20").generate(seed, tier)
    lo, hi, total = (int(problem.values[k]) for k in ("lo", "hi", "total"))
    assert 1 <= lo < hi and lo + hi == total <= 20
    answer = int(problem.answer)
    assert answer in (lo, hi, total) and problem.values["answer"] == answer
    if tier < 2:
        assert set(numbers("fact_families_20", seed, tier)) == {lo, hi, total}
    else:  # the sentence shows two numbers of the family, never the one it asks for
        shown = set(numbers("fact_families_20", seed, tier))
        assert shown == {lo, hi, total} - {answer}
        assert {problem.values["s1"], problem.values["s2"]} == shown
    parts = maths("fact_families_20", seed, tier)
    if tier < 2:
        assert prompt("fact_families_20", seed, tier).startswith("You know that ")
        assert holds(parts[0], 0)  # the fact it gives is true
        assert side_value(parts[1]) == answer
        first, second = (int(n) for n in re.findall(r"\d+", parts[1]))
    else:
        assert holds(parts[0], answer)
        first, second = (int(n) for n in re.findall(r"\d+", parts[0]))
    rules = {
        "added_the_shown": first + second,
        "subtracted_the_shown": abs(first - second),
        "gave_a_shown_number": max(first, second),
    }
    assert wrong_answers("fact_families_20", seed, tier) == kept(answer, rules)


def test_fact_family_tiers_ask_the_form_they_name() -> None:
    def asked(tier: int) -> set[str]:
        return {shape(maths("fact_families_20", seed, tier)[-1]) for seed in range(500)}

    assert asked(0) == {"# + #"}
    assert asked(1) == {"# - #", "# + #"}
    assert asked(2) == {"# + # = ?", "# - # = ?", "# + ? = #", "# - ? = #"}
    known = {shape(maths("fact_families_20", seed, 1)[0]) for seed in range(500)}
    assert known == {"# + # = #", "# - # = #"}


@prop
@given(seed=seeds, tier=tiers)
def test_doubles_by_tier(seed: int, tier: int) -> None:
    problem = get_generator("doubles_near_doubles").generate(seed, tier)
    answer = int(problem.answer)
    shown = numbers("doubles_near_doubles", seed, tier)
    assert int(problem.values["shown"]) in shown
    assert str(answer) in str(problem.values["worked"])
    rules: dict[str, int]
    if tier == 0:
        n = shown[0]
        assert set(shown) == {n} and 1 <= n <= 10 and answer == 2 * n
        rules = {"gave_the_number": n, "counted_start": 2 * n - 1, "went_one_too_far": 2 * n + 1}
    elif tier == 1:
        left, right = shown
        assert abs(left - right) == 1 and 1 <= min(left, right) <= 9
        small = min(left, right)
        assert answer == left + right
        rules = {"doubled_the_smaller": 2 * small, "doubled_the_bigger": 2 * small + 2}
    else:
        (total,) = shown
        assert total % 2 == 0 and 2 <= total <= 20 and answer == total // 2
        rules = {"gave_the_total": total, "doubled_instead": 2 * total}
    assert wrong_answers("doubles_near_doubles", seed, tier) == kept(answer, rules)


@prop
@given(seed=seeds, tier=tiers)
def test_ten_more_ten_less_forms_and_mistakes(seed: int, tier: int) -> None:
    problem = get_generator("ten_more_ten_less").generate(seed, tier)
    n, answer = int(problem.values["n"]), int(problem.answer)
    step = answer - n
    assert abs(step) == 10 and 10 <= answer <= 100 and 10 <= n <= 100
    assert problem.values["dir"] == ("up" if step > 0 else "down")
    assert problem.values["way"] == ("more" if step > 0 else "less")
    assert sorted(numbers("ten_more_ten_less", seed, tier)) == sorted([n, 10])
    text = prompt("ten_more_ten_less", seed, tier)
    if tier == 0:
        assert f"10 {problem.values['way']} than {n}" in text
    elif tier == 1:
        (sentence,) = maths("ten_more_ten_less", seed, tier)
        assert sentence in (f"{n} + 10 = ?", f"10 + {n} = ?", f"{n} - 10 = ?")
        assert side_value(sentence.split("=")[0]) == answer
    else:
        (sentence,) = maths("ten_more_ten_less", seed, tier)
        assert holds(sentence, answer) and "?" in sentence
    rules = {
        "wrong_direction": n - step,
        "changed_the_ones": n + (1 if step > 0 else -1),
        "said_the_tens_digit": answer // 10,
    }
    assert wrong_answers("ten_more_ten_less", seed, tier) == kept(answer, rules)


@prop
@given(seed=seeds, tier=tiers)
def test_sub_tens_are_whole_tens_in_every_form(seed: int, tier: int) -> None:
    problem = get_generator("sub_tens_within_100").generate(seed, tier)
    v = {k: int(x) for k, x in problem.values.items()}
    assert v["top"] % 10 == v["take"] % 10 == 0 and 20 <= v["top"] <= 90 and v["take"] >= 10
    assert v["top"] - v["take"] == v["rest"] >= 10
    answer = int(problem.answer)
    assert answer == v["answer"] and answer % 10 == 0
    shown = numbers("sub_tens_within_100", seed, tier)
    assert len(shown) == 2
    s1, s2 = v["s1_tens"] * 10, v["s2_tens"] * 10
    if tier < 2:
        assert sorted(shown) == sorted([v["top"], v["take"]]) and answer == v["rest"]
        assert (s1, s2) == (v["top"], v["take"])
    else:
        (sentence,) = maths("sub_tens_within_100", seed, tier)
        assert holds(sentence, answer)
        assert shown == [s1, s2]
    rules = {
        "said_the_tens_digit": answer // 10,
        "added_instead": s1 + s2,
        "subtracted_instead": abs(s1 - s2),
        "off_by_ten": answer + 10,
    }
    assert wrong_answers("sub_tens_within_100", seed, tier) == kept(answer, rules)


def test_sub_tens_forms_by_tier() -> None:
    assert {shape(maths("sub_tens_within_100", s, 0)[0]) for s in range(300)} == {"# - # = ?"}
    assert any("Take away" in prompt("sub_tens_within_100", s, 1) for s in range(100))
    assert any(" minus " in prompt("sub_tens_within_100", s, 1) for s in range(100))
    two = {shape(maths("sub_tens_within_100", s, 2)[0]) for s in range(300)}
    assert two == {"# - ? = #", "? - # = #"}


@prop
@given(seed=seeds, tier=tiers)
def test_add_ones_and_tens_by_tier(seed: int, tier: int) -> None:
    problem = get_generator("add_within_100_basic").generate(seed, tier)
    a, b = int(problem.values["a"]), int(problem.values["b"])
    assert 10 <= a <= 99 and problem.answer == a + b <= 99
    assert sorted(numbers("add_within_100_basic", seed, tier)) == sorted([a, b])
    if tier == 0:
        assert 1 <= b <= 9 and a % 10 + b <= 9
        rules = {"added_to_the_tens": a + 10 * b, "subtracted_instead": a - b}
    elif tier == 1:
        assert b % 10 == 0 and 10 <= b <= 80 and a // 10 + b // 10 <= 9
        rules = {
            "added_to_the_ones": a + b // 10,
            "added_one_ten": a + 10,
            "subtracted_instead": a - b,
        }
    else:
        assert 1 <= b <= 9 and a % 10 + b >= 10 and a // 10 <= 8
        rules = {
            "forgot_the_new_ten": a + b - 10,
            "wrote_the_ones_together": a // 10 * 100 + a % 10 + b,
            "added_to_the_tens": a + 10 * b,
        }
    assert wrong_answers("add_within_100_basic", seed, tier) == kept(a + b, rules)


@prop
@given(seed=seeds, tier=tiers)
def test_add_ones_and_tens_values_split_the_digits(seed: int, tier: int) -> None:
    values = get_generator("add_within_100_basic").generate(seed, tier).values
    for name in ("a", "b"):
        tens, ones = int(values[f"{name}_tens"]), int(values[f"{name}_ones"])
        assert tens * 10 + ones == values[name]


@prop
@given(seed=seeds, tier=tiers)
def test_skip_count_2_5_rows(seed: int, tier: int) -> None:
    problem = get_generator("skip_count_2_5").generate(seed, tier)
    v = problem.values
    step, jump, answer = int(v["step"]), int(v["jump"]), int(problem.answer)
    previous = int(v["previous"])
    words = prompt("skip_count_2_5", seed, tier)
    assert step in (2, 5) and abs(jump) == step and answer == previous + jump
    assert v["way"] == ("less" if jump < 0 else "more")
    assert v["dir"] == ("back" if jump < 0 else "up")
    (row_text,) = maths("skip_count_2_5", seed, tier)
    items = row_text.split(", ")
    row = [answer if n == "?" else int(n) for n in items]
    assert all(b - a == jump for a, b in itertools.pairwise(row))
    assert 1 <= answer <= (100 if step == 5 else 51)
    if tier == 2:
        assert len(row) == 5 and jump > 0
        hidden = items.index("?")
        assert 1 <= hidden <= 3 and row[hidden - 1] == previous
    else:
        assert f"{step}s. " in words and items[-1] == "?" and 3 <= len(row) <= 5
        assert row[-2] == previous
    if tier == 0:
        assert jump > 0 and answer % step == 0
    if step == 5:
        assert answer % 5 == 0
    if jump < 0:
        assert tier == 1 and ("back" in words or "down" in words)
    sign = 1 if jump > 0 else -1
    rules = {
        "counted_by_ones": previous + sign,
        "used_the_other_step": previous + sign * (7 - step),
        "skipped_a_number": answer + jump,
    }
    assert wrong_answers("skip_count_2_5", seed, tier) == kept(answer, rules)


def test_skip_count_2_5_tiers_add_counting_back_and_odd_rows() -> None:
    gen = get_generator("skip_count_2_5")

    def seen(tier: int, key: str) -> set[object]:
        return {gen.generate(s, tier).values[key] for s in range(400)}

    assert seen(0, "dir") == {"up"}
    assert seen(1, "dir") == {"up", "back"}
    assert seen(2, "dir") == {"up"}
    assert seen(0, "step") == {2, 5}
    odd = {
        int(p.answer) % 2 for p in (gen.generate(s, 1) for s in range(400)) if p.values["step"] == 2
    }
    assert odd == {0, 1}
    even = {
        int(p.answer) % 2 for p in (gen.generate(s, 0) for s in range(400)) if p.values["step"] == 2
    }
    assert even == {0}


@prop
@given(seed=seeds, tier=tiers)
def test_equal_or_not_sentence_balances(seed: int, tier: int) -> None:
    problem = get_generator("equal_or_not").generate(seed, tier)
    (sentence,) = maths("equal_or_not", seed, tier)
    answer, side, beside = (int(problem.values[k]) for k in ("answer", "side", "beside"))
    assert problem.answer == answer and answer >= 1 and holds(sentence, answer)
    sides = [s.strip() for s in sentence.split("=")]
    full = next(s for s in sides if "?" not in s)
    assert side_value(full) == side and 4 <= side <= 20
    whole = numbers("equal_or_not", seed, tier)
    assert beside in whole and answer == side - beside
    layouts = {"{S} = # + ?", "{S} = ? + #", "# + ? = {S}", "? + # = {S}"}
    sums = {"# + #"} if tier < 2 else {"# + #", "# - #"}
    allowed = {layout.replace("{S}", s) for layout in layouts for s in sums}
    if tier == 0:
        allowed = {"# + # = # + ?"}
    assert shape(sentence) in allowed
    rules = {
        "gave_the_total": side,
        "copied_a_number": beside,
        "added_all_the_numbers": sum(whole),
    }
    assert wrong_answers("equal_or_not", seed, tier) == kept(answer, rules)


def test_equal_or_not_tiers_use_the_forms_they_name() -> None:
    def forms(tier: int) -> set[str]:
        return {shape(maths("equal_or_not", seed, tier)[0]) for seed in range(400)}

    assert forms(0) == {"# + # = # + ?"}
    assert len(forms(1)) == 4 and not any("-" in f for f in forms(1))
    assert len(forms(2)) == 8 and sum("-" in f for f in forms(2)) == 4


WORD_SHAPES = {
    0: ("add_to", "take_from"),
    1: ("put_together", "take_apart", "compare_more", "compare_fewer"),
    2: ("change_add", "change_take", "start_add", "start_take"),
}


def story_shape(text: str) -> tuple[str, str]:
    """The shape a story is told in, and whether its answer adds or takes away."""
    if "some more. Now" in text:
        return "change_add", "take"
    if "gives some away" in text:
        return "change_take", "take"
    if "at first?" in text:
        return ("start_add", "take") if "more. Now" in text else ("start_take", "add")
    if "red" in text and "in all?" in text:
        return "put_together", "add"
    if "The rest are blue" in text:
        return "take_apart", "take"
    if "How many more" in text:
        return "compare_more", "take"
    if "How many fewer" in text:
        return "compare_fewer", "take"
    if "more. How many" in text:
        return "add_to", "add"
    assert "left?" in text, text
    return "take_from", "take"


@prop
@given(seed=seeds, tier=tiers)
def test_word_problem_shapes_and_answers_by_tier(seed: int, tier: int) -> None:
    problem = get_generator("word_problems_20").generate(seed, tier)
    a, b = int(problem.values["a"]), int(problem.values["b"])
    m, n = int(problem.values["m"]), int(problem.values["n"])
    assert 1 <= b < a and a + b <= 20
    assert 1 <= n < m <= 20 and m >= 3
    text = prompt("word_problems_20", seed, tier)
    story, op = story_shape(text)
    assert story in WORD_SHAPES[tier]
    told1, told2 = (a, b) if op == "add" else (m, n)
    answer = told1 + told2 if op == "add" else told1 - told2
    assert (problem.values["told1"], problem.values["told2"]) == (told1, told2)
    assert problem.answer == answer == problem.values["answer"]
    assert set(numbers("word_problems_20", seed, tier)) == {told1, told2}
    assert str(answer) in str(problem.values["worked"])
    other = told1 - told2 if op == "add" else told1 + told2
    rules = {
        "used_the_other_operation": other,
        "gave_the_first_number": told1,
        "gave_the_second_number": told2,
    }
    assert wrong_answers("word_problems_20", seed, tier) == kept(answer, rules)
    assert not re.search(r"\b1 (?!of\b)[a-z]+s\b", text), text


def test_take_aways_to_20_cross_ten() -> None:
    crossing = 0
    for seed in range(600):
        problem = get_generator("word_problems_20").generate(seed, 0)
        if str(problem.values["worked"]).startswith("Start with"):
            crossing += int(problem.values["told1"]) > 10 > int(problem.answer)
    assert crossing > 0


def test_word_problems_tell_every_shape_in_its_tier() -> None:
    for tier, shapes in WORD_SHAPES.items():
        seen = {story_shape(prompt("word_problems_20", s, tier))[0] for s in range(400)}
        assert seen == set(shapes)


@pytest.mark.parametrize("skill", BATCH_TWO)
def test_every_batch_two_tier_has_a_spread_of_answers(skill: str) -> None:
    """Five different answers at least, and no one answer more than 35% of the draws."""
    gen = get_generator(skill)
    for tier in range(3):
        answers = [int(gen.generate(seed, tier).answer) for seed in range(3000)]
        distinct = set(answers)
        assert len(distinct) >= 5, (skill, tier, sorted(distinct))
        top = max(answers.count(a) for a in distinct) / len(answers)
        assert top <= 0.35, (skill, tier, top)


@pytest.mark.parametrize("skill", BATCH_TWO)
def test_no_batch_two_tier_runs_out_of_problems(skill: str) -> None:
    gen = get_generator(skill)
    for tier in range(3):
        assert len({flatten(gen.generate(seed, tier)) for seed in range(5000)}) >= 20, (skill, tier)


@pytest.mark.parametrize("skill", BATCH_TWO)
def test_every_batch_two_tier_names_two_mistakes(skill: str) -> None:
    gen = get_generator(skill)
    for tier in range(3):
        keys = {m.key for seed in range(300) for m in gen.generate(seed, tier).misconceptions}
        assert len(keys) >= 2, (skill, tier, keys)
        assert keys <= set(gen.misconception_keys)


def reads_like_a_child_text(parts: str, extra: list[str]) -> list[str]:
    """Every sentence a generator writes in code, where the content lint does not read it."""
    return [s for text_value in [parts, *extra] for s in re.split(r"(?<=[.?!]) ", text_value)]


@pytest.mark.parametrize("skill", BATCH_TWO)
def test_batch_two_text_is_short_and_has_no_dash(skill: str) -> None:
    gen = get_generator(skill)
    for tier in range(3):
        for seed in range(200):
            problem = gen.generate(seed, tier)
            spoken = "".join(p.text if isinstance(p, TextPart) else " # " for p in problem.prompt)
            written = [v for v in problem.values.values() if isinstance(v, str)]
            for sentence in reads_like_a_child_text(spoken, written):
                assert len(sentence.split()) <= 12, (skill, tier, seed, sentence)
            for text_value in [spoken, *written]:
                for dash in (chr(0x2014), chr(0x2013), " - ", "--"):
                    assert dash not in text_value, (skill, tier, seed, text_value)


def test_batch_two_hint_sentences_are_true_statements() -> None:
    """The worked line a generator gives the last hint names the answer it works out."""
    for skill in ("doubles_near_doubles", "word_problems_20"):
        for tier in range(3):
            for seed in range(100):
                problem = get_generator(skill).generate(seed, tier)
                assert re.search(rf"\b{problem.answer}\b", str(problem.values["worked"]))


@prop
@given(seed=seeds, tier=tiers)
def test_batch_two_values_name_the_answer(seed: int, tier: int) -> None:
    for skill in BATCH_TWO:
        problem = get_generator(skill).generate(seed, tier)
        if "answer" in problem.values:
            assert problem.values["answer"] == problem.answer, skill


@prop
@given(seed=seeds, tier=tiers)
def test_ten_more_values_split_the_number_into_tens_and_ones(seed: int, tier: int) -> None:
    values = get_generator("ten_more_ten_less").generate(seed, tier).values
    assert int(values["tens"]) * 10 + int(values["ones"]) == values["n"]


@prop
@given(seed=seeds, tier=tiers)
def test_skip_count_2_5_names_its_step_in_words(seed: int, tier: int) -> None:
    values = get_generator("skip_count_2_5").generate(seed, tier).values
    assert values["step_word"] == {2: "two", 5: "five"}[int(values["step"])]


@prop
@given(seed=seeds, tier=tiers)
def test_doubles_hint_step_only_uses_numbers_the_prompt_shows(seed: int, tier: int) -> None:
    problem = get_generator("doubles_near_doubles").generate(seed, tier)
    step_numbers = [int(n) for n in re.findall(r"\d+", str(problem.values["step"]))]
    shown = numbers("doubles_near_doubles", seed, tier)
    assert set(step_numbers) <= set(shown)
    assert step_numbers or tier == 2  # only the halving step names no number
