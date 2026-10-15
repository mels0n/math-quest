"""The longest prompt of every skill, shared with the end-to-end prompt-fit check.

``testdata/longest-prompts.json`` (repo root) holds, per skill, the prompt with the most
characters over the first SEEDS seeds of every tier; a skill with word problems also
gets a ``<skill>-word`` entry, the longest over every template, and a skill with bank
items a ``<skill>-bank`` entry. The browser test lays each one out at phone and desktop
widths. Regenerate it with ``UPDATE_FIXTURES=1 uv run pytest
tests/engine/test_prompt_fixture.py`` after changing a generator or content.
"""

import json
import os
from pathlib import Path

from mathquest.engine.catalog import SkillSource, load_catalog
from mathquest.engine.types import Problem, TextPart, Variant

FIXTURE = Path(__file__).resolve().parents[3] / "testdata" / "longest-prompts.json"
CATALOG = load_catalog(Path(__file__).resolve().parents[2] / "content", "k8-core")
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


def _variant_ids(source: SkillSource) -> dict[Variant, list[str | None]]:
    ids: dict[Variant, list[str | None]] = {"bare": [None]}
    if source.word_problems is not None:
        ids["word"] = [t.id for t in source.word_problems.templates]
    if source.bank is not None:
        ids["bank"] = [i.id for i in source.bank.items]
    return ids


def longest_prompts() -> dict[str, object]:
    out: dict[str, object] = {}
    for skill_id, source in sorted(CATALOG.sources.items()):
        for variant, template_ids in _variant_ids(source).items():
            best = max(
                (
                    source.generate(seed, tier, variant, template_id)
                    for tier in range(len(source.tier_difficulties))
                    for seed in range(SEEDS)
                    for template_id in template_ids
                ),
                key=lambda p: (_size(p), -p.tier, -p.seed),
            )
            key = skill_id if variant == "bare" else f"{skill_id}-{variant}"
            out[key] = {"tier": best.tier, "seed": best.seed, "prompt": _parts(best)}
    return out


def test_longest_prompt_fixture_is_current() -> None:
    expected = longest_prompts()
    if os.environ.get("UPDATE_FIXTURES") == "1":
        FIXTURE.parent.mkdir(exist_ok=True)
        FIXTURE.write_text(json.dumps(expected, indent=2) + "\n", encoding="utf-8")
    assert json.loads(FIXTURE.read_text(encoding="utf-8")) == expected
