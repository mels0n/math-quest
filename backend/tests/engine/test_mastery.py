import random

import pytest

from mathquest.engine.mastery import (
    Outcome,
    SkillRating,
    choose_tier,
    initial_rating,
    is_mastered,
    next_review_days,
    predict,
    score,
    update,
)


def _o(
    correct: bool = True, hints: int = 0, seconds: float = 1.0, fluency: bool = False
) -> Outcome:
    return Outcome(correct=correct, hints_used=hints, seconds=seconds, fluency=fluency)


def test_predict_symmetry() -> None:
    assert predict(1.3, 1.3) == pytest.approx(0.5)


def test_hints_reduce_gain() -> None:
    r = SkillRating()
    assert update(r, 0.0, _o(hints=2)).rating < update(r, 0.0, _o(hints=0)).rating
    assert score(_o(hints=10)) == 0.25
    assert score(_o(correct=False)) == 0.0


def test_slow_fluency_reduces_gain() -> None:
    r = SkillRating()
    fast = update(r, 0.0, _o(seconds=2.0, fluency=True)).rating
    mid = update(r, 0.0, _o(seconds=5.5, fluency=True)).rating
    slow = update(r, 0.0, _o(seconds=9.0, fluency=True)).rating
    assert fast > mid > slow
    assert score(_o(seconds=8.0, fluency=True)) == pytest.approx(0.75)


def test_slow_concept_not_penalized() -> None:
    r = SkillRating()
    assert update(r, 0.0, _o(seconds=60.0, fluency=False)) == update(
        r, 0.0, _o(seconds=1.0, fluency=False)
    )


def test_update_returns_new_rating_with_history() -> None:
    r = SkillRating(recent=((True, 0),) * 10)
    n = update(r, 0.0, Outcome(correct=False, hints_used=0, seconds=1.0, fluency=False, tier=2))
    assert n.attempts == 1
    assert len(n.recent) == 10
    assert n.recent[-1] == (False, 2)
    assert r.attempts == 0


@pytest.mark.parametrize("ability", [-1.0, 0.5, 1.0, 2.0])
def test_simulated_learner_converges(ability: float) -> None:
    # Tiers are centred on round(ability) so tier selection is meaningful.
    # Single-run error is noisy (k floor 0.3), so assert on last-50 means:
    # the cross-seed mean within 0.4 and every run within 0.8.
    base = float(round(ability))
    tiers = (base - 1, base, base + 1)
    tail_means: list[float] = []
    for seed in range(20):
        rng = random.Random(seed)
        r = SkillRating()
        tail: list[float] = []
        for attempt in range(200):
            d = tiers[choose_tier(r, tiers)]
            correct = rng.random() < predict(ability, d)
            r = update(r, d, _o(correct=correct))
            if attempt >= 150:
                tail.append(r.rating)
        tail_means.append(sum(tail) / len(tail))
    assert abs(sum(tail_means) / len(tail_means) - ability) < 0.4
    assert all(abs(m - ability) < 0.8 for m in tail_means)


def test_choose_tier_targets_775() -> None:
    tiers = (-2.0, 0.0, 2.0)
    # rating 0: predict(0,-2)=0.88, predict(0,0)=0.5, predict(0,2)=0.12 -> tier 0
    assert choose_tier(SkillRating(rating=0.0), tiers) == 0
    # rating 2: predict vs 2.0 = 0.5, vs 0.0 = 0.88 -> 0.88 closer to 0.775
    assert choose_tier(SkillRating(rating=2.0), tiers) == 1
    assert choose_tier(SkillRating(rating=5.0), tiers) == 2
    # tie goes to the lower tier
    assert choose_tier(SkillRating(rating=0.0), (0.0, 0.0)) == 0


_TOP_STREAK = ((True, 2),) * 6


def test_is_mastered_needs_8_attempts() -> None:
    assert not is_mastered(SkillRating(rating=5.0, attempts=7, recent=_TOP_STREAK), 0.0)
    assert is_mastered(SkillRating(rating=5.0, attempts=8, recent=_TOP_STREAK), 0.0)
    assert not is_mastered(SkillRating(rating=-3.0, attempts=20, recent=_TOP_STREAK), 0.0)


def test_is_mastered_needs_top_tier_streak() -> None:
    def rated(recent: tuple[tuple[bool, int], ...]) -> SkillRating:
        return SkillRating(rating=5.0, attempts=20, recent=recent)

    assert is_mastered(rated(((False, 2), *(((True, 2),) * 5))), 0.0)
    assert not is_mastered(rated(((False, 2), (False, 2), *(((True, 2),) * 4))), 0.0)
    assert not is_mastered(rated(((True, 1),) * 6), 0.0)
    assert not is_mastered(rated(((True, 2), (True, 1), (True, 1), *(((True, 2),) * 3))), 0.0)
    assert not is_mastered(rated(((True, 2),) * 4), 0.0)


@pytest.mark.parametrize("base", [-2.0, 0.0, 0.8])
def test_perfect_learner_masters_quickly(base: float) -> None:
    tiers = (base - 1, base, base + 1)
    r = SkillRating(rating=initial_rating(tiers))
    for n in range(1, 40):
        tier = choose_tier(r, tiers)
        r = update(r, tiers[tier], Outcome(True, 0, 1.0, True, tier))
        if is_mastered(r, tiers[2]):
            assert n <= 15
            return
    raise AssertionError("never mastered")


@pytest.mark.parametrize("seed", range(15))
def test_learner_at_base_difficulty_does_not_master(seed: int) -> None:
    base = 0.0
    tiers = (base - 1, base, base + 1)
    rng = random.Random(seed)
    r = SkillRating(rating=initial_rating(tiers))
    for _ in range(80):
        tier = choose_tier(r, tiers)
        correct = rng.random() < predict(base, tiers[tier])
        r = update(r, tiers[tier], Outcome(correct, 0, 1.0, False, tier))
        assert not is_mastered(r, tiers[2])


def test_review_steps() -> None:
    assert next_review_days(None, True) == 1
    assert next_review_days(1, True) == 3
    assert next_review_days(3, True) == 7
    assert next_review_days(7, True) == 21
    assert next_review_days(21, True) == 42
    assert next_review_days(7, False) == 1
    assert next_review_days(42, True) == 84


def test_review_non_step_previous_moves_to_next_larger_step() -> None:
    assert next_review_days(5, True) == 7
