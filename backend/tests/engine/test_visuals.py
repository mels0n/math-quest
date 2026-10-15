"""Visual params: one schema per kind, range checks before and after templates fill in."""

from typing import Any

import pytest
from pydantic import TypeAdapter, ValidationError

from mathquest.engine.content.visuals import VISUAL_KINDS, NumberLine, Visual
from mathquest.engine.teaching import render_visual
from mathquest.engine.templates import TemplateError

VISUAL: TypeAdapter[Any] = TypeAdapter(Visual)

GOOD: dict[str, dict[str, Any]] = {
    "number_line": {"min": 0, "max": 20, "start": 8, "jumps": [2, 3], "end": 13},
    "base_ten": {"tens": 2, "ones": 7},
    "fraction_bars": {"bars": [{"parts": 4, "shaded": 3}, {"parts": 8, "shaded": 6}]},
    "area_model": {"rows": [20, 3], "cols": [10, 4]},
    "algebra_tiles": {"x2": 1, "x": -3, "units": 2},
    "array": {"rows": 3, "cols": 4},
    "clock": {"hour": 3, "minute": 45},
    "money": {"quarters": 2, "dimes": 1, "pennies": 3},
}

BAD: list[tuple[str, dict[str, Any], str]] = [
    ("number_line", {"min": 5, "max": 5}, "max must be above min"),
    ("number_line", {"min": 0, "max": 10, "start": 11}, "start must be from 0 to 10"),
    ("number_line", {"min": 0, "max": 10, "start": 8, "jumps": [1, 1, 1]}, "landing point"),
    ("number_line", {"min": 0, "max": 10, "jumps": 3}, "jumps need a start"),
    ("number_line", {"min": 0, "max": 10, "start": 2, "jumps": [0]}, "a jump of 0"),
    ("base_ten", {}, "at least one block"),
    ("base_ten", {"ones": -1}, "ones must be from 0"),
    ("fraction_bars", {"bars": [{"parts": 3, "shaded": 4}]}, "shaded must be from 0 to 3"),
    ("fraction_bars", {"bars": []}, "at least 1 item"),
    ("area_model", {"rows": [1, 2, 3, 4], "cols": [1]}, "at most 3 items"),
    ("algebra_tiles", {}, "at least one tile"),
    ("array", {"rows": 0, "cols": 3}, "rows must be from 1"),
    ("clock", {"hour": 13}, "hour must be from 1 to 12"),
    ("clock", {"hour": 3, "minute": 60}, "minute must be from 0 to 59"),
    ("money", {}, "at least one coin"),
    ("money", {"dimes": True}, "whole number or a template"),
    ("array", {"rows": 2, "cols": 2, "colour": "gold"}, "Extra inputs"),
]


def test_every_kind_has_an_example() -> None:
    assert set(GOOD) == set(VISUAL_KINDS)


@pytest.mark.parametrize("kind", sorted(GOOD))
def test_each_kind_accepts_its_params(kind: str) -> None:
    visual = VISUAL.validate_python({"kind": kind, "params": GOOD[kind]})
    assert visual.kind == kind
    assert render_visual(visual, {}) == visual


@pytest.mark.parametrize(("kind", "params", "message"), BAD)
def test_bad_params_are_rejected(kind: str, params: dict[str, Any], message: str) -> None:
    with pytest.raises(ValidationError) as exc:
        VISUAL.validate_python({"kind": kind, "params": params})
    assert message in str(exc.value)


def test_unknown_kind_is_rejected() -> None:
    with pytest.raises(ValidationError):
        VISUAL.validate_python({"kind": "pie_chart", "params": {}})


def test_templates_fill_in_and_are_checked_again() -> None:
    visual = VISUAL.validate_python(
        {
            "kind": "number_line",
            "params": {"min": 0, "max": 10, "start": "{a}", "jumps": "{{= 0 - b }}"},
        }
    )
    shown = render_visual(visual, {"a": 7, "b": 3})
    assert isinstance(shown, NumberLine)
    assert shown.params.start == 7
    assert shown.params.steps() == (-1, -1, -1)
    with pytest.raises(TemplateError, match="landing point"):
        render_visual(visual, {"a": 2, "b": 3})


def test_a_template_that_is_not_a_number_fails_when_rendered() -> None:
    visual = VISUAL.validate_python({"kind": "clock", "params": {"hour": "{name}"}})
    with pytest.raises(TemplateError, match="whole number"):
        render_visual(visual, {"name": "Ada"})
