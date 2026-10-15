import pytest

from mathquest.engine.mastery import SkillRating
from mathquest.engine.scheduler import RUN_LENGTH, current_run, pick_skill
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


def test_current_run_counts_the_newest_ready_skill_and_skips_reviews() -> None:
    ready = ["a", "b"]
    assert current_run([], ready) == (None, 0)
    assert current_run(["b", "a", "a"], ready) == ("a", 2)
    assert current_run(["a", "a", "r", "a"], ready) == ("a", 3)
    assert current_run(["a", "r"], ready) == ("a", 1)
    assert current_run(["r"], ready) == (None, 0)


def test_pick_skill_stays_on_a_skill_for_a_short_run() -> None:
    g = _graph()
    # "b" is rated lowest, but "a" has had fewer than RUN_LENGTH problems in a row.
    ratings = {"a": SkillRating(rating=1.0), "b": SkillRating(rating=-1.0)}
    assert RUN_LENGTH == 3
    assert pick_skill(g, ratings, set(), [], 1, ["a"]) == "a"
    assert pick_skill(g, ratings, set(), [], 2, ["a", "a"]) == "a"
    assert pick_skill(g, ratings, set(), [], 3, ["a", "a", "a"]) == "b"
    assert pick_skill(g, ratings, set(), [], 3, ["b", "a", "a"]) == "a"


def test_a_review_does_not_break_a_run() -> None:
    g = _graph()
    ratings = {"a": SkillRating(rating=-1.0), "b": SkillRating(rating=1.0)}
    mastered = {"a"}  # "a" is reviewed; "b" and "c" are ready
    ratings["c"] = SkillRating(rating=-2.0)
    # Problem 4 is the review slot.
    assert pick_skill(g, ratings, mastered, ["a"], 4, ["b", "b"]) == "a"
    # After the review the run on "b" carries on, although "c" is rated lower.
    assert pick_skill(g, ratings, mastered, ["a"], 5, ["b", "b", "a"]) == "b"
    assert pick_skill(g, ratings, mastered, ["a"], 6, ["b", "b", "a", "b"]) == "c"


def test_a_run_ends_when_its_skill_is_no_longer_ready() -> None:
    g = _graph()
    ratings = {"b": SkillRating(rating=1.0), "c": SkillRating(rating=0.5)}
    # "a" was just mastered: its run is over and the lowest-rated ready skill is picked.
    assert pick_skill(g, ratings, {"a"}, [], 2, ["a", "a"]) == "c"
