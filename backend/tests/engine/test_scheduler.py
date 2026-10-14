import pytest

from mathquest.engine.mastery import SkillRating
from mathquest.engine.scheduler import pick_skill
from mathquest.engine.skillgraph import Skill, SkillGraph


def _skill(sid: str, *prereqs: str) -> Skill:
    return Skill(id=sid, name=sid, region="r", prerequisites=prereqs, fluency=False, anchor=False)


def _graph() -> SkillGraph:
    return SkillGraph([_skill("a"), _skill("b"), _skill("c", "a")])


def test_pick_skill_review_every_fifth() -> None:
    g = _graph()
    assert pick_skill(g, {}, set(), ["a"], 4) == "a"
    assert pick_skill(g, {}, set(), ["c"], 9) == "c"
    assert pick_skill(g, {}, set(), ["c"], 3) == "a"
    assert pick_skill(g, {}, set(), [], 4) == "a"


def test_pick_skill_lowest_rating_then_topo() -> None:
    g = _graph()
    ratings = {"a": SkillRating(rating=1.0), "b": SkillRating(rating=-1.0)}
    assert pick_skill(g, ratings, set(), [], 0) == "b"
    assert pick_skill(g, {}, set(), [], 0) == "a"


def test_pick_skill_nothing_ready_falls_back() -> None:
    g = _graph()
    done = {"a", "b", "c"}
    assert pick_skill(g, {}, done, [], 0) == "a"
    assert pick_skill(g, {}, done, ["c", "b"], 0) == "c"


def test_pick_skill_empty_graph_raises() -> None:
    with pytest.raises(ValueError, match="no skills available"):
        pick_skill(SkillGraph([]), {}, set(), [], 0)
