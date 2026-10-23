# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false
"""Batch 3 generators for clock hours, reading a graph, even or odd, comparing to 1000 and
story problems to 100: each form does what its tier says, the answer follows from the
numbers shown, and the named mistakes are the ones the rules give."""

import re

import pytest
from hypothesis import given

from mathquest.engine.generators import get_generator
from mathquest.engine.types import TextPart
from tests.engine.test_generators import (
    flatten,
    kept,
    prompt,
    prop,
    reads_like_a_child_text,
    seeds,
    tiers,
    wrong_answers,
)

BATCH_THREE_REMAINING = (
    "clock_hours",
    "read_data_graphs",
    "even_odd",
    "compare_numbers_1000",
    "word_problems_100",
)


def hour(n: int) -> int:
    return (n - 1) % 12 + 1


def wrong_pairs(skill: str, seed: int, tier: int) -> set[tuple[str, int]]:
    """Every (mistake, answer) the generator names; two mistakes may share a key."""
    problem = get_generator(skill).generate(seed, tier)
    return {(m.key, int(m.answer)) for m in problem.misconceptions}


def expected_pairs(answer: int, rules: list[tuple[str, int]]) -> set[tuple[str, int]]:
    """What the generator keeps of ``rules``: a wrong answer below zero, equal to the answer
    or equal to an earlier one is dropped."""
    out: list[tuple[str, int]] = []
    for key, value in rules:
        if value >= 0 and value != answer and value not in [v for _, v in out]:
            out.append((key, value))
    return set(out)


# --- clock hours ----------------------------------------------------------------------------


def clock_form(text: str) -> tuple[str, int, int]:
    """The form a clock question is told in, the answer it asks for and the hour in it."""
    if m := re.fullmatch(
        r"The short hand points to (\d+)\. The long hand points to 12\. What hour is it\?", text
    ):
        return "hands_hour", int(m[1]), int(m[1])
    if m := re.fullmatch(r"It is (\d+) o'clock now\. What hour will it be in one hour\?", text):
        return "hour_later", hour(int(m[1]) + 1), int(m[1])
    if m := re.fullmatch(
        r"School starts at (\d+) o'clock\. What hour is it one hour before\?", text
    ):
        return "hour_before", hour(int(m[1]) - 1), int(m[1])
    if m := re.fullmatch(
        r"The long hand points to 6\. The short hand is between (\d+) and (\d+)\. "
        r"It is half past what hour\?",
        text,
    ):
        assert int(m[2]) == hour(int(m[1]) + 1)
        return "hands_half_past", int(m[1]), int(m[1])
    if m := re.fullmatch(r"A clock shows (\d+):30\. It is half past what hour\?", text):
        return "digital_half_past", int(m[1]), int(m[1])
    if m := re.fullmatch(
        r"A game starts at half past (\d+)\. It lasts one hour\. "
        r"It ends at half past what hour\?",
        text,
    ):
        return "half_past_game", hour(int(m[1]) + 1), int(m[1])
    if m := re.fullmatch(
        r"A clock shows (\d+):30\. How many minutes after \1 o'clock is that\?", text
    ):
        return "minutes_after_hour", 30, int(m[1])
    if m := re.fullmatch(
        r"The short hand is just past (\d+)\. The long hand points to 6\. "
        r"How many minutes after \1 o'clock is it\?",
        text,
    ):
        return "minutes_from_hands", 30, int(m[1])
    if m := re.fullmatch(
        r"The short hand points to (\d+)\. The long hand points to 12\. "
        r"How many minutes after \1 o'clock is it\?",
        text,
    ):
        return "minutes_from_hands", 0, int(m[1])
    if m := re.fullmatch(
        r"A (walk|film) starts at (\d+):00 and ends at (\d+):(00|30)\. "
        r"How many (half hours is that|minutes long is it)\?",
        text,
    ):
        halves = (int(m[3]) - int(m[2])) * 2 + (1 if m[4] == "30" else 0)
        assert 1 <= halves <= 5
        if m[1] == "walk":
            assert m[5] == "half hours is that"
            return "half_hours_between", halves, int(m[2])
        assert m[5] == "minutes long is it"
        return "minutes_between", halves * 30, int(m[2])
    raise AssertionError(text)


CLOCK_FORMS = (
    {"hands_hour", "hour_later", "hour_before"},
    {"hands_half_past", "digital_half_past", "half_past_game", "minutes_after_hour"},
    {"minutes_from_hands", "half_hours_between", "minutes_between"},
)


@prop
@given(seed=seeds, tier=tiers)
def test_clock_answers_follow_from_the_time_told(seed: int, tier: int) -> None:
    problem = get_generator("clock_hours").generate(seed, tier)
    form, answer, told = clock_form(prompt("clock_hours", seed, tier))
    assert form in CLOCK_FORMS[tier]
    assert problem.answer == answer == problem.values["answer"]
    assert problem.values["hour"] == told
    assert 1 <= told <= 12
    assert str(answer) in str(problem.values["worked"])


@pytest.mark.parametrize("tier", range(3))
def test_each_tier_of_clock_hours_tells_every_form_it_names(tier: int) -> None:
    seen = {clock_form(prompt("clock_hours", seed, tier))[0] for seed in range(600)}
    assert seen == CLOCK_FORMS[tier]


@prop
@given(seed=seeds, tier=tiers)
def test_clock_hours_wrong_answers_are_the_rules_give(seed: int, tier: int) -> None:
    form, answer, told = clock_form(prompt("clock_hours", seed, tier))
    got = wrong_pairs("clock_hours", seed, tier)
    halves = answer // 30 if form == "minutes_between" else answer
    rules: list[tuple[str, int]]
    if form == "hands_hour":
        # One hour off, in a direction the seed picks.
        assert {k for k, _ in got} <= {"gave_the_long_hand_number", "off_by_one_hour"}
        assert all(v in (12, hour(told + 1), hour(told - 1)) for _, v in got)
        if told != 12:
            assert ("gave_the_long_hand_number", 12) in got
        return
    if form in ("hour_later", "half_past_game"):
        rules = [("gave_the_hour", told), ("went_the_wrong_way", hour(told - 1))]
    elif form == "hour_before":
        rules = [("gave_the_hour", told), ("went_the_wrong_way", hour(told + 1))]
    elif form == "hands_half_past":
        rules = [("gave_the_long_hand_number", 6), ("off_by_one_hour", hour(told + 1))]
    elif form == "digital_half_past":
        rules = [("gave_the_minutes", 30), ("off_by_one_hour", hour(told + 1))]
    elif form == "minutes_after_hour":
        rules = [("gave_the_hour", told), ("gave_the_long_hand_number", 6)]
    elif form == "minutes_from_hands":
        rules = [("gave_the_long_hand_number", 6 if answer else 12), ("gave_the_hour", told)]
    elif form == "half_hours_between":
        rules = [("counted_whole_hours", halves // 2), ("gave_the_minutes", halves * 30)]
    else:
        halves = answer // 30
        rules = [("gave_the_half_hours", halves), ("counted_whole_hours", 60 * (halves // 2))]
    assert got == expected_pairs(answer, rules)


def test_clock_hours_tier_zero_answers_cover_every_hour() -> None:
    hours = {clock_form(prompt("clock_hours", seed, 0))[1] for seed in range(600)}
    assert hours == set(range(1, 13))


# --- reading a graph ------------------------------------------------------------------------

GRAPH_ROW = re.compile(r"([A-Z][a-z]+): (\d+)\.")


def graph_counts(text: str) -> dict[str, int]:
    return {name.lower(): int(n) for name, n in GRAPH_ROW.findall(text)}


def graph_form(text: str, counts: dict[str, int]) -> tuple[str, int]:
    """The question a graph is asked and the answer it has."""
    question = text[text.rindex(". ") + 2 :]
    ranked = sorted(counts.values(), reverse=True)
    if m := re.fullmatch(r"How many kids chose (\w+)\?", question):
        return "read_one", counts[m[1]]
    if m := re.fullmatch(r"How many kids are in the (biggest|smallest) group\?", question):
        return "read_extreme", ranked[0] if m[1] == "biggest" else ranked[2]
    if m := re.fullmatch(r"How many more kids chose (\w+) than (\w+)\?", question):
        return "compare_two", counts[m[1]] - counts[m[2]]
    if m := re.fullmatch(r"How many fewer kids chose (\w+) than (\w+)\?", question):
        return "compare_two", counts[m[2]] - counts[m[1]]
    if question == "How many more kids are in the biggest group than the smallest?":
        return "compare_extremes", ranked[0] - ranked[2]
    if question == "How many kids are there in all?":
        return "total_all", sum(ranked)
    if m := re.fullmatch(r"How many kids chose (\w+) or (\w+)\?", question):
        return "total_two", counts[m[1]] + counts[m[2]]
    raise AssertionError(text)


GRAPH_FORMS = (
    {"read_one", "read_extreme"},
    {"compare_two", "compare_extremes"},
    {"total_all", "total_two"},
)


@prop
@given(seed=seeds, tier=tiers)
def test_graph_answers_follow_from_the_table(seed: int, tier: int) -> None:
    problem = get_generator("read_data_graphs").generate(seed, tier)
    text = prompt("read_data_graphs", seed, tier)
    counts = graph_counts(text)
    assert len(counts) == 3 and len(set(counts.values())) == 3
    form, answer = graph_form(text, counts)
    assert form in GRAPH_FORMS[tier]
    assert problem.answer == answer == problem.values["answer"]
    a, b, c = sorted(counts.values(), reverse=True)
    assert (problem.values["a"], problem.values["b"], problem.values["c"]) == (a, b, c)
    assert a > b > c >= 1
    assert a <= (9, 12, 9)[tier]
    if tier == 2:
        assert a + b + c <= 20
    assert str(answer) in str(problem.values["worked"])


@pytest.mark.parametrize("tier", range(3))
def test_each_tier_of_the_graph_asks_the_forms_it_names(tier: int) -> None:
    seen = set()
    for seed in range(400):
        text = prompt("read_data_graphs", seed, tier)
        seen.add(graph_form(text, graph_counts(text))[0])
    assert seen == GRAPH_FORMS[tier]


@prop
@given(seed=seeds, tier=tiers)
def test_graph_wrong_answers_are_the_rules_give(seed: int, tier: int) -> None:
    text = prompt("read_data_graphs", seed, tier)
    counts = graph_counts(text)
    form, answer = graph_form(text, counts)
    a, b, c = sorted(counts.values(), reverse=True)
    question = text[text.rindex(". ") + 2 :]
    named = re.findall(r"chose (\w+) (?:than|or) (\w+)", question)
    pair = named[0] if named else ()
    rules: list[tuple[str, int]]
    if form == "read_one":
        rules = [("read_a_different_group", v) for v in counts.values() if v != answer]
    elif form == "read_extreme":
        rules = [
            ("confused_most_fewest", c if answer == a else a),
            ("read_a_different_group", b),
        ]
    elif form == "compare_extremes":
        rules = [("added_instead", a + c), ("gave_one_count", a), ("gave_one_count", c)]
    elif form == "compare_two":
        x, y = (counts[w] for w in pair)
        rules = [("added_instead", x + y), ("gave_one_count", x), ("gave_one_count", y)]
    elif form == "total_all":
        rules = [("left_out_a_group", a + b), ("subtracted_instead", a - b - c)]
    else:
        x, y = (counts[w] for w in pair)
        rules = [("subtracted_instead", abs(x - y)), ("gave_one_count", max(x, y))]
    assert wrong_pairs("read_data_graphs", seed, tier) == expected_pairs(answer, rules)


# --- even or odd ----------------------------------------------------------------------------

EVEN_ODD_RANGES = ((1, 20), (21, 99), (101, 999))


def parity_form(text: str) -> tuple[str, int, list[int]]:
    """The form, the answer and the numbers shown."""
    shown = [int(n) for n in re.findall(r"\d+", text)]
    if m := re.match(r"Which (?:number )?is (even|odd), ", text):
        want = 0 if m[1] == "even" else 1
        right = [n for n in shown if n % 2 == want]
        assert len(right) == 1, text
        return "which_" + str(len(shown)), right[0], shown
    if m := re.match(r"What is the next (even|odd) number after \d+\?", text):
        want = 0 if m[1] == "even" else 1
        n = shown[0]
        return "next", next(k for k in (n + 1, n + 2) if k % 2 == want), shown
    assert "puts them in pairs. How many are left over?" in text, text
    return "pairs", shown[0] % 2, shown


@prop
@given(seed=seeds, tier=tiers)
def test_even_odd_answers_follow_from_the_numbers(seed: int, tier: int) -> None:
    problem = get_generator("even_odd").generate(seed, tier)
    form, answer, shown = parity_form(prompt("even_odd", seed, tier))
    assert problem.answer == answer == problem.values["answer"]
    lo, hi = EVEN_ODD_RANGES[tier]
    if form.startswith("which"):
        assert len(shown) == int(form[-1]) and len(set(shown)) == len(shown)
        assert all(lo <= n <= hi for n in shown)
        assert str(answer) in str(problem.values["worked"])
    elif form == "next":
        assert lo <= shown[0] <= hi - 2 and answer <= hi
    else:
        assert max(lo, 2) <= shown[0] <= hi


@prop
@given(seed=seeds, tier=tiers)
def test_even_odd_wrong_answers_are_the_rules_give(seed: int, tier: int) -> None:
    form, answer, shown = parity_form(prompt("even_odd", seed, tier))
    rules: list[tuple[str, int]]
    if form.startswith("which"):
        rules = [("picked_the_other_kind", n) for n in shown if n != answer]
    elif form == "next":
        rules = [
            ("gave_the_other_kind", answer + 1),
            ("skipped_one", answer + 2),
            ("gave_the_other_kind", answer - 1),
        ]
    else:
        rules = [("counted_the_pairs", shown[0] // 2), ("mixed_up_left_over", 1 - answer)]
    assert wrong_pairs("even_odd", seed, tier) == expected_pairs(answer, rules)


@pytest.mark.parametrize("tier", range(3))
def test_each_tier_of_even_odd_uses_the_forms_it_names(tier: int) -> None:
    forms = {parity_form(prompt("even_odd", seed, tier))[0] for seed in range(600)}
    assert {"which_2", "which_3", "next"} <= forms
    # Only tiers 0 and 1 tell the pairs story, since hundreds of shells in pairs is silly.
    assert ("pairs" in forms) == (tier in (0, 1))


def test_even_odd_pairs_in_tier_two_share_every_digit_but_the_last() -> None:
    near = 0
    for seed in range(600):
        form, _, shown = parity_form(prompt("even_odd", seed, 2))
        if form == "which_2" and abs(shown[0] - shown[1]) == 1:
            near += 1
    assert near > 100


def test_even_odd_asks_both_kinds_and_both_parities_are_answers() -> None:
    kinds = set()
    answers = set()
    for seed in range(400):
        text = prompt("even_odd", seed, 1)
        if text.startswith("Which"):
            kinds.add("even" if " even" in text else "odd")
            answers.add(parity_form(text)[1] % 2)
    assert kinds == {"even", "odd"} and answers == {0, 1}


# --- comparing to 1000 ----------------------------------------------------------------------


def compare_1000_pair(seed: int, tier: int) -> tuple[int, int, str]:
    problem = get_generator("compare_numbers_1000").generate(seed, tier)
    a, b = int(problem.values["a"]), int(problem.values["b"])
    return a, b, str(problem.values["which"])


def pair_kind(a: int, b: int) -> str:
    lo, hi = sorted((a, b))
    if hi == 1000:
        return "thousand"
    if lo // 100 == hi // 100:
        return "zero" if lo // 10 % 10 == 0 and hi // 10 % 10 > 0 else "same"
    if hi // 100 - lo // 100 >= 2:
        return "far"
    return "cross" if lo % 100 > hi % 100 else "near"


@prop
@given(seed=seeds, tier=tiers)
def test_compare_1000_pairs_and_answers_by_tier(seed: int, tier: int) -> None:
    problem = get_generator("compare_numbers_1000").generate(seed, tier)
    a, b, which = compare_1000_pair(seed, tier)
    assert a != b and 100 <= a <= 1000 and 100 <= b <= 1000
    answer = max(a, b) if which == "bigger" else min(a, b)
    assert problem.answer == answer == problem.values["answer"]
    assert flatten(problem) == f"Which number is {which}, {a} or {b}?"
    kind = pair_kind(a, b)
    if tier == 0:
        assert kind == "far" and max(a, b) < 1000
    elif tier == 1:
        assert kind in ("same", "zero") and max(a, b) // 100 == min(a, b) // 100
    else:
        assert kind in ("cross", "zero", "thousand"), (a, b)
    assert str(answer) in str(problem.values["worked"])


def test_compare_1000_tier_two_tells_each_tricky_kind_and_tier_one_none_of_them() -> None:
    seen = {pair_kind(*compare_1000_pair(s, 2)[:2]) for s in range(600)}
    assert seen == {"cross", "zero", "thousand"}


@prop
@given(seed=seeds, tier=tiers)
def test_compare_1000_wrong_answers_name_the_slip(seed: int, tier: int) -> None:
    a, b, which = compare_1000_pair(seed, tier)
    big, small = max(a, b), min(a, b)
    answer = big if which == "bigger" else small
    other = small if which == "bigger" else big
    if small % 10 > big % 10:
        key = "compared_ones_only"
    elif small // 10 % 10 > big // 10 % 10:
        key = "compared_tens_only"
    else:
        key = "confused_bigger_smaller"
    assert wrong_answers("compare_numbers_1000", seed, tier) == kept(
        answer, {key: other, "gave_the_difference": big - small}
    )


# --- story problems to 100 ------------------------------------------------------------------

STORY_SHAPES = (
    ("add_to", "take_from"),
    ("put_together", "take_apart", "compare_more", "compare_fewer"),
    (
        "take_apart",
        "compare_more",
        "compare_fewer",
        "change_add",
        "change_take",
        "start_add",
        "start_take",
    ),
)
STORY_ADDS = {"add_to", "put_together", "start_take"}


def story_shape_100(text: str) -> str:
    if "Then" in text and "finds" in text:
        return "add_to"
    if "loses" in text:
        return "take_from"
    if " red " in text and "in all?" in text:
        return "put_together"
    if "The rest are blue" in text:
        return "take_apart"
    if "How many more does" in text:
        return "compare_more"
    if "How many fewer does" in text:
        return "compare_fewer"
    if "gets some more" in text:
        return "change_add"
    if "gives some away" in text:
        return "change_take"
    assert "at first?" in text, text
    return "start_add" if "more. Now" in text else "start_take"


@prop
@given(seed=seeds, tier=tiers)
def test_stories_to_100_use_the_numbers_their_shape_needs(seed: int, tier: int) -> None:
    problem = get_generator("word_problems_100").generate(seed, tier)
    text = prompt("word_problems_100", seed, tier)
    shape = story_shape_100(text)
    assert shape in STORY_SHAPES[tier]
    a, b = int(problem.values["a"]), int(problem.values["b"])
    m, n = int(problem.values["m"]), int(problem.values["n"])
    assert 10 <= b <= a and a + b <= 100
    assert 10 <= n <= m - 5 and 30 <= m <= 100
    adds = shape in STORY_ADDS
    told1, told2 = (a, b) if adds else (m, n)
    assert (problem.values["told1"], problem.values["told2"]) == (told1, told2)
    answer = told1 + told2 if adds else told1 - told2
    assert problem.answer == answer == problem.values["answer"]
    assert sorted(int(x) for x in re.findall(r"\d+", text)) == sorted([told1, told2])
    assert 1 <= answer <= 100
    other = told1 - told2 if adds else told1 + told2
    assert wrong_answers("word_problems_100", seed, tier) == kept(
        answer,
        {
            "used_the_other_operation": other,
            "gave_the_first_number": told1,
            "gave_the_second_number": told2,
        },
    )
    assert re.search(rf"\b{answer}\b", str(problem.values["worked"]))


@pytest.mark.parametrize("tier", range(3))
def test_stories_to_100_tell_every_shape_in_their_tier(tier: int) -> None:
    seen = {story_shape_100(prompt("word_problems_100", s, tier)) for s in range(500)}
    assert seen == set(STORY_SHAPES[tier])


def test_stories_to_100_cross_tens_when_adding_and_taking_away() -> None:
    carries = borrows = 0
    for seed in range(600):
        v = get_generator("word_problems_100").generate(seed, 0).values
        text = prompt("word_problems_100", seed, 0)
        if story_shape_100(text) == "add_to":
            carries += int(v["a"]) % 10 + int(v["b"]) % 10 >= 10
        else:
            borrows += int(v["m"]) % 10 < int(v["n"]) % 10
    assert carries > 30 and borrows > 30


# --- all five --------------------------------------------------------------------------------


@pytest.mark.parametrize("skill", BATCH_THREE_REMAINING)
def test_every_remaining_batch_three_tier_has_a_spread_of_answers(skill: str) -> None:
    """Five different answers at least, and no one answer more than 35% of the draws."""
    gen = get_generator(skill)
    for tier in range(3):
        answers = [int(gen.generate(seed, tier).answer) for seed in range(3000)]
        distinct = set(answers)
        assert len(distinct) >= 5, (skill, tier, sorted(distinct))
        top = max(answers.count(a) for a in distinct) / len(answers)
        assert top <= 0.35, (skill, tier, top)


@pytest.mark.parametrize("skill", BATCH_THREE_REMAINING)
def test_no_remaining_batch_three_tier_runs_out_of_problems(skill: str) -> None:
    gen = get_generator(skill)
    for tier in range(3):
        assert len({flatten(gen.generate(seed, tier)) for seed in range(5000)}) >= 20, (skill, tier)


@pytest.mark.parametrize("skill", BATCH_THREE_REMAINING)
def test_every_remaining_batch_three_tier_names_two_mistakes(skill: str) -> None:
    gen = get_generator(skill)
    for tier in range(3):
        keys = {m.key for seed in range(300) for m in gen.generate(seed, tier).misconceptions}
        assert len(keys) >= 2, (skill, tier, keys)
        assert keys <= set(gen.misconception_keys)


@pytest.mark.parametrize("skill", BATCH_THREE_REMAINING)
def test_remaining_batch_three_text_is_short_and_has_no_dash(skill: str) -> None:
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
            for text_value in [spoken, *(w for w in written if w.endswith((".", "?", "!")))]:
                assert not re.search(r"(^|[.?!] )\d", text_value), (skill, tier, seed, text_value)
                assert not re.search(r"\b1 (?!is\b|as\b|has\b|was\b)[a-z]+s\b", text_value), (
                    skill,
                    tier,
                    seed,
                    text_value,
                )


@pytest.mark.parametrize("skill", BATCH_THREE_REMAINING)
@prop
@given(seed=seeds, tier=tiers)
def test_remaining_batch_three_values_name_the_answer(skill: str, seed: int, tier: int) -> None:
    problem = get_generator(skill).generate(seed, tier)
    assert problem.values["answer"] == problem.answer
