# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false
"""Teaching content and banks of the five batch 3 skills built after the arithmetic ones:
complete, renders for every problem, keeps to short sentences, tells each story or graph with
the numbers its tier makes, and has banks whose every answer follows from the numbers shown."""

import re
from collections import Counter
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

import pytest

from mathquest.engine.bank import items_for_tier, pick_item
from mathquest.engine.catalog import load_catalog
from mathquest.engine.content.coverage import skill_coverage
from mathquest.engine.content.schema import BankItem, Part, WordTemplate
from mathquest.engine.teaching import (
    render_explanations,
    render_feedback,
    render_hints,
    render_lesson,
)
from mathquest.engine.templates import plain
from tests.engine.test_batch_three_arithmetic_teaching import sentences
from tests.engine.test_batch_two_teaching import EXPRESSIONS, KEYWORDS, text_of
from tests.engine.test_generators import flatten
from tests.engine.test_remaining_batch_three_generators import (
    BATCH_THREE_REMAINING,
    STORY_SHAPES,
    pair_kind,
)

CONTENT = Path(__file__).resolve().parents[2] / "content"
CATALOG = load_catalog(CONTENT, "k8-core")
PACK = CATALOG.pack
SEEDS = 60


@pytest.mark.parametrize("skill_id", BATCH_THREE_REMAINING)
def test_skill_meets_every_coverage_target(skill_id: str) -> None:
    source = CATALOG.source(skill_id)
    coverage = skill_coverage(PACK, source.skill, source.generator)
    assert coverage.gaps == ()
    assert coverage.misconceptions >= 2
    assert coverage.feedback == coverage.misconceptions


@pytest.mark.parametrize("skill_id", BATCH_THREE_REMAINING)
def test_lesson_has_screens_a_worked_example_and_a_try_it(skill_id: str) -> None:
    lesson = render_lesson(PACK.lessons[skill_id])
    assert 2 <= len(lesson.screens) <= 4
    assert lesson.worked_steps
    assert lesson.try_it_tier == 0


@pytest.mark.parametrize("skill_id", BATCH_THREE_REMAINING)
def test_hints_feedback_and_explanations_render_and_the_last_hint_names_the_answer(
    skill_id: str,
) -> None:
    source = CATALOG.source(skill_id)
    explanations = PACK.explanations[skill_id]
    for tier in range(len(source.tier_difficulties)):
        for seed in range(SEEDS):
            problem = source.generate(seed, tier)
            hints = [plain(h) for h in render_hints(PACK.hints[skill_id], problem)]
            assert len(hints) == 3
            assert re.search(rf"\b{problem.answer}\b", hints[2]), (tier, seed, hints[2])
            assert len(render_explanations(explanations, problem)) >= 3
            for wrong in problem.misconceptions:
                feedback = render_feedback(explanations, problem, wrong.key)
                assert feedback is not None, (skill_id, wrong.key)
                assert f"= {problem.answer}" not in plain(feedback)


@pytest.mark.parametrize("skill_id", BATCH_THREE_REMAINING)
def test_rendered_help_keeps_to_twelve_words_a_sentence_and_has_no_dash(skill_id: str) -> None:
    """The lint counts a template as written; a child reads it filled in."""
    source = CATALOG.source(skill_id)
    explanations = PACK.explanations[skill_id]
    for tier in range(len(source.tier_difficulties)):
        for seed in range(SEEDS):
            problem = source.generate(seed, tier)
            shown = [plain(h) for h in render_hints(PACK.hints[skill_id], problem)]
            shown += [plain(a.body) for a in render_explanations(explanations, problem)]
            for wrong in problem.misconceptions:
                feedback = render_feedback(explanations, problem, wrong.key)
                assert feedback is not None
                shown.append(plain(feedback))
            for text in shown:
                for dash in (chr(0x2014), chr(0x2013), " - ", "--"):
                    assert dash not in text, (skill_id, tier, seed, text)
                for sentence in sentences(text):
                    assert len(sentence.split()) <= 12, (skill_id, tier, seed, sentence)
                    assert not re.match(r"\d", sentence), (skill_id, tier, seed, sentence)


@pytest.mark.parametrize("skill_id", BATCH_THREE_REMAINING)
def test_hints_before_the_last_show_no_digit_of_the_working(skill_id: str) -> None:
    """Hints 1 and 2 may name the numbers of the question and little else, so that a number
    that happens to be the answer cannot slip in."""
    source = CATALOG.source(skill_id)
    for tier in range(len(source.tier_difficulties)):
        for seed in range(SEEDS):
            problem = source.generate(seed, tier)
            hints = [plain(h) for h in render_hints(PACK.hints[skill_id], problem)]
            shown = {int(n) for n in re.findall(r"\d+", flatten(problem))}
            answer = int(problem.answer)
            for hint in hints[:2]:
                for number in re.findall(r"\d+", hint):
                    assert int(number) != answer or answer in shown, (tier, seed, hint)


def test_the_two_choice_skills_are_typed_and_serve_a_bank_beside_the_generator() -> None:
    """ADR-0027: a lesson's try-it is typed, so neither skill is a choice skill."""
    for skill_id in ("even_odd", "compare_numbers_1000"):
        skill = PACK.skills[skill_id]
        assert skill.keypad == "numpad" and skill.banked
        assert 0 < skill.bank_share < 1


# --- word templates ---------------------------------------------------------------------------


def templates(skill_id: str) -> tuple[WordTemplate, ...]:
    return PACK.word_problems[skill_id].templates


def test_graph_stories_compute_their_own_answer_for_the_tier_they_serve() -> None:
    found = templates("read_data_graphs")
    assert len(found) >= 15
    assert len({t.id for t in found}) == len(found)
    expressions = {"read": "abc", "compare": "-", "total": "+"}
    for template in found:
        kind = template.id.split("_", 1)[0]
        tier = {"read": 0, "compare": 1, "total": 2}[kind]
        assert template.tiers == (tier,), template.id
        assert template.answer_from == "expression"
        expression = template.expression or ""
        if kind == "read":
            assert expression in ("a", "b", "c"), template.id
        else:
            assert expressions[kind] in expression, template.id
        for name in "abc":
            assert "{" + name + "}" in template.text_template, (template.id, name)
    assert {t.tiers[0] for t in found if t.tiers} == {0, 1, 2}
    per_tier = Counter(t.tiers[0] for t in found if t.tiers)
    assert min(per_tier.values()) >= 5


GRAPH_ANSWERS: dict[str, Callable[[dict[str, int]], int]] = {
    "read_votes": lambda r: r["pears"],
    "read_pets": lambda r: r["dogs"],
    "read_cars": lambda r: r["red"],
    "read_biggest": lambda r: max(r.values()),
    "read_smallest": lambda r: min(r.values()),
    "compare_fruit": lambda r: r["apples"] - r["pears"],
    "compare_fewer": lambda r: r["cats"] - r["fish"],
    "compare_days": lambda r: r["tuesday"] - r["wednesday"],
    "compare_shells": lambda r: r["white"] - r["pink"],
    "compare_ride": lambda r: r["bus"] - r["bike"],
    "total_game": lambda r: sum(r.values()),
    "total_pies": lambda r: r["apple"] + r["peach"],
    "total_cars": lambda r: r["blue"] + r["green"],
    "total_toys": lambda r: sum(r.values()),
    "total_stories": lambda r: r["pirates"] + r["robots"],
}


def test_graph_stories_answer_the_question_they_ask_about_the_table_they_show() -> None:
    """Each story shows three counts, and what its question names is read from the table
    in the story itself, so a mismatch between words and expression shows here."""
    source = CATALOG.source("read_data_graphs")
    assert set(GRAPH_ANSWERS) == {t.id for t in templates("read_data_graphs")}
    for template in templates("read_data_graphs"):
        tier = (template.tiers or (0,))[0]
        for seed in range(80):
            problem = source.generate(seed, tier, "word", template.id)
            text = text_of(problem.prompt)
            a, b, c = (int(problem.values[k]) for k in "abc")
            rows = {
                m[0].lower(): int(m[1])
                for m in re.findall(r"([A-Z][a-z]*(?: [a-z]+)?): (\d+)", text)
            }
            assert sorted(rows.values()) == sorted([a, b, c]), (template.id, text)
            expected = GRAPH_ANSWERS[template.id](rows)
            assert problem.answer == expected, (template.id, text)
            assert expected >= 1
            for sentence in sentences(text):
                assert len(sentence.split()) <= 12, (template.id, sentence)
                assert not re.match(r"\d", sentence), (template.id, sentence)


STORY_EXPRESSIONS = EXPRESSIONS


def story_shape(template_id: str) -> str:
    for shape in sorted(STORY_EXPRESSIONS, key=len, reverse=True):
        if template_id.startswith(shape + "_"):
            return shape
    raise AssertionError(template_id)


STORY_KEYWORDS = {
    **KEYWORDS,
    "add_to": ("more",),
    "take_from": ("get out", "gives", "left"),
    "put_together": ("in all", "Both", "together"),
    "take_apart": ("The rest",),
    "change_add": ("some more", "adds some more"),
    "change_take": ("some", "Some"),
    "start_add": ("at first",),
    "start_take": ("at first",),
}


def test_stories_to_100_compute_the_answer_their_shape_asks_for() -> None:
    shapes: Counter[str] = Counter()
    found = templates("word_problems_100")
    assert len(found) >= 15 and len({t.id for t in found}) == len(found)
    for template in found:
        shape = story_shape(template.id)
        shapes[shape] += 1
        assert template.answer_from == "expression"
        assert template.expression == STORY_EXPRESSIONS[shape], template.id
        assert any(k in template.text_template for k in STORY_KEYWORDS[shape]), template.id
    assert set(shapes) == set(STORY_EXPRESSIONS)
    assert max(shapes.values()) <= 2


def test_story_templates_serve_every_tier_their_shape_is_told_in() -> None:
    for template in templates("word_problems_100"):
        shape = story_shape(template.id)
        expected = tuple(t for t in range(3) if shape in STORY_SHAPES[t])
        assert template.tiers == expected, template.id
    source = CATALOG.source("word_problems_100")
    for tier in range(3):
        served = set()
        for seed in range(300):
            problem = source.generate(seed, tier, "word")
            assert problem.template_id is not None
            served.add(story_shape(problem.template_id))
        assert served == set(STORY_SHAPES[tier])


def test_story_answers_follow_the_numbers_told_and_stay_within_100() -> None:
    source = CATALOG.source("word_problems_100")
    for template in templates("word_problems_100"):
        for tier in template.tiers or ():
            for seed in range(80):
                problem = source.generate(seed, tier, "word", template.id)
                adds = STORY_EXPRESSIONS[story_shape(template.id)] == "a + b"
                a, b = (int(problem.values[k]) for k in (("a", "b") if adds else ("m", "n")))
                shown = [int(n) for n in re.findall(r"\d+", text_of(problem.prompt))]
                assert sorted(shown) == sorted([a, b]), (template.id, shown, a, b)
                expected = a + b if adds else a - b
                assert problem.answer == expected
                assert 1 <= expected <= 100


def test_rendered_stories_to_100_keep_to_twelve_words_and_agree_with_one() -> None:
    """The lint counts a template's source, where ``{obj}`` is one word; a child reads the
    filled-in sentence, so count that."""
    source = CATALOG.source("word_problems_100")
    for template in templates("word_problems_100"):
        for tier in template.tiers or ():
            for seed in range(SEEDS):
                problem = source.generate(seed, tier, "word", template.id)
                text = text_of(problem.prompt)
                assert not re.search(r"\b1 (?!is\b|as\b|has\b|was\b)[a-z]+s\b", text), (
                    template.id,
                    text,
                )
                for sentence in sentences(text):
                    assert len(sentence.split()) <= 12, (template.id, sentence)
                    assert not re.match(r"\d", sentence), (template.id, sentence)


# --- the two banks ----------------------------------------------------------------------------


def joined(parts: tuple[Part, ...]) -> str:
    return "".join(p.value for p in parts)


def math_numbers(parts: tuple[Part, ...]) -> list[int]:
    return [int(p.value) for p in parts if p.kind == "math" and p.value.isdigit()]


@dataclass(frozen=True)
class Decoded:
    """What a bank item's answer must be, read from the numbers and words it shows."""

    index: int
    a: int | None = None
    b: int | None = None


def parity_of(kind: str) -> int:
    return 0 if kind == "even" else 1


def decode_even_odd(item: BankItem) -> int:
    assert item.choices is not None
    choices = [joined(c) for c in item.choices]
    text = joined(item.prompt)
    numbers = math_numbers(item.prompt)
    if all(c.isdigit() for c in choices):
        values = [int(c) for c in choices]
        if m := re.search(r"next (even|odd)", text):
            want, n = parity_of(m[1]), max(numbers)
            return values.index(next(k for k in (n + 1, n + 2) if k % 2 == want))
        if "comes next" in text:
            n = max(numbers)  # the odd numbers in order: the next odd number
            return values.index(next(k for k in (n + 1, n + 2) if k % 2 == 1))
        if "Count back from" in text:
            n = numbers[0]
            return values.index(next(k for k in (n - 1, n - 2) if k % 2 == 1))
        if "right after" in text:
            n = max(numbers)
            return values.index(next(k for k in (n + 1, n + 2) if k % 2 == 1))
        if "not even" in text or "left over" in text or re.search(r"\bodd\b", text):
            want = 1
        else:
            assert "even" in text or "equal groups" in text, text
            want = 0
        right = [i for i, v in enumerate(values) if v % 2 == want]
        assert len(right) == 1, item.id
        return right[0]
    if set(choices) == {"Even", "Odd"}:
        return choices.index("Even" if numbers[0] % 2 == 0 else "Odd")
    if choices[0] in ("None", "One", "Two") or "None" in choices:
        return choices.index("None" if numbers[0] % 2 == 0 else "One")
    assert choices[0].startswith("Yes"), item.id
    if "left over" in text or "no partner" in text:
        truth = numbers[0] % 2 == 1
    elif "split into two equal groups" in text:
        truth = numbers[0] % 2 == 0
    elif m := re.search(r"(?:Is (\d+) (?:an )?|(\d+) is (?:an? )?)(even|odd)", text):
        truth = int(m[1] or m[2]) % 2 == parity_of(m[3])
    elif m := re.search(r"ending in (\d)", text):
        truth = int(m[1]) % 2 == 1  # the claim is that such numbers are odd
    else:
        raise AssertionError(item.id)
    return 0 if truth else 1


def relation_of(choice: str) -> str | None:
    t = choice.lower()
    if t in (">", "<", "="):
        return t
    if t.startswith("yes") or "equal" in t or "same" in t:
        return "="
    bigger = any(w in t for w in ("bigger", "greater", "more"))
    if "first is" in t:
        return ">" if bigger else "<"
    if "second is" in t:
        return "<" if bigger else ">"
    if t in ("greater than", "more than", "after"):
        return ">"
    if t in ("less than", "before"):
        return "<"
    return None


def sentence_true(parts: tuple[Part, ...]) -> tuple[bool, int, int]:
    m = re.fullmatch(r"(\d+) ([<>=]) (\d+)", parts[0].value)
    assert m
    a, sign, b = int(m[1]), m[2], int(m[3])
    return {">": a > b, "<": a < b, "=": a == b}[sign], a, b


def decode_compare(item: BankItem) -> Decoded:
    assert item.choices is not None
    choices = item.choices
    if all(len(c) == 1 and c[0].kind == "math" and " " in c[0].value for c in choices):
        checked = [sentence_true(c) for c in choices]
        right = [i for i, (ok, _, _) in enumerate(checked) if ok]
        assert len(right) == 1, item.id
        return Decoded(right[0], checked[right[0]][1], checked[right[0]][2])
    math = [p.value for p in item.prompt if p.kind == "math"]
    if m := re.fullmatch(r"(\d+) \\square (\d+)", math[0]):
        a, b = int(m[1]), int(m[2])
    else:
        a, b = (int(x) for x in math[:2])
    actual = ">" if a > b else ("<" if a < b else "=")
    texts = [joined(c) for c in choices]
    relations = [relation_of(t) for t in texts]
    if texts[-1] == "They are the same":
        # "Which is bigger or smaller?" with the two owners first: the first choice owns the
        # first number shown.
        if a == b:
            return Decoded(2, a, b)
        asked = joined(item.prompt)
        bigger = bool(re.search(r"\b(more|longer|bigger|greater|larger)\b", asked))
        smaller = bool(re.search(r"\b(fewer|less|shorter|smaller)\b", asked))
        assert bigger != smaller, item.id
        return Decoded(0 if (a > b) == bigger else 1, a, b)
    assert actual in relations, (item.id, relations)
    return Decoded(relations.index(actual), a, b)


EVEN_ODD_ITEMS = PACK.bank["even_odd"].items
COMPARE_ITEMS = PACK.bank["compare_numbers_1000"].items


@pytest.mark.parametrize("skill_id", ["even_odd", "compare_numbers_1000"])
def test_each_bank_has_thirty_items_in_three_tiers_and_different_wordings(skill_id: str) -> None:
    items = PACK.bank[skill_id].items
    assert len(items) >= 30
    assert all(i.answer.kind == "choice" and i.choices and len(i.choices) >= 2 for i in items)
    for tier in range(3):
        assert sum(1 for i in items if i.tier == tier) >= 8
    assert all(i.tier is not None for i in items)
    wordings = {re.sub(r"\d+", "#", re.sub(r"\\square", "#", joined(i.prompt))) for i in items}
    assert len(wordings) >= 30
    for item in items:
        assert item.choices is not None
        assert len({joined(c) for c in item.choices}) == len(item.choices), item.id
    # The right answer sits in different places, since the choices are not shuffled in the data.
    assert len({int(i.answer.value) for i in items}) >= 2


@pytest.mark.parametrize("skill_id", ["even_odd", "compare_numbers_1000"])
def test_a_tier_serves_only_its_own_items(skill_id: str) -> None:
    bank = PACK.bank[skill_id]
    for tier in range(3):
        served = {pick_item(bank, seed, tier).id for seed in range(500)}
        assert served == {i.id for i in items_for_tier(bank, tier)}
        assert served <= {i.id for i in bank.items if i.tier == tier}


@pytest.mark.parametrize("skill_id", ["even_odd", "compare_numbers_1000"])
def test_bank_text_is_short_and_has_no_dash(skill_id: str) -> None:
    for item in PACK.bank[skill_id].items:
        assert item.choices is not None
        for parts in (item.prompt, *item.choices):
            text = " ".join(p.value if p.kind == "text" else "#" for p in parts)
            for dash in (chr(0x2014), chr(0x2013), " - ", "--"):
                assert dash not in text, item.id
            for sentence in re.split(r"(?<=[.?!])\s+", text):
                assert len(sentence.split()) <= 12, (item.id, sentence)
                if parts is item.prompt:
                    assert not re.match(r"[#\d]", sentence), (item.id, sentence)


def test_every_even_odd_answer_follows_from_the_numbers_shown() -> None:
    for item in EVEN_ODD_ITEMS:
        assert item.answer.value == decode_even_odd(item), item.id


def test_even_odd_items_stay_in_the_range_of_their_tier() -> None:
    ranges = ((1, 20), (1, 100), (1, 1000))
    for item in EVEN_ODD_ITEMS:
        assert item.tier is not None
        lo, hi = ranges[item.tier]
        shown = math_numbers(item.prompt) + [n for c in item.choices or () for n in math_numbers(c)]
        if "ending in" in joined(item.prompt):
            continue  # a rule about the last digit of every number, so no number to place
        assert all(lo <= n <= hi for n in shown), item.id
        if item.tier == 2:
            assert max(shown) > 100, item.id
        if item.tier == 1:
            assert max(shown) > 20, item.id


def test_even_odd_has_each_kind_of_question_and_both_answers() -> None:
    kinds = Counter()
    for item in EVEN_ODD_ITEMS:
        assert item.choices is not None
        texts = {joined(c) for c in item.choices}
        if texts == {"Even", "Odd"}:
            kinds["kind"] += 1
        elif all(t.isdigit() for t in texts):
            kinds["numbers"] += 1
        else:
            kinds["yes_no_or_count"] += 1
    assert all(count >= 6 for count in kinds.values()), kinds
    answers = Counter(
        joined(item.choices[int(item.answer.value)]) for item in EVEN_ODD_ITEMS if item.choices
    )
    assert answers["Even"] >= 3 and answers["Odd"] >= 3
    assert answers["Yes"] + answers["No"] >= 3


def test_even_odd_wrong_numbers_are_sometimes_one_off_and_sometimes_far() -> None:
    """The wrong numbers of an item that asks for a number are not all next to the right
    one: a child cannot pick the one that is odd out of the line."""
    gaps: set[int] = set()
    for item in EVEN_ODD_ITEMS:
        assert item.choices is not None
        values = [joined(c) for c in item.choices]
        if all(v.isdigit() for v in values) and "next" in joined(item.prompt):
            right = int(values[int(item.answer.value)])
            gaps |= {abs(int(v) - right) for v in values if int(v) != right}
    assert gaps >= {1, 2} and max(gaps) >= 5, gaps


def test_every_compare_1000_answer_follows_from_the_numbers_shown() -> None:
    for item in COMPARE_ITEMS:
        assert item.answer.value == decode_compare(item).index, item.id


def test_compare_1000_items_use_the_pairs_of_their_tier() -> None:
    for item in COMPARE_ITEMS:
        decoded = decode_compare(item)
        assert decoded.a is not None and decoded.b is not None
        a, b = decoded.a, decoded.b
        if a == b:
            continue
        kind = pair_kind(a, b)
        if item.tier == 0:
            assert kind == "far", (item.id, a, b)
        elif item.tier == 1:
            assert kind in ("same", "zero") and a // 100 == b // 100, (item.id, a, b)
        else:
            assert kind in ("cross", "zero", "thousand"), (item.id, a, b)


def test_about_one_compare_1000_item_in_four_is_equal_so_never_picking_a_side_does_not_win() -> (
    None
):
    equal = sum(1 for i in COMPARE_ITEMS if decode_compare(i).a == decode_compare(i).b)
    assert 0.2 <= equal / len(COMPARE_ITEMS) <= 0.4, equal
    for tier in range(3):
        in_tier = [i for i in COMPARE_ITEMS if i.tier == tier]
        assert sum(1 for i in in_tier if decode_compare(i).a == decode_compare(i).b) >= 2


def test_compare_1000_items_reach_1000_and_ask_both_directions() -> None:
    assert any(1000 in math_numbers(i.prompt) or "1000" in joined(i.prompt) for i in COMPARE_ITEMS)
    asked = " ".join(joined(i.prompt) for i in COMPARE_ITEMS)
    assert re.search(r"\b(more|longer)\b", asked) and re.search(r"\b(fewer|less)\b", asked)


def test_compare_1000_sign_items_answer_greater_than_as_often_as_less_than() -> None:
    """Choices are shuffled when served, so only the answer sign can be skewed. In each tier
    that has sign items, both signs are an answer, and neither is more than twice the other."""
    signs: dict[int, Counter[str]] = {0: Counter(), 1: Counter(), 2: Counter()}
    for item in COMPARE_ITEMS:
        assert item.choices is not None and item.tier is not None
        texts = [joined(c) for c in item.choices]
        if texts == [">", "<", "="]:
            signs[item.tier][texts[int(item.answer.value)]] += 1
    overall = sum(signs.values(), Counter())
    assert overall[">"] >= 3 and overall["<"] >= 3
    assert max(overall[">"], overall["<"]) <= 2 * min(overall[">"], overall["<"]), overall
    for tier in (1, 2):
        assert signs[tier][">"] >= 1 and signs[tier]["<"] >= 1, (tier, signs[tier])


def test_no_story_to_100_asks_a_bare_how_many_left() -> None:
    """A bare "How many left?" can mean how many remain, and the count that remains may be
    printed just above it; the question names what is counted."""
    for template in templates("word_problems_100"):
        assert not re.search(r"How many (left|more|fewer)\?", template.text_template), template.id
