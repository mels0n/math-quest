# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false
"""Every answer a keypad profile can type is one the checker's parser reads.

The samples in ``testdata/keypad-samples.json`` (repo root) are the LaTeX the answer
field holds after tapping each key sequence; the frontend unit and browser tests check
the same file from the keypad side.
"""

import json
from fractions import Fraction
from pathlib import Path
from typing import Any

import pytest
import sympy

from mathquest.engine.checker.latex import parse
from mathquest.engine.checker.sympy_bridge import to_sympy
from mathquest.engine.types import KEYPAD_PROFILES

FIXTURE = Path(__file__).resolve().parents[3] / "testdata" / "keypad-samples.json"
PROFILES: dict[str, list[dict[str, Any]]] = json.loads(FIXTURE.read_text(encoding="utf-8"))[
    "profiles"
]
SAMPLES = [(profile, s) for profile, samples in PROFILES.items() for s in samples]


def test_fixture_covers_every_profile() -> None:
    assert set(PROFILES) == set(KEYPAD_PROFILES)
    for profile in KEYPAD_PROFILES:
        assert PROFILES[profile] or profile == "choice", profile


@pytest.mark.parametrize(
    ("profile", "sample"), SAMPLES, ids=[f"{p}:{s['latex']}" for p, s in SAMPLES]
)
def test_sample_parses_to_expected_value(profile: str, sample: dict[str, Any]) -> None:
    del profile
    parsed = to_sympy(parse(sample["latex"]))
    value: Any = parsed.lhs - parsed.rhs if isinstance(parsed, sympy.Equality) else parsed  # pyright: ignore[reportOperatorIssue]
    at = [(sympy.Symbol(name), sympy.Integer(v)) for name, v in sample.get("at", {}).items()]
    got = sympy.simplify(value.subs(at))
    expected = Fraction(sample["value"])
    assert got == sympy.Rational(expected.numerator, expected.denominator)
