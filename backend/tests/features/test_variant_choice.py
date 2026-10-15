"""Variant selection: a seeded draw from the skill's shares (no database needed)."""

from pathlib import Path

from mathquest.engine.catalog import build_catalog, load_catalog
from mathquest.engine.content import load_pack
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
