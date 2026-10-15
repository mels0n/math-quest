"""Chooses which skill a player works on next."""

from collections.abc import Mapping, Sequence

from mathquest.engine.mastery import SkillRating
from mathquest.engine.skillgraph import SkillGraph

REVIEW_EVERY = 5
RUN_LENGTH = 3


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
