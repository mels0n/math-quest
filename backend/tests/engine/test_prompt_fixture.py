"""The longest prompt of every generator, shared with the end-to-end prompt-fit check.

``testdata/longest-prompts.json`` (repo root) holds, per skill, the prompt with the most
characters over the first SEEDS seeds of every tier. The browser test lays each one out
at phone and desktop widths. Regenerate it with ``UPDATE_FIXTURES=1 uv run pytest
tests/engine/test_prompt_fixture.py`` after changing a generator.
"""

import json
import os
from pathlib import Path

from mathquest.engine.generators import all_generators
from mathquest.engine.types import Problem, TextPart

FIXTURE = Path(__file__).resolve().parents[3] / "testdata" / "longest-prompts.json"
SEEDS = 200


def _parts(problem: Problem) -> list[dict[str, str]]:
    return [
        {"kind": "text", "value": p.text}
        if isinstance(p, TextPart)
        else {"kind": "math", "value": p.latex}
        for p in problem.prompt
    ]


def _size(problem: Problem) -> int:
    return sum(len(p["value"]) for p in _parts(problem))


def longest_prompts() -> dict[str, object]:
    out: dict[str, object] = {}
    for skill_id, gen in sorted(all_generators().items()):
        best = max(
            (
                gen.generate(seed, tier)
                for tier in range(len(gen.tier_difficulties))
                for seed in range(SEEDS)
            ),
            key=lambda p: (_size(p), -p.tier, -p.seed),
        )
        out[skill_id] = {"tier": best.tier, "seed": best.seed, "prompt": _parts(best)}
    return out


def test_longest_prompt_fixture_is_current() -> None:
    expected = longest_prompts()
    if os.environ.get("UPDATE_FIXTURES") == "1":
        FIXTURE.parent.mkdir(exist_ok=True)
        FIXTURE.write_text(json.dumps(expected, indent=2) + "\n", encoding="utf-8")
    assert json.loads(FIXTURE.read_text(encoding="utf-8")) == expected
