"""Teaching slice: lessons, whether a player has seen them, and each lesson's try-it."""

from mathquest.features.teaching.schema import (
    LessonOut,
    SeenOut,
    TryAnswerOut,
    TryProblemOut,
)
from mathquest.features.teaching.service import (
    answer_try,
    get_lesson,
    mark_seen,
    start_try,
)

__all__ = [
    "LessonOut",
    "SeenOut",
    "TryAnswerOut",
    "TryProblemOut",
    "answer_try",
    "get_lesson",
    "mark_seen",
    "start_try",
]
