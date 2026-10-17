"""The shipped bank items of the comparing skills have the right answers and tiers.

A bank item carries its own answer, and the lint cannot read a story, so these tests do:
every item's answer is recomputed from the numbers it shows, by the rule of its question.
"""

import re
from pathlib import Path

import pytest

from mathquest.engine.bank import items_for_tier, pick_item
from mathquest.engine.content import load_pack
from mathquest.engine.content.schema import BankItem, Part

PACK = load_pack(Path(__file__).resolve().parents[2] / "content" / "packs" / "k8-core")
SKILLS = ("compare_groups", "compare_numbers_20", "compare_numbers_100")
BIGGER = re.compile(r"\b(more|bigger)\b", re.IGNORECASE)
SMALLER = re.compile(r"\b(fewer|smaller|less)\b", re.IGNORECASE)
TIER_RANGES = {
    "compare_groups": ((2, 5), (2, 10), (6, 10)),
    "compare_numbers_20": ((1, 10), (11, 20), (1, 20)),
}


def _text(parts: tuple[Part, ...]) -> str:
    return " ".join(p.value for p in parts)


def _numbers(item: BankItem) -> list[int]:
    found = [int(p.value) for p in item.prompt if p.kind == "math" and p.value.isdigit()]
    if found:
        return found[:2]
    # A sign item: "47 \square 52" in one math part.
    for p in item.prompt:
        if p.kind == "math":
            return [int(n) for n in re.findall(r"\d+", p.value)][:2]
    raise AssertionError(item.id)


def _expected(item: BankItem) -> int:
    """The index the item's answer must have, by the rule of its question."""
    a, b = _numbers(item)
    assert item.choices is not None
    asked = _text(item.prompt)
    first = _text(item.choices[0])
    if first in (">", "<", "=") or re.fullmatch(r"\d+ [><=] \d+", first):
        return 0 if a > b else (1 if a < b else 2)
    if first.startswith("Yes, equal"):
        return 0 if a == b else (1 if a > b else 2)
    if a == b:
        return 2  # "the same", "equal" or "nothing left over" is always the last choice
    relation = "Finish it" in asked or "more, less" in asked
    if relation:
        return 0 if a > b else 1
    wants_bigger = bool(BIGGER.search(asked)) and not SMALLER.search(asked)
    assert wants_bigger != bool(SMALLER.search(asked)), item.id
    return 0 if (a > b) == wants_bigger else 1


@pytest.mark.parametrize("skill", SKILLS)
def test_each_comparing_skill_has_a_tiered_bank_of_choice_items(skill: str) -> None:
    items = list(PACK.bank[skill].items)
    assert len(items) >= 30
    assert all(i.answer.kind == "choice" and i.choices and len(i.choices) >= 3 for i in items)
    # Typed skills: the bank is only what needs buttons, served beside the generator.
    assert PACK.skills[skill].keypad == "numpad"
    assert 0 < PACK.skills[skill].bank_share < 1
    for tier in range(3):
        assert sum(1 for i in items if i.tier == tier) >= 8
    assert all(i.tier is not None for i in items)


@pytest.mark.parametrize("skill", SKILLS)
def test_every_answer_follows_from_the_numbers_shown(skill: str) -> None:
    for item in PACK.bank[skill].items:
        assert item.choices is not None
        assert item.answer.value == _expected(item), item.id


@pytest.mark.parametrize("skill", SKILLS)
def test_a_tier_serves_only_its_own_items(skill: str) -> None:
    bank = PACK.bank[skill]
    for tier in range(3):
        served = {pick_item(bank, seed, tier).id for seed in range(400)}
        assert served == {i.id for i in items_for_tier(bank, tier)}
        assert served <= {i.id for i in bank.items if i.tier == tier}


@pytest.mark.parametrize("skill", ["compare_groups", "compare_numbers_20"])
def test_items_use_the_numbers_of_their_tier(skill: str) -> None:
    for item in PACK.bank[skill].items:
        lo, hi = TIER_RANGES[skill][item.tier or 0]
        a, b = _numbers(item)
        assert lo <= a <= hi and lo <= b <= hi, item.id
        if item.tier == 2 and a != b:
            assert abs(a - b) <= 1 or skill == "compare_groups", item.id


def test_compare_numbers_100_tiers_pick_the_kind_of_pair() -> None:
    for item in PACK.bank["compare_numbers_100"].items:
        a, b = _numbers(item)
        lo, hi = sorted((a, b))
        if a == b:
            continue
        if item.tier == 0:
            assert abs(a // 10 - b // 10) >= 2, item.id
        elif item.tier == 1:
            assert a // 10 == b // 10, item.id
        else:
            assert lo // 10 < hi // 10 and lo % 10 > hi % 10, item.id


@pytest.mark.parametrize("skill", SKILLS)
def test_about_one_item_in_four_is_equal_so_never_picking_same_does_not_win(skill: str) -> None:
    items = list(PACK.bank[skill].items)
    equal = sum(1 for i in items if _numbers(i)[0] == _numbers(i)[1])
    assert 0.2 <= equal / len(items) <= 0.4, equal
    # The right answer's position in the data is not a pattern either: the engine shuffles
    # the choices by seed, so only the equal answers need to be common.
    assert equal >= 7


@pytest.mark.parametrize("skill", SKILLS)
def test_choices_in_an_item_are_all_different_and_the_answer_is_one_of_them(skill: str) -> None:
    for item in PACK.bank[skill].items:
        assert item.choices is not None
        assert len({_text(c) for c in item.choices}) == len(item.choices), item.id
        assert 0 <= int(item.answer.value) < len(item.choices), item.id


def test_no_bank_item_opens_with_a_scene_sentence() -> None:
    openers = {_text(i.prompt).split(".")[0] for s in SKILLS for i in PACK.bank[s].items}
    assert not any(
        o.startswith(("It is a", "The sun", "The wind", "A bird sings")) for o in openers
    )
    words = " ".join(_text(i.prompt) for s in SKILLS for i in PACK.bank[s].items).lower()
    for hard in ("greatest", "sentence", "between", "row lists"):
        assert hard not in words
