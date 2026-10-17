from collections.abc import Callable

import pytest

from mathquest.engine.content import Skill
from mathquest.engine.mastery import SkillRating
from mathquest.engine.scheduler import (
    FRUSTRATION_MISSES,
    RUN_LENGTH,
    WARMUP_MISSES,
    WARMUP_PROBLEMS,
    Pick,
    Played,
    current_run,
    guard_tier,
    misses_in_a_row,
    pick_skill,
    plan_next,
    plan_practice,
    struggling,
    weakest_prerequisite,
)
from mathquest.engine.skillgraph import SkillGraph


def _skill(sid: str, *prereqs: str) -> Skill:
    return Skill(
        id=sid,
        name=sid,
        region="r",
        prerequisites=prereqs,
        fluency=False,
        anchor=False,
        generator=sid,
        tiers=({"id": 0, "label": "only"},),  # pyright: ignore[reportArgumentType]
        grade_band="K",
        keypad="numpad",
    )


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


def test_current_run_counts_the_newest_skill_and_skips_reviews() -> None:
    ready = ["a", "b"]
    assert current_run([], ready, 0) == (None, 0)
    assert current_run(["b", "a", "a"], ready, 3) == ("a", 2)
    # Problem 4 was a review of the mastered skill "r".
    assert current_run(["a", "a", "a", "a", "r", "a"], ready, 6) == ("a", 5)
    assert current_run(["a", "a", "a", "a", "r"], ready, 5) == ("a", 4)
    assert current_run(["r"], ready, 5) == (None, 0)


def test_current_run_ends_when_the_newest_skill_is_no_longer_ready() -> None:
    # "r" was played on ordinary slots and has just been mastered.
    assert current_run(["a", "r", "r"], ["a", "b"], 3) == (None, 0)


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


def test_a_just_mastered_skill_does_not_hand_its_run_to_an_older_skill() -> None:
    g = SkillGraph([_skill("x"), _skill("y"), _skill("z")])
    ratings = {"x": SkillRating(rating=1.0), "y": SkillRating(rating=-1.0)}
    # "z" was mastered on problem 2; "x" from problem 0 must not resume a run.
    assert pick_skill(g, ratings, {"z"}, [], 3, ["x", "z", "z"]) == "y"


# --- warm-up and frustration guard -------------------------------------------------


def _teaching_graph() -> SkillGraph:
    """a and p are mastered prerequisites of c; b stands alone."""
    return SkillGraph([_skill("a"), _skill("p"), _skill("b"), _skill("c", "a", "p")])


_MASTERED = {"a", "p"}
_RATINGS = {
    "a": SkillRating(rating=3.0),
    "p": SkillRating(rating=1.0),
    "b": SkillRating(rating=2.0),
    "c": SkillRating(rating=-1.0),
}


def _simulate(answers: Callable[[str, int], bool], problems: int) -> list[Pick]:
    """Play ``problems`` problems with a learner whose answer to the n-th problem of a
    skill is ``answers(skill, n)``; returns every pick."""
    graph = _teaching_graph()
    history: list[Played] = []
    picks: list[Pick] = []
    seen: dict[str, int] = {}
    for index in range(problems):
        pick = plan_next(graph, _RATINGS, _MASTERED, [], index, history)
        picks.append(pick)
        n = seen.get(pick.skill_id, 0)
        seen[pick.skill_id] = n + 1
        history.append(Played(pick.skill_id, answers(pick.skill_id, n), warmup_for=pick.warmup_for))
    return picks


def test_a_learner_who_does_well_never_gets_a_warmup() -> None:
    picks = _simulate(lambda _s, _n: True, 30)
    assert all(p.warmup_for is None for p in picks)
    graph = _teaching_graph()
    history: list[Played] = []
    for index, pick in enumerate(picks):
        recent = [h.skill_id for h in history]
        assert pick.skill_id == pick_skill(graph, _RATINGS, _MASTERED, [], index, recent)
        history.append(Played(pick.skill_id, True))


def test_five_misses_warm_up_on_the_weakest_prerequisite_then_return() -> None:
    # Always wrong on c, always right elsewhere; b and c alternate in runs of three.
    picks = _simulate(lambda s, _n: s != "c", 40)
    skills = [p.skill_id for p in picks]
    first = next(i for i, p in enumerate(picks) if p.warmup_for is not None)
    # The fifth miss on c is what triggers it.
    assert skills[:first].count("c") == WARMUP_MISSES
    assert [(p.skill_id, p.warmup_for) for p in picks[first : first + WARMUP_PROBLEMS]] == [
        ("p", "c")
    ] * WARMUP_PROBLEMS  # p (rating 1.0) is weaker than a (3.0)
    assert picks[first + WARMUP_PROBLEMS] == Pick("c")
    # The count starts again after the warm-up: five more misses before the next one.
    second = next(i for i, p in enumerate(picks) if i > first + 1 and p.warmup_for is not None)
    between = skills[first + WARMUP_PROBLEMS : second]
    assert between.count("c") == WARMUP_MISSES


def test_two_stuck_problems_warm_up_too() -> None:
    graph = _teaching_graph()
    history = [Played("c", False, stuck=True), Played("c", False, stuck=True)]
    assert plan_next(graph, _RATINGS, _MASTERED, [], 2, history) == Pick("p", "c")
    one = [Played("c", False, stuck=True), Played("c", True)]
    assert plan_next(graph, _RATINGS, _MASTERED, [], 2, one) == Pick("c")


def test_struggle_counts_misses_not_in_a_row_but_only_scored_ones() -> None:
    mixed = [Played("c", c) for c in (False, True, False, None, False, True, False, False)]
    assert struggling(mixed, "c")
    assert not struggling(mixed[:-1], "c")
    assert not struggling(mixed, "b")


def test_a_skill_without_prerequisites_gets_no_warmup() -> None:
    graph = _teaching_graph()
    history = [Played("b", False)] * WARMUP_MISSES
    ratings = {**_RATINGS, "b": SkillRating(rating=-5.0)}
    assert plan_next(graph, ratings, _MASTERED, [], 5, history) == Pick("b")


def test_weakest_prerequisite_is_the_lowest_rated_then_the_first_listed() -> None:
    graph = _teaching_graph()
    assert weakest_prerequisite(graph, _RATINGS, "c") == "p"
    assert weakest_prerequisite(graph, {}, "c") == "a"
    assert weakest_prerequisite(graph, _RATINGS, "b") is None


def test_an_interrupted_warmup_still_finishes_and_returns() -> None:
    graph = _teaching_graph()
    misses = [Played("c", False)] * WARMUP_MISSES
    # The warm-up problem was closed unanswered: it still counts as given.
    history = [*misses, Played("p", None, warmup_for="c")]
    assert plan_next(graph, _RATINGS, _MASTERED, [], 6, history) == Pick("p", "c")
    history.append(Played("p", True, warmup_for="c"))
    assert plan_next(graph, _RATINGS, _MASTERED, [], 7, history) == Pick("c")


def test_frustration_guard_drops_one_tier_after_three_misses_in_a_row() -> None:
    misses = [Played("c", False)] * FRUSTRATION_MISSES
    assert guard_tier(2, misses, "c") == 1
    assert guard_tier(0, misses, "c") == 0
    assert guard_tier(2, misses[:-1], "c") == 2
    assert guard_tier(2, misses, "b") == 2
    # Another skill's problems and unscored ones in between do not break the run.
    spread = [
        Played("c", False),
        Played("b", True),
        Played("c", None),
        Played("c", False),
        Played("b", False),
        Played("c", False),
    ]
    assert misses_in_a_row(spread, "c") == 3
    assert guard_tier(1, spread, "c") == 0
    # A correct answer ends the run.
    assert guard_tier(2, [*misses, Played("c", True)], "c") == 2
    assert guard_tier(2, [*misses, Played("c", True), *misses[:2]], "c") == 2


def test_a_struggling_learner_meets_easier_problems() -> None:
    """Simulated: tier from a fixed choice of 2, lowered by the guard while missing."""
    history: list[Played] = []
    tiers: list[int] = []
    for n in range(8):
        tier = guard_tier(2, history, "c")
        tiers.append(tier)
        history.append(Played("c", n >= 5))
    assert tiers == [2, 2, 2, 1, 1, 1, 2, 2]


def test_a_due_review_is_not_pushed_back_by_a_warmup() -> None:
    graph = _teaching_graph()
    lead = [Played("b", True)] * 3
    misses = [Played("c", False)] * WARMUP_MISSES
    history = [*lead, *misses]  # indices 0..7
    assert plan_next(graph, _RATINGS, _MASTERED, ["a"], 8, history) == Pick("p", "c")
    history.append(Played("p", True, warmup_for="c"))
    # Index 9 is a review slot: the review comes first.
    assert plan_next(graph, _RATINGS, _MASTERED, ["a"], 9, history) == Pick("a")
    history.append(Played("a", True))
    # The review neither ends nor counts toward the warm-up.
    assert plan_next(graph, _RATINGS, _MASTERED, [], 10, history) == Pick("p", "c")
    history.append(Played("p", True, warmup_for="c"))
    assert plan_next(graph, _RATINGS, _MASTERED, [], 11, history) == Pick("c")


def test_after_a_warmup_play_returns_only_to_a_skill_still_ready_or_due() -> None:
    graph = _teaching_graph()
    misses = [Played("c", False)] * WARMUP_MISSES
    warmup = [Played("p", True, warmup_for="c")] * WARMUP_PROBLEMS
    history = [*misses, *warmup]
    # p was demoted during the warm-up: c is no longer ready, so choose normally.
    demoted = {"a"}
    pick = plan_next(graph, _RATINGS, demoted, [], len(history), history)
    assert pick.skill_id != "c" and pick.warmup_for is None
    # c is mastered but due for review: return to it.
    mastered = {"a", "p", "c"}
    assert plan_next(graph, _RATINGS, mastered, ["c"], len(history), history) == Pick("c")


def test_a_capped_history_uses_the_true_problem_index() -> None:
    """The scheduler sees only the newest problems; review slots still come from the
    session's real problem index."""
    graph = _teaching_graph()
    ratings = {**_RATINGS, "b": SkillRating(rating=-9.0)}
    full = [Played("b", True)] * 52 + [
        Played("c", True),  # 52
        Played("c", True),  # 53
        Played("a", True),  # 54: a review on a review slot
        Played("c", True),  # 55
    ]
    capped = full[-50:]
    # c has had three in its run (the review inside does not break it), so b is next.
    assert plan_next(graph, ratings, _MASTERED, [], 56, capped) == Pick("b")
    assert plan_next(graph, ratings, _MASTERED, [], 56, full) == Pick("b")
    # Index 59 is a review slot, whatever the length of the history passed in.
    assert plan_next(graph, ratings, _MASTERED, ["a"], 59, capped[-10:]) == Pick("a")


def _practice(focus: list[str], answers: Callable[[str, int], bool], problems: int) -> list[Pick]:
    graph = _teaching_graph()
    history: list[Played] = []
    picks: list[Pick] = []
    seen: dict[str, int] = {}
    for _ in range(problems):
        pick = plan_practice(graph, _RATINGS, focus, history)
        picks.append(pick)
        n = seen.get(pick.skill_id, 0)
        seen[pick.skill_id] = n + 1
        history.append(Played(pick.skill_id, answers(pick.skill_id, n), warmup_for=pick.warmup_for))
    return picks


def test_practice_on_one_skill_stays_on_it_with_no_reviews() -> None:
    picks = _practice(["b"], lambda _s, _n: True, 12)
    assert picks == [Pick("b")] * 12


def test_practice_rotates_in_runs_starting_with_the_weakest() -> None:
    picks = _practice(["a", "b", "p"], lambda _s, _n: True, 9)
    # p (1.0) is weakest, then b (2.0) is the weakest of the others, then p again.
    expected = ["p"] * RUN_LENGTH + ["b"] * RUN_LENGTH + ["p"] * RUN_LENGTH
    assert [p.skill_id for p in picks] == expected


def test_practice_warms_up_a_struggling_skill_and_returns_to_it() -> None:
    picks = _practice(["c"], lambda s, _n: s != "c", WARMUP_MISSES + WARMUP_PROBLEMS + 1)
    assert [p.skill_id for p in picks[:WARMUP_MISSES]] == ["c"] * WARMUP_MISSES
    warmup = picks[WARMUP_MISSES : WARMUP_MISSES + WARMUP_PROBLEMS]
    assert warmup == [Pick("p", "c")] * WARMUP_PROBLEMS
    assert picks[-1] == Pick("c")


def test_practice_ignores_skills_missing_from_the_graph() -> None:
    graph = _teaching_graph()
    assert plan_practice(graph, _RATINGS, ["gone", "b"], []) == Pick("b")
    with pytest.raises(ValueError):
        plan_practice(graph, _RATINGS, ["gone"], [])


def test_a_warm_up_on_a_skill_the_graph_lacks_is_ignored() -> None:
    history = [Played("ghost", None, warmup_for="add_within_10")]
    pick = plan_next(_graph(), {}, set(), [], 3, history)
    assert pick.skill_id in _graph().skills


# --- started skills stay ready ------------------------------------------------------


def test_pick_skill_offers_a_started_skill_whose_prerequisite_is_not_mastered() -> None:
    g = _graph()
    ratings = {
        "a": SkillRating(rating=1.0),
        "b": SkillRating(rating=1.0),
        "c": SkillRating(rating=-1.0),
    }
    assert pick_skill(g, ratings, set(), [], 0) == "a"
    assert pick_skill(g, ratings, set(), [], 0, started={"c"}) == "c"


def test_pick_skill_offers_a_started_skill_that_is_also_implied() -> None:
    g = _graph()
    # "c" is mastered, so "a" is implied; "a" was played (and failed a review), so it is offered.
    ratings = {"a": SkillRating(rating=-1.0), "b": SkillRating(rating=1.0)}
    assert pick_skill(g, ratings, {"c"}, [], 0) == "b"
    assert pick_skill(g, ratings, {"c"}, [], 0, started={"a", "c"}) == "a"


def test_a_finished_warmup_returns_to_a_started_skill_that_is_not_otherwise_ready() -> None:
    g = SkillGraph([_skill("a"), _skill("b"), _skill("c", "a"), _skill("p")])
    ratings = {"a": SkillRating(rating=5.0), "b": SkillRating(rating=5.0), "p": SkillRating()}
    history = [Played("p", True, warmup_for="c")] * WARMUP_PROBLEMS
    without = plan_next(g, ratings, set(), [], WARMUP_PROBLEMS, history)
    with_started = plan_next(g, ratings, set(), [], WARMUP_PROBLEMS, history, {"c"})
    assert without.skill_id != "c"
    assert with_started == Pick("c")
