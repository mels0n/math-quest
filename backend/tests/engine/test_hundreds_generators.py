# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false
"""Batch 4 generators: adding and subtracting three-digit numbers, without and with
regrouping."""

import re

import pytest
from hypothesis import given

from mathquest.engine.generators import get_generator
from mathquest.engine.generators.hundreds import _add_slips, _sub_slips  # pyright: ignore[reportPrivateUsage]
from mathquest.engine.types import TextPart
from tests.engine.test_generators import (
    flatten,
    holds,
    kept,
    maths,
    numbers,
    prompt,
    prop,
    reads_like_a_child_text,
    seeds,
    shape,
    tiers,
    wrong_answers,
)

ADDING = ("add_3digit_no_regroup", "add_3digit_regroup")
SUBTRACTING = ("sub_3digit_no_regroup", "sub_3digit_regroup")
HUNDREDS = (*ADDING, *SUBTRACTING)


def pair(skill: str, seed: int, tier: int) -> tuple[int, int, int]:
    """The first number, the second and the result, whatever the form hides."""
    v = get_generator(skill).generate(seed, tier).values
    return int(v["a"]), int(v["b"]), int(v["r"])


def digits(n: int) -> tuple[int, int, int]:
    return n // 100, n // 10 % 10, n % 10


# --- adding ----------------------------------------------------------------------------------


@prop
@given(seed=seeds, tier=tiers)
def test_adding_without_carrying_never_carries(seed: int, tier: int) -> None:
    a, b, r = pair("add_3digit_no_regroup", seed, tier)
    assert 100 <= a <= 899 and 100 <= b <= 899 and r == a + b <= 999
    assert all(x + y <= 9 for x, y in zip(digits(a), digits(b), strict=True))


@prop
@given(seed=seeds, tier=tiers)
def test_adding_with_carrying_always_carries(seed: int, tier: int) -> None:
    a, b, r = pair("add_3digit_regroup", seed, tier)
    assert 100 <= a <= 899 and 100 <= b <= 899 and r == a + b <= 999
    (_, at, ao), (_, bt, bo) = digits(a), digits(b)
    assert ao + bo >= 10 or at + bt >= 10


@pytest.mark.parametrize("skill", ADDING)
@prop
@given(seed=seeds, tier=tiers)
def test_adding_forms_and_answers(skill: str, seed: int, tier: int) -> None:
    problem = get_generator(skill).generate(seed, tier)
    a, b, r = pair(skill, seed, tier)
    v = problem.values
    assert problem.answer == r == v["answer"]
    assert (v["top"], v["bottom"]) == (a, b)
    if tier == 0:
        assert maths(skill, seed, tier) == [f"{a} + {b} = ?"]
    elif tier == 1:
        assert numbers(skill, seed, tier) == [a, b]
        assert len(maths(skill, seed, tier)) == 2
    else:
        assert maths(skill, seed, tier) == [str(a)]
        told = re.findall(r"(\d+) (hundred|ten|one)s?\b", prompt(skill, seed, tier))
        value = {"hundred": 100, "ten": 10, "one": 1}
        assert sum(int(n) * value[unit] for n, unit in told) == b
        assert str(v["parts"]) in prompt(skill, seed, tier)
    for key in ("top", "bottom"):
        number = int(v[key])
        places = (int(v[f"{key}_hundreds"]), int(v[f"{key}_tens"]), int(v[f"{key}_ones"]))
        assert places == digits(number)


@prop
@given(seed=seeds, tier=tiers)
def test_adding_without_carrying_mistakes_follow_their_rules(seed: int, tier: int) -> None:
    skill = "add_3digit_no_regroup"
    a, b, r = pair(skill, seed, tier)
    rules = {
        "subtracted_instead": abs(a - b),
        "left_out_the_hundreds": a + b % 100,
    }
    assert wrong_answers(skill, seed, tier) == kept(r, rules, floor=1)


@prop
@given(seed=seeds, tier=tiers)
def test_adding_with_carrying_mistakes_follow_their_rules(seed: int, tier: int) -> None:
    skill = "add_3digit_regroup"
    a, b, r = pair(skill, seed, tier)
    ones_carry = (a % 10 + b % 10) // 10
    tens_carry = (a // 10 % 10 + b // 10 % 10 + ones_carry) // 10
    rules = {
        "subtracted_instead": abs(a - b),
        "forgot_the_carry": r - 10 * ones_carry - 100 * tens_carry,
        "carried_to_the_wrong_place": r + 90 * ones_carry,
    }
    assert wrong_answers(skill, seed, tier) == kept(r, rules, floor=1)


def test_the_carry_and_borrow_mistakes_by_hand() -> None:
    """478 + 256 is 734. Carrying the ten from 8 + 6 into the hundreds, a child gets 4 in the
    ones, 2 in the tens (7 + 5 = 12, carry 1) and 4 + 2 + 1 + 1 = 8 hundreds: 824. Forgetting
    the carry gives 4, 2 and 6 hundreds: 624. 503 - 178 is 325; borrowing for the ones and the
    tens without lowering the next place leaves 13 - 8, 10 - 7 and 5 - 1: 435."""
    assert dict(_add_slips(478, 256, regroup=True)) == {
        "subtracted_instead": 222,
        "forgot_the_carry": 624,
        "carried_to_the_wrong_place": 824,
    }
    assert dict(_sub_slips(503, 178, regroup=True)) == {
        "added_instead": 681,
        "subtracted_backwards": 475,
        "forgot_to_lower_the_next_place": 435,
    }


@prop
@given(seed=seeds, tier=tiers)
def test_adding_hint_values_work_the_columns(seed: int, tier: int) -> None:
    v = get_generator("add_3digit_regroup").generate(seed, tier).values
    a, b = int(v["a"]), int(v["b"])
    ones = a % 10 + b % 10
    tens = a // 10 % 10 + b // 10 % 10 + ones // 10
    hundreds = a // 100 + b // 100 + tens // 10
    assert (v["ones_total"], v["tens_total"], v["hundreds_total"]) == (ones, tens, hundreds)
    assert ("carry 1 ten" in str(v["ones_line"])) == (ones >= 10)
    assert ("carry 1 hundred" in str(v["tens_line"])) == (tens >= 10)
    assert ("carried hundred" in str(v["hundreds_line"])) == (tens >= 10)
    assert hundreds <= 9


def test_adding_with_carrying_carries_once_twice_and_near_a_thousand() -> None:
    sums = [pair("add_3digit_regroup", s, t) for s in range(600) for t in range(3)]
    carries = {
        (a % 10 + b % 10 >= 10) + (a // 10 % 10 + b // 10 % 10 + (a % 10 + b % 10 >= 10) >= 10)
        for a, b, _ in sums
    }
    assert carries == {1, 2}
    assert any(r >= 950 for _, _, r in sums)


@pytest.mark.parametrize("skill", ADDING)
def test_adding_tiers_use_the_forms_they_name(skill: str) -> None:
    assert {shape(maths(skill, s, 0)[0]) for s in range(200)} == {"# + # = ?"}
    assert any(
        "What is" in prompt(skill, s, 1) and " plus " in prompt(skill, s, 1) for s in range(100)
    )
    assert any(prompt(skill, s, 1).startswith("Add ") for s in range(100))
    assert any("You get" in prompt(skill, s, 1) for s in range(100))
    assert all(len(maths(skill, s, 2)) == 1 for s in range(200))
    assert any(" plus " in prompt(skill, s, 2) for s in range(100))
    assert any(" to " in prompt(skill, s, 2) for s in range(100))


@pytest.mark.parametrize("skill", ADDING)
def test_adding_told_in_places_uses_the_singular_for_one(skill: str) -> None:
    seen: set[str] = set()
    for tier_seed in range(1500):
        v = get_generator(skill).generate(tier_seed, 2).values
        told = str(v["parts"])
        assert not re.search(r"\b1 (hundreds|tens|ones)\b", told), told
        assert not re.search(r"\b0 ", told), told
        seen.add(re.sub(r"\d+", "#", told))
    assert "# hundreds, # tens and # ones" in seen
    assert ("# hundred" in seen) == (skill == "add_3digit_no_regroup")


# --- subtracting -----------------------------------------------------------------------------


@prop
@given(seed=seeds, tier=tiers)
def test_subtracting_without_borrowing_never_borrows(seed: int, tier: int) -> None:
    a, b, r = pair("sub_3digit_no_regroup", seed, tier)
    assert 200 <= a <= 999 and b >= 100 and r == a - b >= 100
    assert all(x >= y for x, y in zip(digits(a), digits(b), strict=True))


@prop
@given(seed=seeds, tier=tiers)
def test_subtracting_with_borrowing_always_borrows(seed: int, tier: int) -> None:
    a, b, r = pair("sub_3digit_regroup", seed, tier)
    assert 200 <= a <= 999 and b >= 100 and r == a - b >= 100
    assert any(x < y for x, y in zip(digits(a), digits(b), strict=True))


@pytest.mark.parametrize("skill", SUBTRACTING)
@prop
@given(seed=seeds, tier=tiers)
def test_subtracting_forms_and_answers(skill: str, seed: int, tier: int) -> None:
    problem = get_generator(skill).generate(seed, tier)
    a, b, r = pair(skill, seed, tier)
    v = problem.values
    assert problem.answer == (b if tier == 2 else r) == v["answer"]
    assert (v["top"], v["bottom"]) == (a, r if tier == 2 else b)
    assert sorted(numbers(skill, seed, tier)) == sorted([a, int(v["bottom"])])
    if tier == 0:
        assert maths(skill, seed, tier) == [f"{a} - {b} = ?"]
    elif tier == 1:
        assert len(maths(skill, seed, tier)) == 2
    else:
        (sentence,) = maths(skill, seed, tier)
        assert shape(sentence) in ("# - ? = #", "# = # - ?")
        assert holds(sentence, b)
    for key in ("top", "bottom"):
        number = int(v[key])
        places = (int(v[f"{key}_hundreds"]), int(v[f"{key}_tens"]), int(v[f"{key}_ones"]))
        assert places == digits(number)


@prop
@given(seed=seeds, tier=tiers)
def test_subtracting_without_borrowing_mistakes_follow_their_rules(seed: int, tier: int) -> None:
    skill = "sub_3digit_no_regroup"
    problem = get_generator(skill).generate(seed, tier)
    top, bottom = int(problem.values["top"]), int(problem.values["bottom"])
    rules = {
        "added_instead": top + bottom,
        "left_out_the_ones": (top // 10 - bottom // 10) * 10,
        "left_out_the_hundreds": top % 100 - bottom % 100,
    }
    assert wrong_answers(skill, seed, tier) == kept(int(problem.answer), rules, floor=1)


@prop
@given(seed=seeds, tier=tiers)
def test_subtracting_with_borrowing_mistakes_follow_their_rules(seed: int, tier: int) -> None:
    skill = "sub_3digit_regroup"
    problem = get_generator(skill).generate(seed, tier)
    top, bottom = int(problem.values["top"]), int(problem.values["bottom"])
    (th, tt, to), (bh, bt, bo) = digits(top), digits(bottom)
    rules = {
        "added_instead": top + bottom,
        "subtracted_backwards": abs(th - bh) * 100 + abs(tt - bt) * 10 + abs(to - bo),
        "forgot_to_lower_the_next_place": top - bottom + 10 * (to < bo) + 100 * (tt < bt),
    }
    assert wrong_answers(skill, seed, tier) == kept(int(problem.answer), rules, floor=1)


def borrow_across_a_zero(a: int, shown: int) -> bool:
    return a // 10 % 10 == 0 and (a % 10 < shown % 10 or shown // 10 % 10 > 0)


@pytest.mark.parametrize("tier", range(3))
def test_borrowing_often_meets_a_zero_in_the_tens_place(tier: int) -> None:
    gen = get_generator("sub_3digit_regroup")
    problems = [gen.generate(seed, tier).values for seed in range(600)]
    zeros = sum(int(v["top_tens"]) == 0 for v in problems)
    across = sum(borrow_across_a_zero(int(v["top"]), int(v["bottom"])) for v in problems)
    assert zeros >= 120, (tier, zeros)
    assert across >= 100, (tier, across)
    classic = {(int(v["top"]), int(v["bottom"])) for v in problems if int(v["top_tens"]) == 0}
    assert len(classic) >= 50


@pytest.mark.parametrize("skill", SUBTRACTING)
@prop
@given(seed=seeds, tier=tiers)
def test_subtracting_worked_columns_give_the_answer(skill: str, seed: int, tier: int) -> None:
    """The three worked lines name the digits of the number the question asks for."""
    problem = get_generator(skill).generate(seed, tier)
    v = problem.values
    lines = [str(v[k]) for k in ("hundreds_line", "tens_line", "ones_line")]
    left = [int(n) for line in lines for n in re.findall(r"leaves? (\d+)", line)]
    assert len(left) == 3, lines
    hundreds, tens, ones = left
    assert hundreds * 100 + tens * 10 + ones == int(v["top"]) - int(v["bottom"])


def test_a_zero_in_the_tens_place_borrows_a_hundred_first() -> None:
    notes = {
        str(get_generator("sub_3digit_regroup").generate(seed, 0).values["first_borrow"])
        for seed in range(600)
    }
    assert any("zero" in note for note in notes)
    assert any("borrow a ten" in note for note in notes)
    assert any("borrow a hundred" in note and "ones are enough" in note for note in notes)


@pytest.mark.parametrize("skill", SUBTRACTING)
def test_subtracting_tiers_use_the_forms_they_name(skill: str) -> None:
    assert {shape(maths(skill, s, 0)[0]) for s in range(200)} == {"# - # = ?"}
    assert any("Take away" in prompt(skill, s, 1) for s in range(100))
    assert any(" minus " in prompt(skill, s, 1) for s in range(100))
    assert any("give away" in prompt(skill, s, 1) for s in range(100))
    assert {shape(maths(skill, s, 2)[0]) for s in range(200)} == {"# - ? = #", "# = # - ?"}


# --- all four --------------------------------------------------------------------------------


@pytest.mark.parametrize("skill", HUNDREDS)
def test_every_tier_has_a_spread_of_answers(skill: str) -> None:
    """Five different answers at least, and no one answer more than 35% of the draws."""
    gen = get_generator(skill)
    for tier in range(3):
        answers = [int(gen.generate(seed, tier).answer) for seed in range(3000)]
        distinct = set(answers)
        assert len(distinct) >= 5, (skill, tier, sorted(distinct))
        top = max(answers.count(a) for a in distinct) / len(answers)
        assert top <= 0.35, (skill, tier, top)


@pytest.mark.parametrize("skill", HUNDREDS)
def test_every_tier_covers_the_whole_range(skill: str) -> None:
    """Tiers differ by form, not by size: each one reaches small and large numbers."""
    gen = get_generator(skill)
    for tier in range(3):
        firsts = [int(gen.generate(seed, tier).values["a"]) for seed in range(1500)]
        assert min(firsts) <= 250 and max(firsts) >= 750, (skill, tier)
        assert len({x // 100 for x in firsts}) >= 7, (skill, tier)


@pytest.mark.parametrize("skill", HUNDREDS)
def test_no_tier_runs_out_of_problems(skill: str) -> None:
    gen = get_generator(skill)
    for tier in range(3):
        assert len({flatten(gen.generate(seed, tier)) for seed in range(5000)}) >= 20, (skill, tier)


@pytest.mark.parametrize("skill", HUNDREDS)
def test_every_tier_names_two_mistakes(skill: str) -> None:
    gen = get_generator(skill)
    for tier in range(3):
        keys = {m.key for seed in range(300) for m in gen.generate(seed, tier).misconceptions}
        assert len(keys) >= 2, (skill, tier, keys)
        assert keys <= set(gen.misconception_keys)


@pytest.mark.parametrize("skill", HUNDREDS)
def test_text_is_short_and_has_no_dash(skill: str) -> None:
    gen = get_generator(skill)
    for tier in range(3):
        for seed in range(300):
            problem = gen.generate(seed, tier)
            spoken = "".join(p.text if isinstance(p, TextPart) else " # " for p in problem.prompt)
            written = [v for v in problem.values.values() if isinstance(v, str)]
            for sentence in reads_like_a_child_text(spoken, written):
                assert len(sentence.split()) <= 12, (skill, tier, seed, sentence)
            for text_value in [spoken, *written]:
                for dash in (chr(0x2014), chr(0x2013), " - ", "--"):
                    assert dash not in text_value, (skill, tier, seed, text_value)
            for text_value in (w for w in written if w.endswith((".", "?", "!"))):
                assert not re.search(r"(^|[.?!] )\d", text_value), (skill, tier, seed, text_value)
