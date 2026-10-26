"""Where the batch four skills sit in the skill graph of the real pack."""

from pathlib import Path

import pytest

from mathquest.engine.catalog import load_catalog

CONTENT = Path(__file__).resolve().parents[2] / "content"
GRAPH = load_catalog(CONTENT, "k8-core").graph
TABLES = ("mult_2_5", "mult_3_4", "mult_6_7", "mult_8_9")


@pytest.mark.parametrize("skill_id", ["add_3digit_regroup", "sub_3digit_regroup"])
def test_three_digit_regrouping_sits_above_its_two_digit_anchor(skill_id: str) -> None:
    anchor = "add_2digit_regroup" if skill_id.startswith("add") else "sub_2digit_regroup"
    assert anchor in GRAPH.ancestors(skill_id)


@pytest.mark.parametrize("skill_id", TABLES)
def test_every_table_sits_above_times_ten(skill_id: str) -> None:
    """The tables ask times 10 and their hints use ten times."""
    assert "mult_0_1_10" in GRAPH.ancestors(skill_id)


@pytest.mark.parametrize("anchor", ["add_2digit_regroup", "sub_2digit_regroup"])
def test_the_two_digit_anchors_leave_the_three_digit_skills_unmarked(anchor: str) -> None:
    """Placing a child at either anchor marks only what is under it (ADR-0028)."""
    three_digit = {
        "add_3digit_no_regroup",
        "sub_3digit_no_regroup",
        "add_3digit_regroup",
        "sub_3digit_regroup",
    }
    assert not three_digit & GRAPH.ancestors(anchor)
