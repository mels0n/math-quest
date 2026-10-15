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
    assert len(graph.skills) == 9
    assert graph.ready(set()) == [
        "add_within_10",
        "sub_within_10",
        "place_value_tens_ones",
        "equivalent_fractions",
    ]
    order = graph.topo_order()
    for skill_id in graph.skills:
        for prereq in graph.prerequisites(skill_id):
            assert order.index(prereq) < order.index(skill_id)
    anchors = {s.id for s in graph.skills.values() if s.anchor}
    assert anchors == {
        "add_within_10",
        "add_within_20",
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
    assert {k for sid, k in keypads.items() if sid != "add_fractions_unlike"} == {"numpad"}
