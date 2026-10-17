"""The shipped bank items of the comparing skills have the right answers.

A bank item carries its own answer, and the lint cannot read a story, so these tests do:
every item whose answer follows from the numbers it shows is recomputed.
"""

import re
from pathlib import Path

import pytest

from mathquest.engine.content import load_pack
from mathquest.engine.content.schema import BankItem, Part

PACK = load_pack(Path(__file__).resolve().parents[2] / "content" / "packs" / "k8-core")
SKILLS = ("compare_groups", "compare_numbers_20", "compare_numbers_100")
BIGGER = re.compile(r"\b(more|bigger|greater|greatest|biggest|later)\b", re.IGNORECASE)
SMALLER = re.compile(r"\b(fewer|smaller|less|least|smallest)\b", re.IGNORECASE)


def _text(parts: tuple[Part, ...]) -> str:
    return " ".join(p.value for p in parts)


def _numbers(parts: tuple[Part, ...]) -> list[int]:
    return [int(p.value) for p in parts if p.kind == "math" and p.value.isdigit()]


def _items(skill: str) -> list[BankItem]:
    return list(PACK.bank[skill].items)


@pytest.mark.parametrize("skill", SKILLS)
def test_each_comparing_skill_has_a_full_bank_of_choice_items(skill: str) -> None:
    items = _items(skill)
    assert len(items) >= 30
    assert all(i.answer.kind == "choice" and i.choices and len(i.choices) >= 3 for i in items)
    assert PACK.skills[skill].keypad == "choice"
    assert PACK.skills[skill].bank_share == 1.0


def test_compare_groups_answers_follow_the_counts() -> None:
    for item in _items("compare_groups"):
        a, b = _numbers(item.prompt)
        assert item.choices is not None
        right = _text(item.choices[int(item.answer.value)]).lower()
        if a == b:
            assert "same" in right, item.id
            continue
        wants_more = bool(BIGGER.search(_text(item.prompt)))
        assert wants_more != bool(SMALLER.search(_text(item.prompt))), item.id
        # The first group named is the first choice, the second group the second.
        assert item.answer.value == (0 if (a > b) == wants_more else 1), item.id
        for choice in item.choices[:2]:
            assert "same" not in _text(choice).lower(), item.id


@pytest.mark.parametrize("skill", ["compare_numbers_20", "compare_numbers_100"])
def test_a_question_about_two_numbers_has_the_bigger_or_smaller_as_its_answer(skill: str) -> None:
    checked = 0
    for item in _items(skill):
        assert item.choices is not None
        shown = _numbers(item.prompt)
        offered = [_numbers(c) for c in item.choices]
        if len(shown) != 2 or offered[:2] != [[shown[0]], [shown[1]]]:
            continue
        asked = _text(item.prompt)
        if "tens" in asked:
            continue
        if BIGGER.search(asked) and not SMALLER.search(asked):
            want = max(shown)
        elif SMALLER.search(asked) and not BIGGER.search(asked):
            want = min(shown)
        else:
            continue
        assert offered[int(item.answer.value)] == [want], item.id
        checked += 1
    assert checked >= 8


def test_compare_numbers_100_signs_and_sentences_are_true() -> None:
    checked = 0
    for item in _items("compare_numbers_100"):
        assert item.choices is not None
        right = item.choices[int(item.answer.value)][0].value
        blank = [p.value for p in item.prompt if p.kind == "math" and r"\square" in p.value]
        if blank and right in (">", "<", "="):
            a, b = (int(n) for n in blank[0].split(r"\square"))
            assert right == (">" if a > b else "<" if a < b else "="), item.id
            checked += 1
        elif _text(item.prompt) == "Which sentence is true?":
            a, sign, b = right.split()
            truth = {">": int(a) > int(b), "<": int(a) < int(b), "=": int(a) == int(b)}
            assert truth[sign], item.id
            checked += 1
    assert checked >= 6


@pytest.mark.parametrize("skill", SKILLS)
def test_choices_in_an_item_are_all_different_and_the_answer_is_one_of_them(skill: str) -> None:
    for item in _items(skill):
        assert item.choices is not None
        assert len({_text(c) for c in item.choices}) == len(item.choices), item.id
        assert 0 <= int(item.answer.value) < len(item.choices), item.id
