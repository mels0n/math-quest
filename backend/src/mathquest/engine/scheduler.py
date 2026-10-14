"""Chooses which skill a player works on next."""

from collections.abc import Mapping, Sequence

from mathquest.engine.mastery import SkillRating
from mathquest.engine.skillgraph import SkillGraph

REVIEW_EVERY = 5


def pick_skill(
    graph: SkillGraph,
    ratings: Mapping[str, SkillRating],
    mastered: set[str],
    due_reviews: Sequence[str],
    problem_index: int,
) -> str:
    """Pick the next skill.

    `due_reviews` must already be ordered oldest review first.
    Every fifth problem (problem_index % 5 == 4) takes the first due review.
    Otherwise the ready skill with the lowest rating wins (unrated skills count as
    rating 0.0); ties go to the earlier skill in topological order. When nothing is
    ready, the first due review is used, and with no due review either, the mastered
    skill earliest in topological order.
    """
    if due_reviews and problem_index % REVIEW_EVERY == REVIEW_EVERY - 1:
        return due_reviews[0]
    ready = graph.ready(mastered)
    if ready:
        return min(ready, key=lambda sid: ratings.get(sid, SkillRating()).rating)
    if due_reviews:
        return due_reviews[0]
    for sid in graph.topo_order():
        if sid in mastered:
            return sid
    raise ValueError("no skills available")
