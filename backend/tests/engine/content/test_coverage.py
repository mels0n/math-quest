"""Coverage numbers and the content-report command."""

import json
from pathlib import Path

import pytest

from mathquest.cli import content_report
from mathquest.engine.content.coverage import Gap, pack_coverage
from mathquest.engine.generators import all_generators
from tests.engine.content.packbuilder import CONTENT, base, load, write


def test_coverage_counts_and_gaps(tmp_path: Path) -> None:
    coverage = pack_coverage(load(tmp_path, base()), all_generators())
    assert (coverage.pack_id, coverage.version) == ("lint-pack", "1.0.0")
    (region,) = coverage.regions
    assert (region.region_id, region.complete) == ("meadow", False)
    (skill,) = region.skills
    assert (skill.tiers, skill.misconceptions, skill.feedback) == (3, 2, 2)
    assert (skill.word_templates, skill.bank_items) == (3, 2)
    assert (skill.lesson, skill.hints, skill.explanations) == (True, 3, 3)
    assert skill.gaps == (
        Gap("word templates", 3, 15),
        Gap("bank items", 2, 30),
    )


def test_coverage_leaves_out_word_and_bank_targets_when_flags_are_off(tmp_path: Path) -> None:
    files = base()
    files["skills.yaml"]["skills"][0].update(word_problems_fit=False, banked=False)
    del files["word_problems/alpha.yaml"], files["bank/alpha.yaml"]
    (skill,) = pack_coverage(load(tmp_path, files), all_generators()).skills()
    assert (skill.word_templates, skill.bank_items) == (None, None)
    assert skill.gaps == ()


def test_a_mistake_without_feedback_is_a_gap(tmp_path: Path) -> None:
    files = base()
    del files["explanations/alpha.yaml"]["misconceptions"]["counted_start"]
    (skill,) = pack_coverage(load(tmp_path, files), all_generators()).skills()
    assert skill.feedback == 1
    assert Gap("misconception feedback", 1, 2) in skill.gaps


def test_missing_teaching_is_a_gap(tmp_path: Path) -> None:
    files = base()
    del files["lessons/alpha.yaml"], files["hints/alpha.yaml"]
    (skill,) = pack_coverage(load(tmp_path, files), all_generators()).skills()
    assert {"lesson", "hints"} <= {g.field for g in skill.gaps}


def test_report_markdown_for_the_real_pack(capsys: pytest.CaptureFixture[str]) -> None:
    assert content_report.main([str(CONTENT / "packs" / "k8-core")]) == 0
    out = capsys.readouterr().out
    assert "## Number Meadows (in progress)" in out
    row = "| 3 / 3+ | 2 / 2+ | 2 / 2 | 15 / 15+ | n/a | yes | 3 / 3 | 4 / 3-4 | done |"
    assert f"| `add_within_20` {row}" in out
    assert "## Totals" in out
    assert "Stuck" not in out


def test_report_json_with_stuck_counts(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    pack = write(tmp_path, base())
    stuck = tmp_path / "stuck.json"
    entry = {"skill": "alpha", "generator": "add_within_20", "tier": 1, "seed": 7}
    stuck.write_text(json.dumps([{**entry, "wrong_answers": ["3", "4"]}] * 2), encoding="utf-8")
    assert content_report.main([str(pack), "--json", "--stuck", str(stuck)]) == 0
    data = json.loads(capsys.readouterr().out)
    (skill,) = data["packs"][0]["regions"][0]["skills"]
    assert skill["stuck"] == 2
    assert skill["word_templates"] == 3


def test_report_markdown_with_stuck_column(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    pack = write(tmp_path, base())
    stuck = tmp_path / "stuck.json"
    stuck.write_text("[]", encoding="utf-8")
    assert content_report.main([str(pack), "--stuck", str(stuck)]) == 0
    out = capsys.readouterr().out
    assert "| Stuck |" in out
    assert "- Stuck problems: 0" in out


def test_report_rejects_a_malformed_stuck_file(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    stuck = tmp_path / "stuck.json"
    stuck.write_text('[{"skill": "alpha"}]', encoding="utf-8")
    assert content_report.main([str(write(tmp_path, base())), "--stuck", str(stuck)]) == 2
    assert "cannot read" in capsys.readouterr().err
