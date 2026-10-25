# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false
"""Batch 4 generators: the times tables 2 to 9."""

import re

import pytest
from hypothesis import given

from mathquest.engine.generators import get_generator
from mathquest.engine.generators._groups import each_wrongs, group_wrongs
from mathquest.engine.types import TextPart
from tests.engine.test_generators import (
    kept,
    numbers,
    prompt,
    prop,
    reads_like_a_child_text,
    seeds,
    shape,
    tiers,
    wrong_answers,
)

TABLES = {"mult_2_5": (2, 5), "mult_3_4": (3, 4), "mult_6_7": (6, 7), "mult_8_9": (8, 9)}


def values(skill: str, seed: int, tier: int) -> dict[str, int | str]:
    return dict(get_generator(skill).generate(seed, tier).values)


def swapped(total: int) -> int:
    return int(str(total)[::-1]) if 10 <= total <= 99 and total % 10 else 0


@pytest.mark.parametrize("skill", TABLES)
@prop
@given(seed=seeds, tier=tiers)
def test_a_fact_is_a_table_times_a_number_and_its_mistakes_follow_their_rules(
    skill: str, seed: int, tier: int
) -> None:
    v = values(skill, seed, tier)
    g, s = int(v["g"]), int(v["s"])
    total = g * s
    assert get_generator(skill).generate(seed, tier).answer == total
    allowed = TABLES[skill] if tier == 2 else (TABLES[skill][tier],)
    assert (g in allowed and 2 <= s <= 10) or (s in allowed and 2 <= g <= 10)
    rules = {
        "added_instead": g + s,
        "one_group_too_few": total - s,
        "one_group_too_many": total + s,
        "one_each_too_few": total - g,
        "one_each_too_many": total + g,
    }
    if skill == "mult_8_9" and 9 in (g, s):
        rules["digits_swapped"] = swapped(total)
    assert wrong_answers(skill, seed, tier) == kept(total, rules, floor=1)


def test_the_mistakes_for_seven_times_six_by_hand() -> None:
    """7 times 6 is 42. Read as 7 groups of 6, one group short is 36 and one over is 48; the
    fact next door, 7 times 5 or 7 times 7, is 35 or 49."""
    assert group_wrongs(7, 6) == [
        ("added_instead", 13),
        ("one_group_too_few", 36),
        ("one_group_too_many", 48),
    ]
    assert each_wrongs(7, 6) == [("one_each_too_few", 35), ("one_each_too_many", 49)]
    assert each_wrongs(6, 7) == [("one_each_too_few", 36), ("one_each_too_many", 48)]


def test_a_generated_seven_times_six_names_those_mistakes() -> None:
    problem = next(
        p
        for seed in range(400)
        if (p := get_generator("mult_6_7").generate(seed, 2)).values["g"] == 7
        and p.values["s"] == 6
    )
    assert problem.answer == 42
    assert {int(m.answer) for m in problem.misconceptions} == {13, 36, 48, 35, 49}


@pytest.mark.parametrize("skill", TABLES)
def test_tiers_are_the_first_table_the_second_and_both(skill: str) -> None:
    first, second = TABLES[skill]
    for tier, want in ((0, {first}), (1, {second}), (2, {first, second})):
        used: set[int] = set()
        for seed in range(600):
            v = values(skill, seed, tier)
            g, s = int(v["g"]), int(v["s"])
            hit = {t for t in (first, second) if t in (g, s)}
            assert hit & want, (tier, g, s)
            used |= hit & want
        assert used == want, (skill, tier)


@pytest.mark.parametrize("skill", TABLES)
def test_both_orders_and_the_forms_of_each_tier(skill: str) -> None:
    first, second = TABLES[skill]
    for tier in range(3):
        table = (first, second, first)[tier]
        order = {int(values(skill, s, tier)["g"]) == table for s in range(600)}
        assert order == {True, False}, (skill, tier)
    forms = [{shape(prompt(skill, s, t)) for s in range(1500)} for t in range(3)]
    assert forms[0] == {r"# \times # = ?", r"What is # \times #?"}
    assert forms[1] - forms[0] == {"There are # groups of #. How many are there in all?"}
    assert forms[2] - forms[1] == {"What is # times #?"}
    assert forms[0] <= forms[1] <= forms[2]


@pytest.mark.parametrize("skill", TABLES)
def test_the_question_shows_exactly_the_two_numbers(skill: str) -> None:
    for tier in range(3):
        for seed in range(300):
            v = values(skill, seed, tier)
            assert sorted(numbers(skill, seed, tier)) == sorted([int(v["g"]), int(v["s"])])


@pytest.mark.parametrize("skill", TABLES)
def test_no_missing_factor_and_no_division(skill: str) -> None:
    for tier in range(3):
        for seed in range(300):
            text = prompt(skill, seed, tier)
            assert "?" in text and not re.search(r"= \d|\div|÷|share", text)
            assert not re.match(r"\? \times|\times \?", text)


def test_digits_swapped_is_reachable_only_for_the_nines() -> None:
    gen = get_generator("mult_8_9")
    reached = {
        (int(m.answer), int(p.answer))
        for tier in range(3)
        for seed in range(600)
        for p in [gen.generate(seed, tier)]
        for m in p.misconceptions
        if m.key == "digits_swapped"
    }
    assert (36, 63) in reached and (72, 27) in reached
    for skill in ("mult_2_5", "mult_3_4", "mult_6_7"):
        assert "digits_swapped" not in get_generator(skill).misconception_keys


@pytest.mark.parametrize("skill", TABLES)
def test_every_tier_has_a_spread_of_answers_and_the_top_tier_is_hardest(skill: str) -> None:
    gen = get_generator(skill)
    for tier in range(3):
        answers = [int(gen.generate(seed, tier).answer) for seed in range(3000)]
        distinct = set(answers)
        assert len(distinct) >= 5, (skill, tier, sorted(distinct))
        assert max(answers.count(a) for a in distinct) / len(answers) <= 0.33, (skill, tier)
    assert gen.tier_difficulties[0] < gen.tier_difficulties[1] < gen.tier_difficulties[2]


@pytest.mark.parametrize("skill", TABLES)
def test_every_tier_names_at_least_two_mistakes_and_reaches_every_key(skill: str) -> None:
    gen = get_generator(skill)
    seen: set[str] = set()
    for tier in range(3):
        keys = {m.key for seed in range(600) for m in gen.generate(seed, tier).misconceptions}
        assert keys <= set(gen.misconception_keys)
        assert len(keys) >= 2, (skill, tier)
        seen |= keys
    assert seen == set(gen.misconception_keys)


@pytest.mark.parametrize("skill", TABLES)
def test_no_tier_runs_out_of_problems(skill: str) -> None:
    for tier in range(3):
        keys = {prompt(skill, seed, tier) for seed in range(5000)}
        assert len(keys) >= 20, (skill, tier)


@pytest.mark.parametrize("skill", TABLES)
def test_text_is_short_has_no_dash_and_never_starts_with_a_number(skill: str) -> None:
    gen = get_generator(skill)
    for tier in range(3):
        for seed in range(300):
            problem = gen.generate(seed, tier)
            spoken = "".join(p.text if isinstance(p, TextPart) else " # " for p in problem.prompt)
            written = [v for v in problem.values.values() if isinstance(v, str)]
            for sentence in reads_like_a_child_text(spoken, written):
                assert len(sentence.split()) <= 12, (skill, tier, seed, sentence)
                assert not re.match(r"\d", sentence), (skill, tier, seed, sentence)
                for dash in (chr(0x2014), chr(0x2013), " - ", "--"):
                    assert dash not in sentence


@pytest.mark.parametrize("skill", TABLES)
@prop
@given(seed=seeds, tier=tiers)
def test_deterministic_per_seed_and_tier(skill: str, seed: int, tier: int) -> None:
    gen = get_generator(skill)
    assert gen.generate(seed, tier) == gen.generate(seed, tier)
