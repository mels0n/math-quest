# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false
"""Batch 3 arithmetic generators: two-digit subtraction, adding several numbers, ten or a
hundred more or less, and fast facts to 20."""

import re

import pytest
from hypothesis import given

from mathquest.engine.generators import get_generator
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

BATCH_THREE_ARITHMETIC = (
    "sub_2digit_no_regroup",
    "sub_2digit_regroup",
    "add_several_2digit",
    "mental_add_10_100",
    "fluency_within_20",
)
SUBTRACTION = ("sub_2digit_no_regroup", "sub_2digit_regroup")


# --- two-digit subtraction ------------------------------------------------------------------


def sub_numbers(skill: str, seed: int, tier: int) -> tuple[int, int, int]:
    """The top number, the amount taken away and what is left, whatever the form hides."""
    v = get_generator(skill).generate(seed, tier).values
    return int(v["a"]), int(v["b"]), int(v["r"])


@prop
@given(seed=seeds, tier=tiers)
def test_subtraction_without_borrowing_never_borrows(seed: int, tier: int) -> None:
    a, b, r = sub_numbers("sub_2digit_no_regroup", seed, tier)
    assert 20 <= a <= 99 and 10 <= b <= a and r == a - b >= 1
    assert a % 10 >= b % 10 and a // 10 >= b // 10


@prop
@given(seed=seeds, tier=tiers)
def test_subtraction_with_borrowing_always_borrows(seed: int, tier: int) -> None:
    a, b, r = sub_numbers("sub_2digit_regroup", seed, tier)
    assert 20 <= a <= 99 and 10 <= b < a and r == a - b >= 1
    assert a % 10 < b % 10 and a // 10 > b // 10


@pytest.mark.parametrize("skill", SUBTRACTION)
@prop
@given(seed=seeds, tier=tiers)
def test_subtraction_forms_and_answers(skill: str, seed: int, tier: int) -> None:
    problem = get_generator(skill).generate(seed, tier)
    a, b, r = sub_numbers(skill, seed, tier)
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
        assert int(v[f"{key}_tens"]) * 10 + int(v[f"{key}_ones"]) == number


@prop
@given(seed=seeds, tier=tiers)
def test_subtraction_without_borrowing_mistakes_follow_their_rules(seed: int, tier: int) -> None:
    problem = get_generator("sub_2digit_no_regroup").generate(seed, tier)
    top, bottom = int(problem.values["top"]), int(problem.values["bottom"])
    rules = {
        "added_instead": top + bottom,
        "left_out_the_ones": (top // 10 - bottom // 10) * 10,
        "left_out_the_tens": top % 10 - bottom % 10,
    }
    assert wrong_answers("sub_2digit_no_regroup", seed, tier) == kept(
        int(problem.answer), rules, floor=1
    )


@prop
@given(seed=seeds, tier=tiers)
def test_subtraction_with_borrowing_mistakes_follow_their_rules(seed: int, tier: int) -> None:
    problem = get_generator("sub_2digit_regroup").generate(seed, tier)
    top, bottom = int(problem.values["top"]), int(problem.values["bottom"])
    answer = int(problem.answer)
    rules = {
        "added_instead": top + bottom,
        "subtracted_backwards": (top // 10 - bottom // 10) * 10 + (bottom % 10 - top % 10),
        "forgot_to_lower_the_tens": answer + 10,
    }
    assert wrong_answers("sub_2digit_regroup", seed, tier) == kept(answer, rules, floor=1)


def test_borrowing_often_meets_a_zero_in_the_ones_place() -> None:
    gen = get_generator("sub_2digit_regroup")
    for tier in range(3):
        zeros = sum(int(gen.generate(seed, tier).values["a"]) % 10 == 0 for seed in range(600))
        assert zeros >= 60, (tier, zeros)


@pytest.mark.parametrize("skill", SUBTRACTION)
def test_subtraction_tiers_use_the_forms_they_name(skill: str) -> None:
    assert {shape(maths(skill, s, 0)[0]) for s in range(200)} == {"# - # = ?"}
    assert any("Take away" in prompt(skill, s, 1) for s in range(100))
    assert any(" minus " in prompt(skill, s, 1) for s in range(100))
    assert any("give away" in prompt(skill, s, 1) for s in range(100))
    assert {shape(maths(skill, s, 2)[0]) for s in range(200)} == {"# - ? = #", "# = # - ?"}


# --- adding several numbers ------------------------------------------------------------------


def several(seed: int, tier: int) -> list[int]:
    values = get_generator("add_several_2digit").generate(seed, tier).values
    return [int(values[name]) for name in "abcd"[: 4 if tier == 1 else 3]]


@prop
@given(seed=seeds, tier=tiers)
def test_adding_several_numbers_by_tier(seed: int, tier: int) -> None:
    problem = get_generator("add_several_2digit").generate(seed, tier)
    nums = several(seed, tier)
    total = int(problem.answer)
    assert len(nums) == (4 if tier == 1 else 3)
    assert all(10 <= n <= 99 for n in nums)
    assert sum(nums) == total == int(str(problem.values["total"]))
    assert numbers("add_several_2digit", seed, tier) == nums
    if tier == 0:
        assert 40 <= total <= 99
    elif tier == 1:
        assert 50 <= total <= 99
    else:
        assert 101 <= total <= 297
    assert str(problem.values["nums"]).replace(" and ", ", ").split(", ") == [str(n) for n in nums]


@prop
@given(seed=seeds, tier=tiers)
def test_adding_several_numbers_mistakes_follow_their_rules(seed: int, tier: int) -> None:
    problem = get_generator("add_several_2digit").generate(seed, tier)
    nums = several(seed, tier)
    total = int(problem.answer)
    carry = sum(n % 10 for n in nums) // 10
    rules = {
        "left_out_the_last": total - nums[-1],
        "forgot_the_carry": total - 10 * carry,
        "carried_one_ten": total - 10 * (carry - 1) if carry >= 2 else total,
        "dropped_the_hundred": total - 100,
    }
    assert wrong_answers("add_several_2digit", seed, tier) == kept(total, rules, floor=1)


@prop
@given(seed=seeds, tier=tiers)
def test_adding_several_numbers_hint_values_work_the_columns(seed: int, tier: int) -> None:
    v = get_generator("add_several_2digit").generate(seed, tier).values
    nums = several(seed, tier)
    ones = sum(n % 10 for n in nums)
    assert int(str(v["ones_total"])) == ones
    assert v["count"] == ("four" if tier == 1 else "three")
    # The carry is only talked about when there is one, and a hundred only when tens pass 9.
    assert bool(v["carry_note"]) == (ones >= 10)
    tens = sum(n // 10 for n in nums) + ones // 10
    assert f"make {tens} tens" in str(v["tens_line"])
    assert bool(v["hundreds_note"]) == (tens >= 10)
    assert (v["first_tens"], v["first_ones"]) == (nums[0] // 10, nums[0] % 10)


def test_hundreds_notes_say_the_hundreds_and_tens_that_tens_make() -> None:
    notes = {
        str(get_generator("add_several_2digit").generate(seed, 2).values["hundreds_note"])
        for seed in range(2000)
    }
    assert "That is 1 hundred and 2 tens. " in notes
    assert "That is 1 hundred. " in notes
    assert "That is 1 hundred and 1 ten. " in notes
    assert "That is 2 hundreds and 1 ten. " in notes
    assert not any(re.search(r"\b1 (hundreds|tens)\b", note) for note in notes)


# --- ten or a hundred more or less ------------------------------------------------------------


@prop
@given(seed=seeds, tier=tiers)
def test_ten_or_a_hundred_by_tier(seed: int, tier: int) -> None:
    problem = get_generator("mental_add_10_100").generate(seed, tier)
    v = problem.values
    n, answer = int(v["n"]), int(problem.answer)
    step = 10 if v["step_word"] == "ten" else 100
    assert v["place"] == ("tens" if step == 10 else "hundreds")
    assert v["other_place"] == ("hundreds" if step == 10 else "tens")
    assert v["step_say"] == ("ten" if step == 10 else "one hundred")
    assert abs(answer - n) == step and 100 <= answer <= 1000 and 100 <= n <= 1000
    assert v["dir"] == ("up" if answer > n else "down")
    assert v["way"] == ("more" if answer > n else "less")
    assert n == int(v["n_hundreds"]) * 100 + int(v["n_tens"]) * 10 + int(v["n_ones"])
    assert v["digit"] == (n // step) % 10
    if tier == 0:
        assert step == 10
    elif tier == 1:
        assert step == 100
    sentence = maths("mental_add_10_100", seed, tier)
    if prompt("mental_add_10_100", seed, tier).startswith("Find the missing number."):
        assert tier == 2 and "?" in sentence[0]
        assert holds(sentence[0], answer)
    else:
        assert sorted(numbers("mental_add_10_100", seed, tier)) == sorted([n, step])


@prop
@given(seed=seeds, tier=tiers)
def test_ten_or_a_hundred_mistakes_follow_their_rules(seed: int, tier: int) -> None:
    problem = get_generator("mental_add_10_100").generate(seed, tier)
    n, answer = int(problem.values["n"]), int(problem.answer)
    move = answer - n
    sign = 1 if move > 0 else -1
    other = 100 if abs(move) == 10 else 10
    rules = {
        "wrong_direction": n - move,
        "used_the_other_step": n + sign * other,
        "changed_the_ones": n + sign,
    }
    assert wrong_answers("mental_add_10_100", seed, tier) == kept(answer, rules, floor=1)


def test_ten_or_a_hundred_tiers_use_the_forms_they_name() -> None:
    def forms(tier: int) -> set[str]:
        return {re.sub(r"\d+", "#", prompt("mental_add_10_100", s, tier)) for s in range(1500)}

    plain = {
        "What is # more than #?",
        "What is # less than #?",
        "Find # more than #.",
        "Find # less than #.",
        "What number is # more than #?",
        "What number is # less than #?",
        "# + # = ?",
        "# - # = ?",
    }
    assert forms(0) == forms(1) == plain
    hidden = {
        "Find the missing number. ? + # = #",
        "Find the missing number. # + ? = #",
        "Find the missing number. ? - # = #",
        "Find the missing number. # = ? - #",
    }
    assert forms(2) == plain | hidden
    gen = get_generator("mental_add_10_100")
    assert {gen.generate(s, 2).values["step_word"] for s in range(200)} == {"ten", "hundred"}


def test_a_digit_that_wraps_names_the_next_place() -> None:
    gen = get_generator("mental_add_10_100")
    for seed in range(600):
        v = gen.generate(seed, 2).values
        wraps = (v["digit"] == 9 and v["dir"] == "up") or (v["digit"] == 0 and v["dir"] == "down")
        assert bool(v["wrap_note"]) == wraps


# --- fast facts to 20 -------------------------------------------------------------------------


@prop
@given(seed=seeds, tier=tiers)
def test_fast_facts_by_tier(seed: int, tier: int) -> None:
    problem = get_generator("fluency_within_20").generate(seed, tier)
    (sentence,) = maths("fluency_within_20", seed, tier)
    a, b = int(problem.values["a"]), int(problem.values["b"])
    answer = int(problem.answer)
    adding = "+" in sentence
    assert adding == (tier == 0) or tier == 2
    if adding:
        assert 1 <= a <= 10 and 1 <= b <= 10 and answer == a + b <= 20
        assert sentence in (f"{a} + {b} = ?", f"{b} + {a} = ?")
        rules = {
            "subtracted_instead": abs(a - b),
            "one_too_few": answer - 1,
            "one_too_many": answer + 1,
        }
    else:
        assert 2 <= a <= 20 and 1 <= b < a and answer == a - b >= 1
        assert sentence == f"{a} - {b} = ?"
        rules = {
            "added_instead": a + b,
            "one_too_few": answer - 1,
            "one_too_many": answer + 1,
        }
    assert (problem.values["top"], problem.values["take"]) == (a, b)
    assert answer == problem.values["answer"]
    assert wrong_answers("fluency_within_20", seed, tier) == kept(answer, rules, floor=1)


def test_fast_fact_tiers_hold_what_they_name() -> None:
    gen = get_generator("fluency_within_20")
    ops = [{"+" in maths("fluency_within_20", s, t)[0] for s in range(300)} for t in range(3)]
    assert ops == [{True}, {False}, {True, False}]
    crossing = sum(
        int(gen.generate(s, 1).values["a"]) % 10 < int(gen.generate(s, 1).values["b"])
        for s in range(300)
    )
    assert crossing >= 60


@pytest.mark.parametrize("tier", range(3))
def test_fast_fact_worked_lines_name_the_answer(tier: int) -> None:
    gen = get_generator("fluency_within_20")
    kinds: set[str] = set()
    for seed in range(400):
        problem = gen.generate(seed, tier)
        worked = str(problem.values["worked"])
        answer = int(problem.answer)
        a, b = int(problem.values["a"]), int(problem.values["b"])
        adding = "+" in maths("fluency_within_20", seed, tier)[0]
        if worked.startswith("This is a double"):
            assert adding and a == b and f"is {answer}" in worked
        elif worked.startswith("Double"):
            assert adding and abs(a - b) == 1 and f"is {2 * min(a, b)}" in worked
        elif worked.startswith("Ten and"):
            assert adding and 10 in (a, b) and f"make {answer}" in worked
        elif worked.startswith("Make ten"):
            assert adding and answer > 10 and f"make {answer}" in worked
        elif worked.startswith("Start at"):
            assert adding and answer <= 10
        elif worked.startswith("Count back"):
            ones = a % 10
            assert not adding and 11 <= a <= 19 and ones < b < 10
            assert f"{ones} to reach ten" in worked and f"{b - ones} more" in worked
        elif worked.startswith("Ten less"):
            assert not adding and b == 10 and worked == f"Ten less than {a} is {answer}."
        else:
            assert not adding and worked == f"Think about {b} and {answer}. They make {a}."
        kinds.add(worked.split(" ")[0])
    assert len(kinds) >= 2


# --- all five --------------------------------------------------------------------------------


@pytest.mark.parametrize("skill", BATCH_THREE_ARITHMETIC)
def test_every_batch_three_arithmetic_tier_has_a_spread_of_answers(skill: str) -> None:
    """Five different answers at least, and no one answer more than 35% of the draws."""
    gen = get_generator(skill)
    for tier in range(3):
        answers = [int(gen.generate(seed, tier).answer) for seed in range(3000)]
        distinct = set(answers)
        assert len(distinct) >= 5, (skill, tier, sorted(distinct))
        top = max(answers.count(a) for a in distinct) / len(answers)
        assert top <= 0.35, (skill, tier, top)


@pytest.mark.parametrize("skill", BATCH_THREE_ARITHMETIC)
def test_no_batch_three_arithmetic_tier_runs_out_of_problems(skill: str) -> None:
    gen = get_generator(skill)
    for tier in range(3):
        assert len({flatten(gen.generate(seed, tier)) for seed in range(5000)}) >= 20, (skill, tier)


@pytest.mark.parametrize("skill", BATCH_THREE_ARITHMETIC)
def test_every_batch_three_arithmetic_tier_names_two_mistakes(skill: str) -> None:
    gen = get_generator(skill)
    for tier in range(3):
        keys = {m.key for seed in range(300) for m in gen.generate(seed, tier).misconceptions}
        assert len(keys) >= 2, (skill, tier, keys)
        assert keys <= set(gen.misconception_keys)


@pytest.mark.parametrize("skill", BATCH_THREE_ARITHMETIC)
def test_batch_three_arithmetic_text_is_short_and_has_no_dash(skill: str) -> None:
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
            for text_value in (w for w in written if w.endswith((".", "?", "!"))):
                assert not re.search(r"(^|[.?!] )\d", text_value), (skill, tier, seed, text_value)


@pytest.mark.parametrize(
    "skill",
    ("sub_2digit_no_regroup", "sub_2digit_regroup", "mental_add_10_100", "fluency_within_20"),
)
@prop
@given(seed=seeds, tier=tiers)
def test_batch_three_arithmetic_values_name_the_answer(skill: str, seed: int, tier: int) -> None:
    problem = get_generator(skill).generate(seed, tier)
    assert problem.values["answer"] == problem.answer


@prop
@given(seed=seeds, tier=tiers)
def test_fast_fact_values_name_the_numbers_in_the_order_the_sentence_shows_them(
    seed: int, tier: int
) -> None:
    """The explanation marks the first number of the fact and the hint reads "a and b", so
    both follow the sentence, not the order the pair was drawn in."""
    values = get_generator("fluency_within_20").generate(seed, tier).values
    (sentence,) = maths("fluency_within_20", seed, tier)
    first, second = (int(n) for n in re.findall(r"\d+", sentence.split("=")[0]))
    assert (values["a"], values["b"]) == (first, second) == (values["top"], values["take"])


def test_the_carry_note_counts_tens_and_a_single_ten_is_singular() -> None:
    seen: set[tuple[int, str]] = set()
    for tier in range(3):
        for seed in range(400):
            note = str(
                get_generator("add_several_2digit").generate(seed, tier).values["carry_note"]
            )
            if note:
                m = re.fullmatch(
                    r"Keep \d+ in the ones place\. Carry (\d+) (tens?) to the tens place\. ", note
                )
                assert m, note
                seen.add((int(m[1]), m[2]))
    assert {word for count, word in seen if count == 1} == {"ten"}
    assert {word for count, word in seen if count > 1} == {"tens"}


@pytest.mark.parametrize("tier", range(3))
def test_no_borrowing_subtraction_never_starts_below_20_or_takes_one_digit(tier: int) -> None:
    """The lesson's examples start below 20 or take a one-digit number, so a replayed lesson
    never shows a problem the skill asks (the lint cannot read place-value words)."""
    for seed in range(400):
        values = get_generator("sub_2digit_no_regroup").generate(seed, tier).values
        assert int(values["a"]) >= 20 and int(values["b"]) >= 10
