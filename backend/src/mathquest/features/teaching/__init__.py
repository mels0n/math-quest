"""Teaching slice: lessons and their try-its, hints, explanations and the stuck log."""

from mathquest.features.teaching.help import (
    STUCK_LOG_LIMIT,
    STUCK_LOG_MAX,
    next_explanation,
    next_hint,
    stuck_csv,
    stuck_log,
)
from mathquest.features.teaching.schema import (
    ExplanationOut,
    HintOut,
    LessonOut,
    SeenOut,
    StuckProblemOut,
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
    "STUCK_LOG_LIMIT",
    "STUCK_LOG_MAX",
    "ExplanationOut",
    "HintOut",
    "LessonOut",
    "SeenOut",
    "StuckProblemOut",
    "TryAnswerOut",
    "TryProblemOut",
    "answer_try",
    "get_lesson",
    "mark_seen",
    "next_explanation",
    "next_hint",
    "start_try",
    "stuck_csv",
    "stuck_log",
]
