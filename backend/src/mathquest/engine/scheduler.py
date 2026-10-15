"""Chooses which skill a player works on next, and when to step back.

`pick_skill` is the plain choice. `plan_next` adds two teaching rules on top, using only
the session's history (passed in, newest last):

- Warm-up. A skill the learner keeps struggling with in this session (WARMUP_STUCK stuck
  problems, or WARMUP_MISSES problems scored wrong, counted since its last warm-up) gets
  WARMUP_PROBLEMS problems of its weakest prerequisite (the lowest rating among its
  prerequisites; ties go to the first listed) before play returns to it. A skill with no
  prerequisites gets no warm-up.
- Frustration guard (`guard_tier`). After FRUSTRATION_MISSES scored misses in a row on a
  skill in this session, its next problem is one tier easier than `choose_tier` picks
  (never below tier 0).

Both rules are pure: the caller reads the history and stores which problems are
warm-ups. See docs/adr/0014-teaching-flow.md.
"""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from mathquest.engine.mastery import SkillRating
from mathquest.engine.skillgraph import SkillGraph

REVIEW_EVERY = 5
RUN_LENGTH = 3
WARMUP_PROBLEMS = 2
WARMUP_STUCK = 2
WARMUP_MISSES = 5
FRUSTRATION_MISSES = 3


def _review_slot(index: int) -> bool:
    return index % REVIEW_EVERY == REVIEW_EVERY - 1


def current_run(
    recent: Sequence[str], ready: Sequence[str], problem_index: int
) -> tuple[str | None, int]:
    """The skill of the run in progress and how many problems it has had so far.

    `recent` is the session's latest skill ids, newest last, and `problem_index` the
    index of the problem about to be picked, so `recent[-1]` was problem
    `problem_index - 1`. An entry is a review when it sat on a review slot and its skill
    is not ready (it is mastered); reviews are skipped, so one inside a run neither
    counts nor ends it. The run belongs to the newest entry that is not a review. If that
    skill is no longer ready (it was just mastered), there is no run: (None, 0).
    """
    ready_set = set(ready)
    skill: str | None = None
    length = 0
    for back, sid in enumerate(reversed(recent)):
        if _review_slot(problem_index - 1 - back) and sid not in ready_set:
            continue
        if skill is None:
            if sid not in ready_set:
                return None, 0
            skill = sid
        elif sid != skill:
            break
        length += 1
    return skill, length


def pick_skill(
    graph: SkillGraph,
    ratings: Mapping[str, SkillRating],
    mastered: set[str],
    due_reviews: Sequence[str],
    problem_index: int,
    recent: Sequence[str] = (),
) -> str:
    """Pick the next skill.

    `due_reviews` must already be ordered oldest review first. `recent` holds the
    session's last skill ids, newest last.
    Every fifth problem (problem_index % 5 == 4) takes the first due review.
    Otherwise, when the skill of the newest problem that was not a review is still
    ready and has had fewer than RUN_LENGTH problems in a row (see `current_run`), it is
    picked again, so a short run on one skill shows progress before the scheduler
    rotates. `recent` must be the session's latest problems with none left out.
    Otherwise the ready skill with the lowest rating wins; ties go to the earlier skill
    in topological order. Ratings come from `ratings`: the caller passes the start
    rating (`initial_rating`) for skills not yet played, and a skill missing from the
    mapping counts as 0.0. When nothing is ready, the first due review is used, and
    with no due review either, the mastered skill earliest in topological order.
    """
    if due_reviews and problem_index % REVIEW_EVERY == REVIEW_EVERY - 1:
        return due_reviews[0]
    ready = graph.ready(mastered)
    if ready:
        skill, length = current_run(recent, ready, problem_index)
        if skill is not None and length < RUN_LENGTH:
            return skill
        return min(ready, key=lambda sid: ratings.get(sid, SkillRating()).rating)
    if due_reviews:
        return due_reviews[0]
    for sid in graph.topo_order():
        if sid in mastered:
            return sid
    raise ValueError("no skills available")


@dataclass(frozen=True)
class Played:
    """One problem issued earlier in the session.

    ``correct`` is None while it is open or when it was closed unanswered. ``stuck`` is
    set when it was scored wrong after every explanation of its skill had been shown.
    ``warmup_for`` names the skill a warm-up problem was inserted for.
    """

    skill_id: str
    correct: bool | None
    stuck: bool = False
    warmup_for: str | None = None


@dataclass(frozen=True)
class Pick:
    """The next skill, and the skill it warms up for when it is a warm-up problem."""

    skill_id: str
    warmup_for: str | None = None


def _since_warmup(history: Sequence[Played], skill_id: str) -> Sequence[Played]:
    """The part of ``history`` after the last warm-up problem inserted for ``skill_id``."""
    for back in range(len(history) - 1, -1, -1):
        if history[back].warmup_for == skill_id:
            return history[back + 1 :]
    return history


def struggling(history: Sequence[Played], skill_id: str) -> bool:
    """WARMUP_STUCK stuck problems or WARMUP_MISSES misses on the skill since its last
    warm-up in this session."""
    mine = [p for p in _since_warmup(history, skill_id) if p.skill_id == skill_id]
    stuck = sum(1 for p in mine if p.stuck)
    misses = sum(1 for p in mine if p.correct is False)
    return stuck >= WARMUP_STUCK or misses >= WARMUP_MISSES


def weakest_prerequisite(
    graph: SkillGraph, ratings: Mapping[str, SkillRating], skill_id: str
) -> str | None:
    """The prerequisite with the lowest rating (first listed on a tie); None without one."""
    prereqs = graph.prerequisites(skill_id)
    if not prereqs:
        return None
    return min(prereqs, key=lambda sid: ratings.get(sid, SkillRating()).rating)


def _warmup_tail(history: Sequence[Played], problem_index: int) -> list[Played]:
    """The warm-up problems at the end of ``history`` for one skill, oldest first.

    A review given on a review slot during a warm-up is skipped, so it neither ends nor
    counts toward the warm-up. ``history`` is the session's latest problems, newest last,
    so ``history[-1]`` was problem ``problem_index - 1``."""
    tail: list[Played] = []
    target: str | None = None
    for back, played in enumerate(reversed(history)):
        if played.warmup_for is None and _review_slot(problem_index - 1 - back):
            continue
        if played.warmup_for is None or (target is not None and played.warmup_for != target):
            break
        target = played.warmup_for
        tail.append(played)
    return list(reversed(tail))


def plan_next(
    graph: SkillGraph,
    ratings: Mapping[str, SkillRating],
    mastered: set[str],
    due_reviews: Sequence[str],
    problem_index: int,
    history: Sequence[Played],
) -> Pick:
    """The next skill.

    A review slot with a review due takes it first, so a warm-up never pushes a review
    back (the warm-up carries on after it). A warm-up in progress continues until it has
    WARMUP_PROBLEMS problems; then play returns to the skill it was for if that skill is
    still ready or due for review, and otherwise chooses normally. Otherwise `pick_skill`
    chooses, and a skill the learner is struggling with (`struggling`) starts a warm-up on
    its weakest prerequisite instead. ``history`` is the session's latest problems
    (newest last, none left out) and ``problem_index`` the true index of the problem
    being picked, which may be larger than ``len(history)`` when the history is capped.
    """
    if due_reviews and _review_slot(problem_index):
        return Pick(due_reviews[0])
    tail = _warmup_tail(history, problem_index)
    if tail:
        target = tail[-1].warmup_for
        assert target is not None
        if len(tail) < WARMUP_PROBLEMS:
            return Pick(tail[-1].skill_id, target)
        if target in graph.skills and (target in graph.ready(mastered) or target in due_reviews):
            return Pick(target)
    recent = [p.skill_id for p in history]
    skill = pick_skill(graph, ratings, mastered, due_reviews, problem_index, recent)
    if struggling(history, skill):
        prereq = weakest_prerequisite(graph, ratings, skill)
        if prereq is not None:
            return Pick(prereq, skill)
    return Pick(skill)


def misses_in_a_row(history: Sequence[Played], skill_id: str) -> int:
    """Scored misses on ``skill_id`` at the end of its scored history in this session;
    other skills' problems and unscored ones in between do not break the run."""
    run = 0
    for played in reversed(history):
        if played.skill_id != skill_id or played.correct is None:
            continue
        if played.correct:
            break
        run += 1
    return run


def guard_tier(tier: int, history: Sequence[Played], skill_id: str) -> int:
    """``tier`` one lower (floor 0) after FRUSTRATION_MISSES scored misses in a row on the
    skill in this session; ``tier`` unchanged otherwise."""
    if misses_in_a_row(history, skill_id) >= FRUSTRATION_MISSES:
        return max(0, tier - 1)
    return tier
