from pathlib import Path

import pytest

from mathquest.engine.skillgraph import ContentError, load_pack

PACK = Path(__file__).resolve().parents[2] / "content" / "packs" / "k8-core"


def _write_pack(tmp_path: Path, body: str) -> Path:
    (tmp_path / "skills.yaml").write_text(body, encoding="utf-8")
    return tmp_path


def test_load_slice_pack() -> None:
    graph = load_pack(PACK)
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
    assert anchors == {"add_within_20", "add_2digit_regroup", "add_fractions_unlike"}


def test_cycle_rejected(tmp_path: Path) -> None:
    body = """
skills:
  - {id: a, name: A, region: r, prerequisites: [b], fluency: false, anchor: false}
  - {id: b, name: B, region: r, prerequisites: [a], fluency: false, anchor: false}
"""
    with pytest.raises(ContentError) as exc:
        load_pack(_write_pack(tmp_path, body))
    assert "a" in str(exc.value)
    assert "b" in str(exc.value)


def test_missing_prereq_rejected(tmp_path: Path) -> None:
    body = """
skills:
  - {id: a, name: A, region: r, prerequisites: [ghost], fluency: false, anchor: false}
"""
    with pytest.raises(ContentError, match="ghost"):
        load_pack(_write_pack(tmp_path, body))


def test_ready_after_mastery() -> None:
    graph = load_pack(PACK)
    assert "add_within_20" in graph.ready({"add_within_10"})
    assert "add_within_10" not in graph.ready({"add_within_10"})
