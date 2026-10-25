# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false
"""Batch 4 generators: equal groups, arrays and the first multiplying."""

import re

import pytest
from hypothesis import given

from mathquest.engine.generators import get_generator
from mathquest.engine.generators._groups import EACH_KEYS, GROUP_KEYS, each_wrongs, group_wrongs
from mathquest.engine.types import MathPart, TextPart
from tests.engine.test_batch_two_teaching import text_of
from tests.engine.test_generators import (
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

GROUPS = ("equal_groups", "arrays", "mult_as_groups", "mult_0_1_10")


def values(skill: str, seed: int, tier: int) -> dict[str, int | str]:
    return dict(get_generator(skill).generate(seed, tier).values)


# --- equal groups and multiplying groups -----------------------------------------------------


@pytest.mark.parametrize("skill", ["equal_groups", "mult_as_groups"])
@prop
@given(seed=seeds, tier=tiers)
def test_groups_total_and_mistakes_follow_their_rules(skill: str, seed: int, tier: int) -> None:
    v = values(skill, seed, tier)
    g, s = int(v["g"]), int(v["s"])
    assert get_generator(skill).generate(seed, tier).answer == g * s
    rules = {
        "added_instead": g + s,
        "one_group_too_few": g * s - s,
        "one_group_too_many": g * s + s,
    }
    assert wrong_answers(skill, seed, tier) == kept(g * s, rules, floor=1)


def test_the_shared_mistakes_for_groups_and_neighbour_facts_by_hand() -> None:
    """4 groups of 3 is 12: the numbers added, a group short, a group over; the neighbour
    facts 3 times 3 and 5 times 3 are four short and four over."""
    assert group_wrongs(4, 3) == [
        ("added_instead", 7),
        ("one_group_too_few", 9),
        ("one_group_too_many", 15),
    ]
    assert each_wrongs(4, 3) == [("one_each_too_few", 8), ("one_each_too_many", 16)]


def test_every_skill_that_names_the_group_mistakes_declares_the_same_keys() -> None:
    for skill in ("equal_groups", "mult_as_groups"):
        assert get_generator(skill).misconception_keys == GROUP_KEYS
    for skill in ("mult_2_5", "mult_3_4", "mult_6_7", "mult_8_9"):
        assert get_generator(skill).misconception_keys[:5] == (*GROUP_KEYS, *EACH_KEYS)


def test_equal_groups_tiers_narrow_the_size_of_a_group() -> None:
    sizes = [{int(values("equal_groups", s, t)["s"]) for s in range(600)} for t in range(3)]
    assert sizes[0] == {2}
    assert sizes[1] == {3, 4, 5}
    assert sizes[2] == {2, 3, 4, 5, 10}
    counts = {int(values("equal_groups", s, t)["g"]) for s in range(600) for t in range(3)}
    assert counts == set(range(2, 10))


@pytest.mark.parametrize("skill", ["equal_groups", "mult_as_groups"])
def test_stories_never_give_a_person_tables_of_kids(skill: str) -> None:
    """ "Mia has 4 tables. Each table holds 5 kids" is told as "There are 4 tables" instead."""
    seen_tables = 0
    for tier in range(3):
        for seed in range(1200):
            words = text_of(get_generator(skill).generate(seed, tier).prompt)
            assert not re.search(r"has \d+ tables", words), words
            seen_tables += words.startswith("There are") and " tables." in words
    assert seen_tables


def test_equal_groups_never_uses_the_times_sign_and_tells_the_groups() -> None:
    for tier in range(3):
        for seed in range(400):
            v = values("equal_groups", seed, tier)
            g, s = int(v["g"]), int(v["s"])
            text = prompt("equal_groups", seed, tier)
            assert "times" not in text and "\\times" not in text
            if "+" in text:
                assert tier == 2
                assert maths("equal_groups", seed, tier) == [" + ".join([str(s)] * g) + " = ?"]
            else:
                assert numbers("equal_groups", seed, tier) == [g, s]
                assert f"{g} {v['groups']}" in text and f"{s} {v['items']}" in text


def test_equal_groups_sometimes_gives_the_sum_only_in_the_top_tier() -> None:
    for tier in (0, 1):
        assert not any("+" in prompt("equal_groups", s, tier) for s in range(400))
    sums = sum("+" in prompt("equal_groups", s, 2) for s in range(1000))
    assert 200 <= sums <= 400


@prop
@given(seed=seeds, tier=tiers)
def test_multiplying_groups_tell_their_numbers_in_every_form(seed: int, tier: int) -> None:
    v = values("mult_as_groups", seed, tier)
    g, s = int(v["g"]), int(v["s"])
    assert numbers("mult_as_groups", seed, tier) == [g, s]
    assert 2 <= g <= (2, 5, 10)[tier] and 2 <= s <= 9
    if tier == 0:
        assert g == 2


def test_multiplying_groups_use_the_times_sign_after_the_first_tier() -> None:
    forms = {
        tier: {re.sub(r"\d+", "#", prompt("mult_as_groups", s, tier)) for s in range(800)}
        for tier in range(3)
    }
    assert not any("times" in f for f in forms[0])
    assert any(r"\times" in f for f in forms[1]) and any(r"\times" in f for f in forms[2])
    assert any("groups of" in f for f in forms[0] | forms[1] | forms[2])
    assert any(f.startswith("There are # groups of #.") for f in forms[0])
    for tier in range(3):
        for seed in range(300):
            for part in get_generator("mult_as_groups").generate(seed, tier).prompt:
                if isinstance(part, MathPart):
                    assert re.fullmatch(r"\d+ \\times \d+( = \?)?", part.latex)


# --- arrays ----------------------------------------------------------------------------------


@prop
@given(seed=seeds, tier=tiers)
def test_arrays_tell_rows_and_columns_and_follow_their_rules(seed: int, tier: int) -> None:
    problem = get_generator("arrays").generate(seed, tier)
    v = problem.values
    r, c = int(v["r"]), int(v["c"])
    assert 2 <= c <= 5
    if tier < 2:
        assert 2 <= r <= 5
        assert problem.answer == r * c == v["total"]
        assert numbers("arrays", seed, tier) == [r, c]
        rules = {
            "added_rows_and_columns": r + c,
            "counted_one_row": c,
            "one_row_short": r * c - c,
        }
        assert wrong_answers("arrays", seed, tier) == kept(r * c, rules, floor=1)
        assert ("columns" in prompt("arrays", seed, tier)) == (tier == 1)
    else:
        adds = v["change"] == "adds"
        now = r + 1 if adds else r - 1
        assert (2 <= r <= 4) if adds else (3 <= r <= 5)
        assert problem.answer == now * c == v["answer"] and v["now"] == now
        assert numbers("arrays", seed, tier) == [r, c]
        text = prompt("arrays", seed, tier)
        assert ("adds one more row" in text) == adds
        assert ("takes away one row" in text) == (not adds)
        rules = {
            "forgot_the_change": r * c,
            "changed_the_total_by_one": r * c + (1 if adds else -1),
            "wrong_direction": (r - 1 if adds else r + 1) * c,
        }
        assert wrong_answers("arrays", seed, tier) == kept(now * c, rules, floor=1)


def test_arrays_stay_within_the_five_by_five_of_the_standard() -> None:
    for tier in range(3):
        for seed in range(400):
            v = values("arrays", seed, tier)
            assert int(v["c"]) <= 5 and int(v["r"]) <= 5
            assert int(v["answer"]) <= 25


def test_arrays_ask_both_ways_in_the_top_tier() -> None:
    kinds = {values("arrays", s, 2)["change"] for s in range(200)}
    assert kinds == {"adds", "takes away"}


# --- times 0, 1 and 10 -----------------------------------------------------------------------


@prop
@given(seed=seeds, tier=tiers)
def test_zero_one_ten_facts_and_mistakes_follow_their_rules(seed: int, tier: int) -> None:
    problem = get_generator("mult_0_1_10").generate(seed, tier)
    v = problem.values
    a, b, n = int(v["a"]), int(v["b"]), int(v["n"])
    assert 2 <= n <= 10 and problem.answer == a * b == v["answer"]
    assert {a, b} == {n, {"zero": 0, "one": 1, "ten": 10}[str(v["kind"])]}
    assert sorted(numbers("mult_0_1_10", seed, tier)) == sorted([a, b])
    rules: dict[str, int] = {
        "zero": {"answered_the_other_number": n},
        "one": {"added_one": n + 1, "answered_zero": 0},
        "ten": {"dropped_the_zero": n, "put_on_two_zeros": n * 100, "added_ten": n + 10},
    }[str(v["kind"])]
    assert wrong_answers("mult_0_1_10", seed, tier) == kept(int(problem.answer), rules)


def test_zero_one_ten_tiers_use_the_facts_they_name() -> None:
    kinds = [{values("mult_0_1_10", s, t)["kind"] for s in range(600)} for t in range(3)]
    assert kinds == [{"zero", "one"}, {"ten"}, {"zero", "one", "ten"}]


def test_zero_one_ten_comes_in_both_orders_and_three_forms() -> None:
    for tier in range(3):
        firsts = {int(values("mult_0_1_10", s, tier)["a"]) for s in range(600)}
        assert {0, 1, 10} & firsts and firsts - {0, 1, 10}, tier
    shapes = {t: {shape(prompt("mult_0_1_10", s, t)) for s in range(600)} for t in range(3)}
    assert {r"# \times # = ?", r"What is # \times #?"} <= shapes[0]
    assert not any("groups" in f for f in shapes[0])
    assert any("groups of #" in f for f in shapes[1])
    assert any("1 group of" in prompt("mult_0_1_10", s, 2) for s in range(2000))
    assert not any("1 groups" in prompt("mult_0_1_10", s, t) for s in range(600) for t in range(3))


# --- every skill -----------------------------------------------------------------------------


@pytest.mark.parametrize("skill", GROUPS)
def test_every_tier_has_a_spread_of_answers_and_the_top_tier_is_hardest(skill: str) -> None:
    gen = get_generator(skill)
    for tier in range(3):
        answers = [int(gen.generate(seed, tier).answer) for seed in range(3000)]
        distinct = set(answers)
        assert len(distinct) >= 5, (skill, tier, sorted(distinct))
        assert max(answers.count(a) for a in distinct) / len(answers) <= 0.33, (skill, tier)
    assert gen.tier_difficulties[0] < gen.tier_difficulties[1] < gen.tier_difficulties[2]


@pytest.mark.parametrize("skill", GROUPS)
def test_every_tier_names_at_least_two_mistakes_and_reaches_every_key(skill: str) -> None:
    gen = get_generator(skill)
    seen: set[str] = set()
    for tier in range(3):
        keys = {m.key for seed in range(600) for m in gen.generate(seed, tier).misconceptions}
        assert keys <= set(gen.misconception_keys)
        seen |= keys
        assert keys, (skill, tier)
    assert seen == set(gen.misconception_keys)
    assert len(seen) >= 2


@pytest.mark.parametrize("skill", GROUPS)
def test_no_tier_runs_out_of_problems(skill: str) -> None:
    gen = get_generator(skill)
    for tier in range(3):
        keys = {
            "".join(
                p.text if isinstance(p, TextPart) else p.latex
                for p in gen.generate(seed, tier).prompt
            )
            for seed in range(5000)
        }
        assert len(keys) >= 20, (skill, tier)


@pytest.mark.parametrize("skill", GROUPS)
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
            assert not re.search(r"\b1 [a-z]+s\b", spoken)


@pytest.mark.parametrize("skill", GROUPS)
@prop
@given(seed=seeds, tier=tiers)
def test_deterministic_per_seed_and_tier(skill: str, seed: int, tier: int) -> None:
    gen = get_generator(skill)
    assert gen.generate(seed, tier) == gen.generate(seed, tier)
