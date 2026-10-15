"""Chooses which skill a player works on next."""

from collections.abc import Mapping, Sequence

from mathquest.engine.mastery import SkillRating
from mathquest.engine.skillgraph import SkillGraph

REVIEW_EVERY = 5
RUN_LENGTH = 3


def current_run(recent: Sequence[str], ready: Sequence[str]) -> tuple[str | None, int]:
    """The skill of the run in progress and how many problems it has had so far.

    `recent` is the session's skill ids, newest last. Entries for skills that are not
    ready (reviews of mastered skills) are skipped, so a review inside a run does not
    end it. Returns (None, 0) when no recent skill is ready.
    """
    ready_set = set(ready)
    skill: str | None = None
    length = 0
    for sid in reversed(recent):
        if sid not in ready_set:
            continue
        if skill is None:
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
    Otherwise, when the newest ready skill in `recent` has had fewer than RUN_LENGTH
    problems in a row (reviews in between do not count or break the run), it is picked
    again, so a short run on one skill shows progress before the scheduler rotates.
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
        skill, length = current_run(recent, ready)
        if skill is not None and length < RUN_LENGTH:
            return skill
        return min(ready, key=lambda sid: ratings.get(sid, SkillRating()).rating)
    if due_reviews:
        return due_reviews[0]
    for sid in graph.topo_order():
        if sid in mastered:
            return sid
    raise ValueError("no skills available")
