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
    assert len(graph.skills) == 20
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
        "add_2digit_regroup",
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
    # teen_numbers sits only under place_value_tens_ones among the built skills.
    assert graph.implied({"place_value_tens_ones"}) == {"teen_numbers"}
    assert "teen_numbers" not in graph.ready({"place_value_tens_ones"})
    # With a prerequisite chain above it known too, what builds on it opens up.
    assert "place_value_hundreds" in graph.ready({"place_value_tens_ones"})
    # One dependent still unplayed keeps count_to_10 an ordinary ready skill.
    known = {"add_within_10", "sub_within_10"}
    assert "count_to_10" not in graph.implied(known)
    assert "count_to_10" in graph.ready(known)
    # Every dependent known: nothing is implied below a skill with no dependents.
    assert graph.implied(set()) == set()


def test_implied_skills_chain_down_the_graph() -> None:
    graph = _graph()
    everything_above = {
        "add_within_10",
        "sub_within_10",
        "count_to_100",
        "compare_groups",
        "compare_numbers_20",
        "teen_numbers",
    }
    assert {"count_to_10", "count_to_20"} <= graph.implied(everything_above)
