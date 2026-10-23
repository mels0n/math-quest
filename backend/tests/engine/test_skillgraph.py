from pathlib import Path

import pytest

from mathquest.engine.content import ContentError, Skill, load_pack
from mathquest.engine.skillgraph import SkillGraph

PACK = Path(__file__).resolve().parents[2] / "content" / "packs" / "k8-core"


def _graph() -> SkillGraph:
    return SkillGraph(load_pack(PACK).skills.values())


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


def test_load_slice_pack() -> None:
    graph = _graph()
    assert len(graph.skills) == 42
    assert graph.ready(set()) == ["count_to_10", "equivalent_fractions"]
    assert graph.ready({"count_to_10"}) == [
        "add_within_10",
        "sub_within_10",
        "count_to_20",
        "compare_groups",
        "equivalent_fractions",
    ]
    order = graph.topo_order()
    for skill_id in graph.skills:
        for prereq in graph.prerequisites(skill_id):
            assert order.index(prereq) < order.index(skill_id)
    anchors = {s.id for s in graph.skills.values() if s.anchor}
    assert anchors == {
        "count_to_10",
        "add_within_10",
        "add_within_20",
        "place_value_tens_ones",
        "missing_number_20",
        "add_2digit_regroup",
        "sub_2digit_regroup",
        "add_fractions_unlike",
    }


def test_cycle_rejected() -> None:
    with pytest.raises(ContentError) as exc:
        SkillGraph([_skill("alpha_skill", "beta_skill"), _skill("beta_skill", "alpha_skill")])
    assert "alpha_skill" in str(exc.value)
    assert "beta_skill" in str(exc.value)


def test_missing_prereq_rejected() -> None:
    with pytest.raises(ContentError, match="ghost"):
        SkillGraph([_skill("a", "ghost")])


def test_duplicate_rejected() -> None:
    with pytest.raises(ContentError, match="duplicate"):
        SkillGraph([_skill("a"), _skill("a")])


def test_ready_after_mastery() -> None:
    graph = _graph()
    assert "add_within_20" in graph.ready({"add_within_10"})
    assert "add_within_10" not in graph.ready({"add_within_10"})


def test_pack_skills_name_their_keypad() -> None:
    keypads = {sid: s.keypad for sid, s in _graph().skills.items()}
    assert keypads["add_fractions_unlike"] == "fraction"
    # The comparing skills are typed too: their button questions are bank items beside them.
    assert {k for sid, k in keypads.items() if sid != "add_fractions_unlike"} == {"numpad"}


def test_promoted_skills_sit_under_the_skills_they_unlock() -> None:
    skills = _graph().skills
    assert "count_to_10" in skills["add_within_10"].prerequisites
    assert "count_to_10" in skills["sub_within_10"].prerequisites
    assert "teen_numbers" in skills["place_value_tens_ones"].prerequisites
    assert skills["place_value_hundreds"].prerequisites == ("place_value_tens_ones",)
    assert skills["compare_numbers_100"].prerequisites == (
        "place_value_tens_ones",
        "compare_numbers_20",
    )


def test_a_started_skill_stays_ready_whatever_prerequisites_it_gained() -> None:
    graph = _graph()
    assert "add_within_10" not in graph.ready(set())
    assert "add_within_10" in graph.ready(set(), {"add_within_10"})
    # Mastered skills are never offered, started or not.
    assert "add_within_10" not in graph.ready({"add_within_10"}, {"add_within_10"})


def test_a_skill_under_what_the_learner_knows_is_implied() -> None:
    graph = _graph()
    # Everything that place_value_tens_ones builds on, directly or not.
    assert graph.implied({"place_value_tens_ones"}) == {
        "teen_numbers",
        "count_to_20",
        "count_to_10",
    }
    assert "teen_numbers" not in graph.ready({"place_value_tens_ones"})
    assert "place_value_hundreds" in graph.ready({"place_value_tens_ones"})
    # Nothing known, nothing implied.
    assert graph.implied(set()) == set()


def test_a_grade_two_learner_from_before_counting_existed_is_not_sent_back() -> None:
    graph = _graph()
    old = {"add_within_10", "add_within_20", "add_2digit_regroup"}
    assert {"count_to_10", "count_to_20", "teen_numbers"} <= graph.implied(old)
    assert not {"count_to_10", "count_to_20"} & set(graph.ready(old))
    # What builds on counting that they have not met stays open to them.
    assert "compare_groups" in graph.ready(old)
    # With only add_within_10 known, count_to_20 is under nothing they know.
    assert graph.implied({"add_within_10"}) == {"count_to_10"}
    assert "count_to_20" in graph.ready({"add_within_10"})


def test_a_skill_whose_dependents_are_all_unplayed_is_not_implied() -> None:
    graph = _graph()
    known = {"add_within_10"}
    for sid in ("count_to_20", "compare_groups", "sub_within_10", "teen_numbers"):
        assert sid not in graph.implied(known)
    assert graph.implied(known) == {"count_to_10"}


def test_a_started_skill_under_a_mastered_one_is_still_offered() -> None:
    """A placed child fails the first review of add_within_10 while add_within_20 counts as
    mastered: add_within_10 is learning again and must be offered, not implied away."""
    graph = _graph()
    mastered = {"count_to_10", "add_within_20"}
    started = mastered | {"add_within_10"}
    assert "add_within_10" in graph.implied(mastered)
    assert "add_within_10" in graph.ready(mastered, started)
    # Never played, it is implied and stays out.
    assert "add_within_10" not in graph.ready(mastered, mastered)


def test_a_demoted_skill_under_a_placed_high_learner_is_offered() -> None:
    graph = _graph()
    mastered = {"add_2digit_regroup", "add_within_20", "count_to_10"}
    ready = graph.ready(mastered, mastered | {"add_within_10"})
    assert "add_within_10" in ready
    assert "add_within_10" not in graph.ready(mastered, mastered)


def test_a_slipped_prerequisite_and_the_skill_that_needs_it_are_both_offered() -> None:
    """add_within_10 slipped back to learning while add_within_20 is being learned."""
    graph = _graph()
    started = {"count_to_10", "add_within_10", "add_within_20"}
    ready = graph.ready({"count_to_10"}, started)
    assert "add_within_10" in ready and "add_within_20" in ready
    # Without any record of play, add_within_20 would wait for add_within_10.
    assert "add_within_20" not in graph.ready({"count_to_10"})
