"""Elo-style per-skill rating, mastery decision and spaced-review steps."""

from collections.abc import Sequence
from dataclasses import dataclass, replace
from enum import StrEnum
from math import exp, sqrt

TARGET_SUCCESS = 0.775
RECENT_WINDOW = 10
MASTERY_PREDICT = 0.7
MASTERY_MIN_ATTEMPTS = 8
MASTERY_STREAK_WINDOW = 6
MASTERY_STREAK_NEEDED = 5
TOP_TIER = 2
REVIEW_STEPS = (1, 3, 7, 21)


class SkillState(StrEnum):
    LOCKED = "locked"
    READY = "ready"
    LEARNING = "learning"
    MASTERED = "mastered"
    REVIEW_DUE = "review_due"


@dataclass(frozen=True)
class SkillRating:
    """Rating plus the last 10 outcomes as (correct, tier), newest last."""

    rating: float = 0.0
    attempts: int = 0
    recent: tuple[tuple[bool, int], ...] = ()


@dataclass(frozen=True)
class Outcome:
    correct: bool
    hints_used: int
    seconds: float
    fluency: bool
    tier: int = 0


def predict(rating: float, difficulty: float) -> float:
    return 1 / (1 + exp(difficulty - rating))


def score(o: Outcome) -> float:
    if not o.correct:
        return 0.0
    base = max(0.25, 1 - 0.25 * o.hints_used)
    if not o.fluency:
        return base
    if o.seconds <= 3:
        factor = 1.0
    elif o.seconds >= 8:
        factor = 0.75
    else:
        factor = 1.0 - 0.25 * (o.seconds - 3) / 5
    return base * factor


def update(r: SkillRating, difficulty: float, o: Outcome) -> SkillRating:
    k = max(0.3, 1.0 / sqrt(1 + r.attempts))
    rating = r.rating + k * (score(o) - predict(r.rating, difficulty))
    return replace(
        r,
        rating=rating,
        attempts=r.attempts + 1,
        recent=(*r.recent, (o.correct, o.tier))[-RECENT_WINDOW:],
    )


def choose_tier(r: SkillRating, tier_difficulties: Sequence[float]) -> int:
    """Index of the tier whose predicted success is closest to 0.775; ties go to the lower tier."""
    best = 0
    best_gap = abs(predict(r.rating, tier_difficulties[0]) - TARGET_SUCCESS)
    for i in range(1, len(tier_difficulties)):
        gap = abs(predict(r.rating, tier_difficulties[i]) - TARGET_SUCCESS)
        if gap < best_gap:
            best, best_gap = i, gap
    return best


def initial_rating(tier_difficulties: Sequence[float]) -> float:
    """A skill's first rating: its base (middle tier) difficulty plus 1.0."""
    return tier_difficulties[1] + 1.0


def is_mastered(r: SkillRating, top_difficulty: float, top_tier: int = TOP_TIER) -> bool:
    """Enough attempts, high predicted success on the top tier, and a recent top-tier streak."""
    if r.attempts < MASTERY_MIN_ATTEMPTS or predict(r.rating, top_difficulty) < MASTERY_PREDICT:
        return False
    streak = sum(
        1 for correct, tier in r.recent[-MASTERY_STREAK_WINDOW:] if correct and tier == top_tier
    )
    return streak >= MASTERY_STREAK_NEEDED


def next_review_days(previous: int | None, success: bool) -> int:
    """Days until the next review (1 on first or failed review, doubling past 21)."""
    if previous is None or not success:
        return REVIEW_STEPS[0]
    for step in REVIEW_STEPS:
        if step > previous:
            return step
    return previous * 2
