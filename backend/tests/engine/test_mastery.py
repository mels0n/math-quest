import random
from collections.abc import Callable
from math import log

import pytest

from mathquest.engine.mastery import (
    MASTERY_MIN_ATTEMPTS,
    MASTERY_PREDICT,
    RATING_CAP_ABOVE_TOP,
    Outcome,
    SkillRating,
    choose_tier,
    correct_streak,
    initial_rating,
    is_mastered,
    next_review_days,
    predict,
    score,
    step_size,
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


def test_correct_streak_counts_the_newest_correct_outcomes() -> None:
    assert correct_streak(SkillRating()) == 0
    assert correct_streak(SkillRating(recent=((True, 0), (False, 1), (True, 2), (True, 2)))) == 2
    assert correct_streak(SkillRating(recent=((True, 0), (False, 1)))) == 0
    assert correct_streak(SkillRating(recent=((True, 1),) * 7)) == 7


def test_streak_bonus_grows_the_step_up_to_three_times() -> None:
    def k(streak: int) -> float:
        return step_size(SkillRating(attempts=20, recent=((False, 0), *(((True, 0),) * streak))))

    assert k(0) == pytest.approx(0.3)
    assert k(1) == pytest.approx(0.6)
    assert k(2) == pytest.approx(0.9)
    assert k(5) == pytest.approx(0.9)
    assert step_size(SkillRating()) == pytest.approx(1.0)


def test_update_caps_the_rating_above_the_top_tier() -> None:
    r = SkillRating(rating=0.0)
    for _ in range(30):
        r = update(r, 1.0, _o(), top_difficulty=1.0)
        assert r.rating <= 1.0 + RATING_CAP_ABOVE_TOP
    assert r.rating == pytest.approx(1.0 + RATING_CAP_ABOVE_TOP)
    assert update(SkillRating(rating=0.0), 1.0, _o()).rating > 0.0


@pytest.mark.parametrize("ability", [-1.0, 0.5, 1.0, 2.0])
def test_simulated_learner_converges(ability: float) -> None:
    # Tiers are centred on round(ability) so tier selection is meaningful.
    # Single-run error is noisy (k floor 0.3 and the streak bonus), so assert on
    # last-50 means: the cross-seed mean within 0.4 and every run within 1.0
    # (the worst of these 80 runs is 0.968 off).
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
            r = update(r, d, _o(correct=correct), tiers[2])
            if attempt >= 150:
                tail.append(r.rating)
        tail_means.append(sum(tail) / len(tail))
    assert abs(sum(tail_means) / len(tail_means) - ability) < 0.4
    assert all(abs(m - ability) < 1.0 for m in tail_means)


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


def test_is_mastered_needs_6_attempts() -> None:
    assert MASTERY_MIN_ATTEMPTS == 6
    assert not is_mastered(SkillRating(rating=5.0, attempts=5, recent=_TOP_STREAK), 0.0)
    assert is_mastered(SkillRating(rating=5.0, attempts=6, recent=_TOP_STREAK), 0.0)
    assert not is_mastered(SkillRating(rating=-3.0, attempts=20, recent=_TOP_STREAK), 0.0)


def test_is_mastered_needs_predicted_top_tier_success_of_0_7() -> None:
    assert MASTERY_PREDICT == 0.7
    top = 1.0
    at_threshold = top + log(0.7 / 0.3)
    above = SkillRating(rating=at_threshold + 1e-6, attempts=6, recent=_TOP_STREAK)
    below = SkillRating(rating=at_threshold - 1e-6, attempts=6, recent=_TOP_STREAK)
    assert predict(above.rating, top) > 0.7 > predict(below.rating, top)
    assert is_mastered(above, top)
    assert not is_mastered(below, top)


def test_is_mastered_needs_top_tier_streak() -> None:
    def rated(recent: tuple[tuple[bool, int], ...]) -> SkillRating:
        return SkillRating(rating=5.0, attempts=20, recent=recent)

    assert is_mastered(rated(((False, 2), *(((True, 2),) * 5))), 0.0)
    assert not is_mastered(rated(((False, 2), (False, 2), *(((True, 2),) * 4))), 0.0)
    assert not is_mastered(rated(((True, 1),) * 6), 0.0)
    assert not is_mastered(rated(((True, 2), (True, 1), (True, 1), *(((True, 2),) * 3))), 0.0)
    assert not is_mastered(rated(((True, 2),) * 4), 0.0)


Answer = Callable[[random.Random, int, int], bool]
"""(rng, tier shown, problem number from 1) -> answered correctly."""


def _play(
    answer: Answer,
    problems: int,
    seed: int = 0,
    base: float = 0.0,
    seconds: Callable[[int], float] = lambda n: 1.0,
    fluency: bool = True,
) -> tuple[list[int], int | None]:
    """Play one skill with the engine choosing tiers; returns the tiers shown and the
    problem number on which the skill was first mastered (None if never)."""
    tiers = (base - 1, base, base + 1)
    rng = random.Random(seed)
    r = SkillRating(rating=initial_rating(tiers))
    shown: list[int] = []
    mastered_on: int | None = None
    for n in range(1, problems + 1):
        tier = choose_tier(r, tiers)
        correct = answer(rng, tier, n)
        r = update(r, tiers[tier], Outcome(correct, 0, seconds(n), fluency, tier), tiers[2])
        shown.append(tier)
        if mastered_on is None and is_mastered(r, tiers[2]):
            mastered_on = n
    return shown, mastered_on


def _always(rng: random.Random, tier: int, n: int) -> bool:
    return True


def _never(rng: random.Random, tier: int, n: int) -> bool:
    return False


@pytest.mark.parametrize("base", [-2.0, 0.0, 0.8])
def test_perfect_learner_reaches_top_tier_by_4_and_masters_by_6_to_8(base: float) -> None:
    shown, mastered_on = _play(_always, 20, base=base)
    assert 2 in shown[:4]
    assert mastered_on is not None
    assert 6 <= mastered_on <= 8


def _fast(n: int) -> float:
    return 1.0


def _slow_after_4(n: int) -> float:
    # Answering slowly from the start holds a fluency skill on the middle tier (a slow
    # answer scores 0.75), so the top tier is reached fast and then answered slowly.
    return 1.0 if n <= 4 else 9.0


@pytest.mark.parametrize("streak", [4, 10, 20, 60])
@pytest.mark.parametrize(
    ("seconds", "fluency"),
    [(_fast, True), (_slow_after_4, True), (_slow_after_4, False)],
    ids=["fast-fluency", "slow-fluency", "slow-concept"],
)
def test_one_top_tier_miss_drops_a_tier_after_any_streak(
    streak: int, seconds: Callable[[int], float], fluency: bool
) -> None:
    shown, _ = _play(lambda rng, tier, n: n <= streak, streak + 2, seconds=seconds, fluency=fluency)
    assert shown[streak] == 2  # the missed problem was on the top tier
    assert shown[streak + 1] < 2


def test_a_kid_who_keeps_missing_drops_and_does_not_master() -> None:
    # Reaches the top tier, then misses every third problem.
    shown, mastered_on = _play(lambda rng, tier, n: n <= 4 or n % 3 != 0, 60)
    assert shown[5] == 2  # the first miss, problem 6, is on the top tier
    assert shown[6] < 2  # and moves problem 7 down a tier
    assert mastered_on is None


def test_always_wrong_never_masters_and_sits_on_tier_0() -> None:
    shown, mastered_on = _play(_never, 60)
    assert mastered_on is None
    assert all(tier == 0 for tier in shown[2:])


def _mastery_rate(accuracy: float, seeds: int = 1000) -> float:
    """Share of 60-problem runs that master, for a kid right `accuracy` of the time on
    every tier. Seeds are fixed, so the rate is the same on every run of the tests."""
    mastered = sum(
        _play(lambda rng, tier, n: rng.random() < accuracy, 60, seed=seed)[1] is not None
        for seed in range(seeds)
    )
    return mastered / seeds


@pytest.mark.parametrize(
    ("accuracy", "bound"),
    # Measured: 0.027, 0.056 and 0.137 over these 1000 seeds (0.024, 0.059 and 0.140
    # over 4000).
    [(0.60, 0.04), (0.65, 0.08), (0.70, 0.16)],
)
def test_mixed_accuracy_rarely_masters(accuracy: float, bound: float) -> None:
    assert _mastery_rate(accuracy) <= bound


def test_ninety_percent_accuracy_masters_almost_always() -> None:
    # Measured: 0.983 over these 1000 seeds (0.979 over 4000).
    assert _mastery_rate(0.90) >= 0.90


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
