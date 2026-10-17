"""The build plan: loading, each lint rule against its own failing fixture, the report."""

import json
import shutil
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

from mathquest.cli import content_lint, content_report
from mathquest.engine.content import ContentError, load_pack
from mathquest.engine.content.lint import Finding
from mathquest.engine.content.planned import (
    MAX_BATCH,
    MAX_LABEL,
    MAX_NAME,
    lint_planned,
    load_planned,
    plan_summary,
)
from mathquest.engine.generators import all_generators
from tests.engine.content.packbuilder import CONTENT, base, write

Plan = dict[str, Any]
REGISTRY = all_generators()


def _skill(sid: str, **over: Any) -> dict[str, Any]:
    entry: dict[str, Any] = {
        "id": sid,
        "name": sid.replace("_", " ").title(),
        "region": "meadow",
        "prerequisites": [],
        "fluency": False,
        "anchor": False,
        "tiers": [{"id": i, "label": f"Step {i}"} for i in range(3)],
        "grade_band": "1",
        "keypad": "numpad",
        "standards": ["1.OA.A.1"],
        "batch": 1,
    }
    entry.update(over)
    return entry


def _plan() -> Plan:
    """A plan that lints clean beside the base pack (built skill ``alpha``)."""
    return {
        "scope": {"regions": ["meadow"], "grade_bands": ["1"]},
        "planned": [_skill("beta", prerequisites=["alpha"], anchor=True)],
    }


def _files(plan: Plan) -> dict[str, Any]:
    files = base()
    files["planned_skills.yaml"] = plan
    return files


def _pack(tmp_path: Path, plan: Plan, files: dict[str, Any] | None = None) -> Path:
    files = _files(plan) if files is None else {**files, "planned_skills.yaml": plan}
    return write(tmp_path, files)


def _check(tmp_path: Path, plan: Plan, files: dict[str, Any] | None = None) -> list[Finding]:
    root = _pack(tmp_path, plan, files)
    loaded = load_planned(root)
    assert loaded is not None
    return lint_planned(load_pack(root), loaded)


def _rule(findings: list[Finding], rule: str) -> list[Finding]:
    return [f for f in findings if f.rule == rule]


def _edit(change: Callable[[Plan], None]) -> Plan:
    plan = _plan()
    change(plan)
    return plan


def _one_error(tmp_path: Path, plan: Plan, rule: str, fragment: str, path: str = "") -> None:
    found = _rule(_check(tmp_path, plan), rule)
    assert [f for f in found if fragment in f.message], found
    assert all(f.level == "error" for f in found)
    if path:
        assert any(f.path == path for f in found), found


def test_clean_plan_has_no_findings(tmp_path: Path) -> None:
    assert _check(tmp_path, _plan()) == []


def test_real_plan_has_no_findings() -> None:
    pack = load_pack(CONTENT / "packs" / "k8-core")
    plan = load_planned(CONTENT / "packs" / "k8-core")
    assert plan is not None
    assert lint_planned(pack, plan) == []
    assert not {s.id for s in plan.planned} & set(pack.skills)


def test_a_pack_without_a_plan_has_none(tmp_path: Path) -> None:
    assert load_planned(write(tmp_path, base())) is None


def test_the_plan_is_never_loaded_with_the_pack(tmp_path: Path) -> None:
    pack = load_pack(_pack(tmp_path, _plan()))
    assert set(pack.skills) == {"alpha"}


def test_a_broken_plan_does_not_stop_the_pack_loading(tmp_path: Path) -> None:
    root = write(tmp_path, {**base(), "planned_skills.yaml": {"nonsense": True}})
    assert set(load_pack(root).skills) == {"alpha"}
    with pytest.raises(ContentError, match=r"planned_skills.yaml"):
        load_planned(root)


# --- loading: shape, standards, keypad -------------------------------------------


def _load_error(tmp_path: Path, plan: Plan) -> str:
    with pytest.raises(ContentError) as caught:
        load_planned(_pack(tmp_path, plan))
    return str(caught.value)


@pytest.mark.parametrize(
    "code", ["K.CC.1", "6.XX.A.1", "9.OA.A.1", "2.NBT.B", "2.nbt.b.5", "2.NBT.B.5 ", "CC.A.1"]
)
def test_a_malformed_standard_does_not_load(tmp_path: Path, code: str) -> None:
    plan = _edit(lambda p: p["planned"][0].update(standards=[code]))
    assert "standards[0]" in _load_error(tmp_path, plan)


@pytest.mark.parametrize("code", ["K.CC.A.1", "2.NBT.B.5", "3.OA.C.7", "K.CC.B.4a", "3.MD.A.1"])
def test_well_formed_standards_load(tmp_path: Path, code: str) -> None:
    plan = _edit(lambda p: p["planned"][0].update(standards=[code], grade_band="3"))
    plan["scope"]["grade_bands"] = ["3"]
    assert _check(tmp_path, plan) == []


def test_a_skill_needs_at_least_one_standard(tmp_path: Path) -> None:
    plan = _edit(lambda p: p["planned"][0].update(standards=[]))
    assert "planned[0].standards" in _load_error(tmp_path, plan)


def test_a_planned_skill_takes_no_generator(tmp_path: Path) -> None:
    plan = _edit(lambda p: p["planned"][0].update(generator="add_within_20"))
    assert "planned[0].generator" in _load_error(tmp_path, plan)


def test_an_unknown_keypad_does_not_load(tmp_path: Path) -> None:
    plan = _edit(lambda p: p["planned"][0].update(keypad="piano"))
    assert "planned[0].keypad" in _load_error(tmp_path, plan)


def test_a_choice_keypad_needs_a_bank(tmp_path: Path) -> None:
    plan = _edit(lambda p: p["planned"][0].update(keypad="choice"))
    assert "banked" in _load_error(tmp_path, plan)
    plan["planned"][0]["banked"] = True
    assert _check(tmp_path, plan) == []


def test_tier_ids_run_from_zero(tmp_path: Path) -> None:
    plan = _edit(lambda p: p["planned"][0]["tiers"][1].update(id=5))
    assert "tier ids" in _load_error(tmp_path, plan)


def test_a_batch_starts_at_one(tmp_path: Path) -> None:
    plan = _edit(lambda p: p["planned"][0].update(batch=0))
    assert "planned[0].batch" in _load_error(tmp_path, plan)


# --- ids --------------------------------------------------------------------------


def test_a_built_skill_must_leave_the_plan(tmp_path: Path) -> None:
    plan = _edit(lambda p: p["planned"].append(_skill("alpha")))
    _one_error(tmp_path, plan, "planned-ids", "already built", "planned[1].id")


def test_planned_ids_are_unique(tmp_path: Path) -> None:
    plan = _edit(lambda p: p["planned"].append(_skill("beta", name="Other Beta")))
    _one_error(tmp_path, plan, "planned-ids", "duplicate", "planned[1].id")


def test_a_repeated_name_is_a_warning(tmp_path: Path) -> None:
    plan = _edit(lambda p: p["planned"].append(_skill("gamma", name="Beta")))
    (found,) = _rule(_check(tmp_path, plan), "planned-ids")
    assert found.level == "warning"
    assert "same name as beta" in found.message


# --- scope ------------------------------------------------------------------------


def _with_second_region(files: dict[str, Any]) -> dict[str, Any]:
    files["world.yaml"]["regions"].append(
        {
            "id": "canyon",
            "name": "Canyon",
            "order": 2,
            "creature_family": "family_b",
            "map_hint": "Rock.",
        }
    )
    return files


def test_an_unknown_region_is_an_error(tmp_path: Path) -> None:
    plan = _edit(lambda p: p["planned"][0].update(region="nowhere"))
    _one_error(tmp_path, plan, "planned-scope", "unknown region nowhere", "planned[0].region")


def test_the_scope_names_real_regions(tmp_path: Path) -> None:
    plan = _edit(lambda p: p["scope"]["regions"].append("nowhere"))
    _one_error(tmp_path, plan, "planned-scope", "unknown region", "scope.regions[1]")


def test_a_region_outside_the_scope_is_an_error(tmp_path: Path) -> None:
    plan = _edit(lambda p: p["planned"][0].update(region="canyon"))
    files = _with_second_region(base())
    found = _rule(_check(tmp_path, plan, files), "planned-scope")
    assert [f.message for f in found] == ["region canyon is outside the plan"]


def test_a_grade_band_outside_the_scope_is_an_error(tmp_path: Path) -> None:
    plan = _edit(lambda p: p["planned"][0].update(grade_band="4", standards=["4.NBT.A.1"]))
    _one_error(tmp_path, plan, "planned-scope", "grade band 4", "planned[0].grade_band")


# --- the graph --------------------------------------------------------------------


def test_an_unknown_prerequisite_is_an_error(tmp_path: Path) -> None:
    plan = _edit(lambda p: p["planned"][0].update(prerequisites=["alpha", "ghost"]))
    _one_error(
        tmp_path, plan, "planned-graph", "unknown skill ghost", "planned[0].prerequisites[1]"
    )


def test_an_unknown_unlock_target_is_an_error(tmp_path: Path) -> None:
    plan = _edit(lambda p: p["planned"][0].update(unlocks=["ghost"]))
    _one_error(tmp_path, plan, "planned-graph", "unknown skill ghost", "planned[0].unlocks[0]")


def test_a_skill_cannot_unlock_itself(tmp_path: Path) -> None:
    plan = _edit(lambda p: p["planned"][0].update(unlocks=["beta"]))
    _one_error(tmp_path, plan, "planned-graph", "cannot unlock itself")


def test_a_prerequisite_cycle_is_an_error(tmp_path: Path) -> None:
    plan = _edit(
        lambda p: p["planned"].extend(
            [_skill("gamma", prerequisites=["delta"]), _skill("delta", prerequisites=["gamma"])]
        )
    )
    _one_error(tmp_path, plan, "planned-graph", "prerequisite cycle: gamma -> delta -> gamma")


def test_a_cycle_through_an_unlock_is_an_error(tmp_path: Path) -> None:
    plan = _edit(lambda p: p["planned"][0].update(unlocks=["alpha"]))
    _one_error(tmp_path, plan, "planned-graph", "prerequisite cycle")


def test_an_unlock_gives_a_built_skill_a_prerequisite(tmp_path: Path) -> None:
    plan = _edit(
        lambda p: p["planned"].append(_skill("root", unlocks=["alpha"], standards=["K.CC.A.1"]))
    )
    plan["planned"][1]["grade_band"] = "1"
    assert _rule(_check(tmp_path, plan), "planned-graph") == []


def test_a_cycle_is_reported_once(tmp_path: Path) -> None:
    plan = _edit(
        lambda p: p["planned"].extend(
            [_skill("gamma", prerequisites=["delta"]), _skill("delta", prerequisites=["gamma"])]
        )
    )
    found = _rule(_check(tmp_path, plan), "planned-graph")
    assert len(found) == 1


def test_a_skill_without_prerequisites_belongs_in_batch_one(tmp_path: Path) -> None:
    plan = _edit(lambda p: p["planned"].append(_skill("gamma", batch=2)))
    _one_error(tmp_path, plan, "planned-graph", "belongs in batch 1", "planned[1].prerequisites")


def test_a_prerequisite_in_a_later_region_is_an_error(tmp_path: Path) -> None:
    plan = _edit(lambda p: p["scope"]["regions"].append("canyon"))
    plan["planned"].append(_skill("gamma", region="canyon"))
    plan["planned"][0]["prerequisites"].append("gamma")
    found = _rule(_check(tmp_path, plan, _with_second_region(base())), "planned-graph")
    assert [f.message for f in found] == ["gamma is in canyon, later on the map than beta"]


def test_an_unlock_in_an_earlier_region_is_an_error(tmp_path: Path) -> None:
    plan = _edit(lambda p: p["scope"]["regions"].append("canyon"))
    plan["planned"][0].update(region="canyon")
    plan["planned"][0]["unlocks"] = ["alpha"]
    plan["planned"][0]["prerequisites"] = []
    found = _rule(_check(tmp_path, plan, _with_second_region(base())), "planned-graph")
    assert any("later on the map" in f.message for f in found), found


def test_a_prerequisite_from_a_later_grade_is_an_error(tmp_path: Path) -> None:
    plan = _edit(lambda p: p["scope"].update(grade_bands=["1", "2"]))
    plan["planned"].append(_skill("gamma", grade_band="2", standards=["2.OA.A.1"], anchor=True))
    plan["planned"][0]["prerequisites"].append("gamma")
    found = _rule(_check(tmp_path, plan), "planned-graph")
    assert [f.message for f in found] == ["gamma is for grade 2, later than beta (grade 1)"]


# --- batches ----------------------------------------------------------------------


def test_a_plan_may_start_after_the_built_batches(tmp_path: Path) -> None:
    plan = _edit(lambda p: p["planned"][0].update(batch=2))
    plan["planned"].append(_skill("gamma", prerequisites=["beta"], batch=3))
    assert _check(tmp_path, plan) == []


def test_a_root_must_be_in_the_first_remaining_batch(tmp_path: Path) -> None:
    plan = _edit(lambda p: p["planned"][0].update(batch=2))
    plan["planned"].append(_skill("gamma", batch=3))
    _one_error(tmp_path, plan, "planned-graph", "belongs in batch 2", "planned[1].prerequisites")


def test_a_gap_after_the_first_remaining_batch_is_an_error(tmp_path: Path) -> None:
    plan = _edit(lambda p: p["planned"][0].update(batch=2))
    plan["planned"].append(_skill("gamma", prerequisites=["beta"], batch=4))
    _one_error(tmp_path, plan, "planned-batch", "2 to 4 with none missing")


def test_batches_have_no_gaps(tmp_path: Path) -> None:
    plan = _edit(lambda p: p["planned"].append(_skill("gamma", prerequisites=["beta"], batch=3)))
    _one_error(tmp_path, plan, "planned-batch", "1 to 3 with none missing")


def test_a_later_batch_prerequisite_is_an_error(tmp_path: Path) -> None:
    plan = _edit(lambda p: p["planned"].append(_skill("gamma", prerequisites=["beta"], batch=2)))
    plan["planned"][0]["prerequisites"] = ["alpha", "gamma"]
    found = _rule(_check(tmp_path, plan), "planned-batch")
    assert [f.message for f in found] == ["gamma is in batch 2, after batch 1 of beta"]


def test_an_unlock_target_must_not_be_built_earlier(tmp_path: Path) -> None:
    plan = _edit(lambda p: p["planned"].append(_skill("gamma", prerequisites=["alpha"], batch=1)))
    plan["planned"].append(_skill("delta", prerequisites=["gamma"], batch=2, unlocks=["gamma"]))
    found = _rule(_check(tmp_path, plan), "planned-batch")
    assert [f.message for f in found] == ["gamma is in batch 1, before batch 2 of delta"]


@pytest.mark.parametrize(("extra", "warned"), [(MAX_BATCH - 1, False), (MAX_BATCH, True)])
def test_a_batch_over_the_limit_is_a_warning(tmp_path: Path, extra: int, warned: bool) -> None:
    plan = _edit(
        lambda p: p["planned"].extend(
            _skill(f"extra_{i}", prerequisites=["alpha"], name=f"Extra {i}") for i in range(extra)
        )
    )
    found = _rule(_check(tmp_path, plan), "planned-batch")
    assert [(f.level, f"batch 1 has {MAX_BATCH + 1} skills" in f.message) for f in found] == (
        [("warning", True)] if warned else []
    )


# --- anchors ----------------------------------------------------------------------


def test_an_anchor_must_not_build_on_a_later_grade_anchor(tmp_path: Path) -> None:
    plan = _edit(lambda p: p["scope"].update(grade_bands=["K", "1"]))
    plan["planned"].append(
        _skill(
            "early", grade_band="K", standards=["K.CC.A.1"], anchor=True, prerequisites=["alpha"]
        )
    )
    files = base()
    files["skills.yaml"]["skills"][0]["anchor"] = True
    found = _rule(_check(tmp_path, plan, files), "planned-anchors")
    assert [f.message for f in found] == ["anchor early (grade K) builds on anchor alpha (grade 1)"]


@pytest.mark.parametrize("early_first", [True, False])
def test_unrelated_anchors_may_be_declared_in_either_order(
    tmp_path: Path, early_first: bool
) -> None:
    plan = _edit(lambda p: p["scope"].update(grade_bands=["K", "1"]))
    early = _skill("early", grade_band="K", standards=["K.CC.A.1"], anchor=True)
    late = _skill("late", grade_band="1", anchor=True)
    plan["planned"] = [early, late] if early_first else [late, early]
    assert _rule(_check(tmp_path, plan), "planned-anchors") == []


def test_anchors_are_not_checked_when_there_is_a_cycle(tmp_path: Path) -> None:
    plan = _edit(lambda p: p["scope"].update(grade_bands=["1", "2"]))
    plan["planned"] += [
        _skill("gamma", prerequisites=["delta"], anchor=True),
        _skill("delta", prerequisites=["gamma"], anchor=True),
    ]
    found = _check(tmp_path, plan)
    assert _rule(found, "planned-anchors") == []
    assert _rule(found, "planned-graph")


def test_every_grade_of_the_scope_needs_an_anchor(tmp_path: Path) -> None:
    plan = _edit(lambda p: p["scope"].update(grade_bands=["1", "2"]))
    _one_error(tmp_path, plan, "planned-anchors", "no anchor for grade 2", "scope.grade_bands")


def test_anchors_outside_the_scope_are_not_part_of_the_spine(tmp_path: Path) -> None:
    files = _with_second_region(base())
    files["skills.yaml"]["skills"].append(
        {**files["skills.yaml"]["skills"][0], "id": "late", "region": "canyon", "anchor": True}
    )
    files["skills.yaml"]["skills"][-1]["grade_band"] = "5"
    assert _rule(_check(tmp_path, _plan(), files), "planned-anchors") == []


# --- tiers, standards and text -----------------------------------------------------


def test_a_skill_needs_three_tiers(tmp_path: Path) -> None:
    plan = _edit(lambda p: p["planned"][0].update(tiers=p["planned"][0]["tiers"][:2]))
    _one_error(tmp_path, plan, "planned-tiers", "has 2 tiers", "planned[0].tiers")


def test_a_standard_from_a_later_grade_is_an_error(tmp_path: Path) -> None:
    plan = _edit(lambda p: p["planned"][0].update(standards=["1.OA.A.1", "2.OA.A.1"]))
    _one_error(tmp_path, plan, "planned-standards", "later grade", "planned[0].standards[1]")


def test_a_kindergarten_standard_suits_any_grade(tmp_path: Path) -> None:
    plan = _edit(lambda p: p["planned"][0].update(standards=["K.CC.A.1"]))
    assert _check(tmp_path, plan) == []


def test_a_standard_listed_twice_is_an_error(tmp_path: Path) -> None:
    plan = _edit(lambda p: p["planned"][0].update(standards=["1.OA.A.1", "1.OA.A.1"]))
    _one_error(tmp_path, plan, "planned-standards", "listed twice", "planned[0].standards[1]")


@pytest.mark.parametrize(
    "bad",
    [
        "Add " + chr(0x2014) + " carry",
        "Add " + chr(0x2013) + " carry",
        "Add -- carry",
        "Add - carry",
    ],
)
def test_a_dash_in_a_name_is_an_error(tmp_path: Path, bad: str) -> None:
    plan = _edit(lambda p: p["planned"][0].update(name=bad))
    _one_error(tmp_path, plan, "planned-text", "no dash", "planned[0].name")


def test_a_dash_in_a_tier_label_is_an_error(tmp_path: Path) -> None:
    plan = _edit(
        lambda p: p["planned"][0]["tiers"][2].update(label="Big " + chr(0x2014) + " small")
    )
    _one_error(tmp_path, plan, "planned-text", "no dash", "planned[0].tiers[2].label")


def test_a_hyphen_inside_a_word_is_fine(tmp_path: Path) -> None:
    plan = _edit(lambda p: p["planned"][0].update(name="Two-Step Stories"))
    assert _check(tmp_path, plan) == []


@pytest.mark.parametrize(("length", "flagged"), [(MAX_NAME, False), (MAX_NAME + 1, True)])
def test_name_length_limit(tmp_path: Path, length: int, flagged: bool) -> None:
    plan = _edit(lambda p: p["planned"][0].update(name="A" * length))
    found = _rule(_check(tmp_path, plan), "planned-text")
    assert [f.path for f in found] == (["planned[0].name"] if flagged else [])


@pytest.mark.parametrize(("length", "flagged"), [(MAX_LABEL, False), (MAX_LABEL + 1, True)])
def test_tier_label_length_limit(tmp_path: Path, length: int, flagged: bool) -> None:
    plan = _edit(lambda p: p["planned"][0]["tiers"][0].update(label="B" * length))
    found = _rule(_check(tmp_path, plan), "planned-text")
    assert [f.path for f in found] == (["planned[0].tiers[0].label"] if flagged else [])


# --- the report --------------------------------------------------------------------


def test_the_summary_counts_built_and_planned_per_region_and_batch(tmp_path: Path) -> None:
    plan = _edit(lambda p: p["planned"].append(_skill("gamma", prerequisites=["beta"], batch=2)))
    root = _pack(tmp_path, plan)
    loaded = load_planned(root)
    assert loaded is not None
    summary = plan_summary(load_pack(root), loaded)
    assert [(r.region_id, r.built, r.planned) for r in summary.regions] == [("meadow", 1, 2)]
    assert [(b.batch, b.skills, b.regions) for b in summary.batches] == [
        (1, 1, {"meadow": 1}),
        (2, 1, {"meadow": 1}),
    ]
    assert summary.planned == 2


def _two_batch_plan() -> Plan:
    plan = _plan()
    plan["planned"].append(_skill("gamma", prerequisites=["beta"], batch=2))
    return plan


def test_the_report_shows_planned_skills(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert content_report.main([str(_pack(tmp_path, _two_batch_plan()))]) == 0
    out = capsys.readouterr().out
    assert "## Planned skills" in out
    assert "| Meadow | 1 | 2 | 3 |" in out
    assert "| 1 | 1 | 1 | meadow 1 |" in out
    assert "| 2 | 1 | 1 | meadow 1 |" in out


def test_the_json_report_carries_the_plan(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert content_report.main([str(_pack(tmp_path, _two_batch_plan())), "--json"]) == 0
    (pack,) = json.loads(capsys.readouterr().out)["packs"]
    assert [b["skills"] for b in pack["planned"]["batches"]] == [1, 1]
    assert [(r["region_id"], r["built"], r["planned"]) for r in pack["planned"]["regions"]] == [
        ("meadow", 1, 2)
    ]


def test_the_real_report_has_a_planned_section(capsys: pytest.CaptureFixture[str]) -> None:
    assert content_report.main([str(CONTENT / "packs" / "k8-core")]) == 0
    assert "## Planned skills" in capsys.readouterr().out


def test_a_report_for_a_pack_without_a_plan_has_no_planned_section(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    root = write(tmp_path, base())
    assert content_report.main([str(root)]) == 0
    assert "Planned skills" not in capsys.readouterr().out
    assert content_report.main([str(root), "--json"]) == 0
    (pack,) = json.loads(capsys.readouterr().out)["packs"]
    assert "planned" not in pack


def test_a_report_fails_on_a_plan_that_does_not_load(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    root = write(tmp_path, {**base(), "planned_skills.yaml": {"nonsense": True}})
    assert content_report.main([str(root)]) == 2
    assert "planned_skills.yaml" in capsys.readouterr().err


# --- the command -------------------------------------------------------------------


def _content_dir(tmp_path: Path) -> Path:
    root = tmp_path / "content"
    (root / "lint").mkdir(parents=True)
    shutil.copy(CONTENT / "slots.yaml", root / "slots.yaml")
    shutil.copy(CONTENT / "lint" / "k2_words.txt", root / "lint" / "k2_words.txt")
    return root


def test_content_lint_fails_on_a_plan_error(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    plan = _edit(lambda p: p["planned"][0].update(prerequisites=["ghost"]))
    root = write(_content_dir(tmp_path) / "packs", {**base(), "planned_skills.yaml": plan})
    assert content_lint.main([str(root)]) == 1
    out = capsys.readouterr().out
    assert f"error: {root}/planned_skills.yaml:planned[0].prerequisites[0]: planned-graph: " in out


def test_content_lint_fails_on_a_plan_that_does_not_load(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    plan = _edit(lambda p: p["planned"][0].update(standards=["nope"]))
    root = write(_content_dir(tmp_path) / "packs", {**base(), "planned_skills.yaml": plan})
    assert content_lint.main([str(root)]) == 1
    assert "planned_skills.yaml: planned[0].standards[0]" in capsys.readouterr().out


def test_content_lint_passes_a_clean_plan(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    root = write(_content_dir(tmp_path) / "packs", {**base(), "planned_skills.yaml": _plan()})
    assert content_lint.main([str(root)]) == 0
    assert "0 errors, 0 warnings" in capsys.readouterr().out
