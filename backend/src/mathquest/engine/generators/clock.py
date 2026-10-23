# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false
"""Telling time to the hour and half hour (1.MD.B.3), without a picture.

A problem describes the clock in words and numerals: where the short hand and the long hand
point ("The short hand points to 7. The long hand points to 12."), or what a digital clock
shows ("4:30"). The answer is always a whole number: an hour, or a count of minutes or half
hours. The picture of a clock is for the lesson, which can show one.

Tier 0 is the hour (long hand on 12), tier 1 is half past (long hand on 6), and tier 2 mixes
the hour and the half hour and counts minutes and half hours between two times.
"""

import random
from collections.abc import Callable

import sympy

from mathquest.engine.generators._util import Built, SkillGenerator, named_wrongs, text
from mathquest.engine.types import AnswerForm

_Int = sympy.Integer

_NUDGE_HOUR = "The short hand tells the hour. The long hand tells the minutes."
_NUDGE_HALF = "At half past, the long hand points to six. The short hand sits between two hours."
_NUDGE_AFTER = "Think about the clock face. The hour hand moves slowly around it."
_NUDGE_SPAN = "Look at the start and the end. Count the half hours between them."


def _hour(n: int) -> int:
    """``n`` as an hour on a clock face: 1 to 12, so 13 is 1 and 0 is 12."""
    return (n - 1) % 12 + 1


def _built(
    prompt: str,
    answer: int,
    wrong: list[tuple[str, int]],
    nudge: str,
    step: str,
    worked: str,
    *,
    hour: int,
) -> Built:
    return Built(
        prompt=(text(prompt),),
        answer=_Int(answer),
        wrong=named_wrongs(wrong),
        values={
            "hour": hour,
            "answer": answer,
            "nudge": nudge,
            "step": step,
            "worked": worked,
        },
    )


# --- tier 0: the hour ---------------------------------------------------------------------


def _hands_on_the_hour(rng: random.Random) -> Built:
    h = rng.randint(1, 12)
    return _built(
        f"The short hand points to {h}. The long hand points to 12. What hour is it?",
        h,
        [
            ("gave_the_long_hand_number", 12),
            ("off_by_one_hour", _hour(h + rng.choice((1, -1)))),
        ],
        _NUDGE_HOUR,
        "Which hand is the short one? Read the number it points to.",
        f"The short hand points to {h}. So it is {h} o'clock.",
        hour=h,
    )


def _hour_later(rng: random.Random) -> Built:
    h = rng.randint(1, 12)
    answer = _hour(h + 1)
    return _built(
        f"It is {h} o'clock now. What hour will it be in one hour?",
        answer,
        [("gave_the_hour", h), ("went_the_wrong_way", _hour(h - 1))],
        _NUDGE_AFTER,
        "Later means the short hand moves forward to the next number.",
        f"One hour after {h} o'clock is {answer} o'clock.",
        hour=h,
    )


def _hour_before(rng: random.Random) -> Built:
    h = rng.randint(1, 12)
    answer = _hour(h - 1)
    return _built(
        f"School starts at {h} o'clock. What hour is it one hour before?",
        answer,
        [("gave_the_hour", h), ("went_the_wrong_way", _hour(h + 1))],
        _NUDGE_AFTER,
        "Before means the short hand goes back to the number before.",
        f"One hour before {h} o'clock is {answer} o'clock.",
        hour=h,
    )


# --- tier 1: half past --------------------------------------------------------------------


def _hands_half_past(rng: random.Random) -> Built:
    h = rng.randint(1, 12)
    return _built(
        f"The long hand points to 6. The short hand is between {h} and {_hour(h + 1)}. "
        "It is half past what hour?",
        h,
        [("gave_the_long_hand_number", 6), ("off_by_one_hour", _hour(h + 1))],
        _NUDGE_HALF,
        "The short hand has passed one hour. It has not reached the next one.",
        f"The short hand is past {h}. So it is half past {h}.",
        hour=h,
    )


def _digital_half_past(rng: random.Random) -> Built:
    h = rng.randint(1, 12)
    return _built(
        f"A clock shows {h}:30. It is half past what hour?",
        h,
        [("gave_the_minutes", 30), ("off_by_one_hour", _hour(h + 1))],
        _NUDGE_HALF,
        "In a digital time, the number before the colon is the hour.",
        f"The hour is {h}. So it is half past {h}.",
        hour=h,
    )


def _half_past_game(rng: random.Random) -> Built:
    h = rng.randint(1, 12)
    answer = _hour(h + 1)
    return _built(
        f"A game starts at half past {h}. It lasts one hour. It ends at half past what hour?",
        answer,
        [("gave_the_hour", h), ("went_the_wrong_way", _hour(h - 1))],
        _NUDGE_AFTER,
        "One hour later keeps the long hand on six. The short hand moves on.",
        f"One hour after half past {h} is half past {answer}.",
        hour=h,
    )


def _minutes_after_hour(rng: random.Random) -> Built:
    h = rng.randint(1, 12)
    return _built(
        f"A clock shows {h}:30. How many minutes after {h} o'clock is that?",
        30,
        [("gave_the_hour", h), ("gave_the_long_hand_number", 6)],
        "Half past means half of an hour has gone by.",
        "An hour has sixty minutes. Think about half of them.",
        f"Half an hour after {h} o'clock is half past {h}. That is 30 minutes.",
        hour=h,
    )


# --- tier 2: the hour or the half hour -----------------------------------------------------


def _minutes_from_hands(rng: random.Random) -> Built:
    h = rng.randint(1, 12)
    half = rng.choice((True, False))
    first = (
        f"The short hand is just past {h}. The long hand points to 6."
        if half
        else f"The short hand points to {h}. The long hand points to 12."
    )
    answer = 30 if half else 0
    return _built(
        f"{first} How many minutes after {h} o'clock is it?",
        answer,
        [
            ("gave_the_long_hand_number", 6 if half else 12),
            ("gave_the_hour", h),
        ],
        "The long hand tells the minutes. Where does it point?",
        "On twelve no minutes have gone by. On six a half hour has gone by.",
        f"The long hand points to {6 if half else 12}. So {answer} minutes have gone by.",
        hour=h,
    )


def _span(rng: random.Random) -> tuple[int, int, int, str, str]:
    """A start on the hour, an end 1 to 5 half hours later, and both as digital times."""
    start = rng.randint(1, 7)
    halves = rng.randint(1, 5)
    end_hour, end_half = divmod(start * 2 + halves, 2)
    return start, halves, end_hour, f"{start}:00", f"{end_hour}:{'30' if end_half else '00'}"


def _half_hours_between(rng: random.Random) -> Built:
    start, halves, _, begin, finish = _span(rng)
    return _built(
        f"A walk starts at {begin} and ends at {finish}. How many half hours is that?",
        halves,
        [
            ("counted_whole_hours", halves // 2),
            ("gave_the_minutes", halves * 30),
        ],
        _NUDGE_SPAN,
        "Jump from the start to the end. Each jump is a half hour.",
        f"Count the half hours from {begin} to {finish}. The count is {halves}.",
        hour=start,
    )


def _minutes_between(rng: random.Random) -> Built:
    start, halves, _, begin, finish = _span(rng)
    return _built(
        f"A film starts at {begin} and ends at {finish}. How many minutes long is it?",
        halves * 30,
        [
            ("gave_the_half_hours", halves),
            ("counted_whole_hours", 60 * (halves // 2)),
        ],
        _NUDGE_SPAN,
        "Count the half hours from the start to the end. Each one is half an hour.",
        f"Count the half hours from {begin} to {finish}. Each is half an hour. "
        f"So the film is {halves * 30} minutes long.",
        hour=start,
    )


_FORMS: tuple[tuple[Callable[[random.Random], Built], ...], ...] = (
    (_hands_on_the_hour, _hands_on_the_hour, _hour_later, _hour_before),
    (
        _hands_half_past,
        _digital_half_past,
        _half_past_game,
        _hands_half_past,
        _minutes_after_hour,
    ),
    (_minutes_from_hands, _half_hours_between, _minutes_between),
)


def _build_clock(rng: random.Random, tier: int) -> Built:
    return rng.choice(_FORMS[tier])(rng)


def generators() -> list[SkillGenerator]:
    return [
        SkillGenerator(
            "clock_hours",
            -1.5,
            AnswerForm.INTEGER,
            _build_clock,
            (
                "gave_the_long_hand_number",
                "off_by_one_hour",
                "gave_the_hour",
                "went_the_wrong_way",
                "gave_the_minutes",
                "counted_whole_hours",
                "gave_the_half_hours",
            ),
            first_try_counts=True,
        )
    ]
