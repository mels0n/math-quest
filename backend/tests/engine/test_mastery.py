import random

import pytest

from mathquest.engine.mastery import (
    Outcome,
    SkillRating,
    choose_tier,
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
    r = SkillRating(recent=(True,) * 10)
    n = update(r, 0.0, _o(correct=False))
    assert n.attempts == 1
    assert len(n.recent) == 10
    assert n.recent[-1] is False
    assert r.attempts == 0


def test_simulated_learner_converges() -> None:
    rng = random.Random(12345)
    true_ability = 1.0
    tiers = (-1.0, 0.0, 1.0)
    r = SkillRating()
    for _ in range(200):
        tier = choose_tier(r, tiers)
        d = tiers[tier]
        correct = rng.random() < predict(true_ability, d)
        r = update(r, d, _o(correct=correct))
    assert abs(r.rating - true_ability) < 0.4


def test_choose_tier_targets_775() -> None:
    tiers = (-2.0, 0.0, 2.0)
    # rating 0: predict(0,-2)=0.88, predict(0,0)=0.5, predict(0,2)=0.12 -> tier 0
    assert choose_tier(SkillRating(rating=0.0), tiers) == 0
    # rating 2: predict vs 2.0 = 0.5, vs 0.0 = 0.88 -> 0.88 closer to 0.775
    assert choose_tier(SkillRating(rating=2.0), tiers) == 1
    assert choose_tier(SkillRating(rating=5.0), tiers) == 2
    # tie goes to the lower tier
    assert choose_tier(SkillRating(rating=0.0), (0.0, 0.0)) == 0


def test_is_mastered_needs_8_attempts() -> None:
    strong = (True,) * 10
    assert not is_mastered(SkillRating(rating=5.0, attempts=7, recent=strong), 0.0)
    assert is_mastered(SkillRating(rating=5.0, attempts=8, recent=strong), 0.0)
    assert not is_mastered(SkillRating(rating=0.0, attempts=20, recent=strong), 0.0)
    weak = (True, True, False, False, True)
    assert not is_mastered(SkillRating(rating=5.0, attempts=20, recent=weak), 0.0)


def test_review_steps() -> None:
    assert next_review_days(None, True) == 1
    assert next_review_days(1, True) == 3
    assert next_review_days(3, True) == 7
    assert next_review_days(7, True) == 21
    assert next_review_days(21, True) == 42
    assert next_review_days(7, False) == 1
