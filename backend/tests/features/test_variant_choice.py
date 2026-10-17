"""Variant selection: a seeded draw from the skill's shares (no database needed)."""

import dataclasses
from pathlib import Path

from mathquest.engine.bank import pick_item
from mathquest.engine.catalog import SkillSource, build_catalog, load_catalog
from mathquest.engine.content import load_pack
from mathquest.engine.content.schema import Bank
from mathquest.features.play.variants import choose_variant

BACKEND = Path(__file__).resolve().parents[2]
REAL = load_catalog(BACKEND / "content", "k8-core")
FIXTURE = build_catalog(
    load_pack(BACKEND / "tests" / "fixtures" / "packs" / "test-pack"), REAL.slots
)


def test_variant_is_deterministic_per_seed() -> None:
    source = FIXTURE.source("story")
    first = [choose_variant(source, seed) for seed in range(500)]
    assert first == [choose_variant(source, seed) for seed in range(500)]


def test_variant_follows_the_shares() -> None:
    source = FIXTURE.source("story")  # bank 0.2, word 0.5
    picks = [choose_variant(source, seed) for seed in range(4000)]
    assert abs(picks.count("bank") / 4000 - 0.2) < 0.03
    assert abs(picks.count("word") / 4000 - 0.5) < 0.03
    assert abs(picks.count("bare") / 4000 - 0.3) < 0.03


def test_full_bank_share_is_always_bank() -> None:
    source = FIXTURE.source("pick")
    assert {choose_variant(source, seed) for seed in range(300)} == {"bank"}


def test_skill_without_content_is_always_bare() -> None:
    source = REAL.source("sub_within_10")
    assert {choose_variant(source, seed) for seed in range(300)} == {"bare"}


def _tiered(source: SkillSource) -> SkillSource:
    """``source`` with a bank whose items suit tier 0, tier 1 or every tier."""
    assert source.bank is not None
    base = source.bank.items[0]
    items = tuple(
        base.model_copy(update={"id": f"item_{n}", "tier": tier})
        for n, tier in enumerate((0, 0, 1, None))
    )
    return dataclasses.replace(source, bank=Bank(skill=source.bank.skill, items=items))


def test_a_bank_item_is_picked_only_from_the_learners_tier() -> None:
    source = _tiered(FIXTURE.source("pick"))
    assert source.bank is not None
    for tier, allowed in ((0, {"item_0", "item_1", "item_3"}), (1, {"item_2", "item_3"})):
        picked = {pick_item(source.bank, seed, tier).id for seed in range(200)}
        assert picked == allowed
    # A tier with no item of its own and no untagged one serves the whole bank.
    only_tier_zero = Bank(skill="pick", items=source.bank.items[:2])
    assert {pick_item(only_tier_zero, seed, 2).id for seed in range(100)} == {"item_0", "item_1"}


def test_the_bank_share_only_counts_when_the_tier_has_items() -> None:
    source = _tiered(FIXTURE.source("story"))  # bank 0.2, word 0.5
    assert source.bank is not None
    assert "bank" in {choose_variant(source, seed, 1) for seed in range(300)}
    tier_two = dataclasses.replace(
        source, bank=Bank(skill="story", items=tuple(i for i in source.bank.items if i.tier == 0))
    )
    assert "bank" not in {choose_variant(tier_two, seed, 1) for seed in range(300)}
    assert source.generate(3, 1, "bank").template_id in {"item_2", "item_3"}
    assert source.generate(3, 0, "bank").template_id in {"item_0", "item_1", "item_3"}
