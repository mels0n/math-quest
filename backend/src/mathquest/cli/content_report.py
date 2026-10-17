"""``content-report``: how much content each skill has, against the per-skill targets.

Usage: ``uv run content-report [PACK_DIR ...] [--json] [--stuck FILE]`` (run in
``backend/``; default: every pack under ``content/packs``). Prints a Markdown table per
region with totals, or the same numbers as JSON. The report never fails on gaps; in a
region declared complete the content lint does.

A pack with a build plan (``planned_skills.yaml``) also gets the planned skills per
region and per batch.

``--stuck FILE`` reads a stuck-problem export: a JSON list of
``{"skill", "generator", "tier", "seed", "wrong_answers": [...]}`` objects, one per
problem a learner could not solve, and adds a count per skill.
"""

import argparse
import dataclasses
import json
import sys
from collections import Counter
from collections.abc import Sequence
from pathlib import Path
from typing import Annotated, Any

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter, ValidationError

from mathquest.cli.content_lint import pack_dirs
from mathquest.engine.content import ContentError, load_pack
from mathquest.engine.content.coverage import (
    TARGETS,
    PackCoverage,
    SkillCoverage,
    pack_coverage,
)
from mathquest.engine.content.planned import PlanSummary, load_planned, plan_summary
from mathquest.engine.generators import all_generators


class StuckProblem(BaseModel):
    """One entry of a stuck-problem export."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    skill: Annotated[str, Field(min_length=1, max_length=64)]
    generator: Annotated[str, Field(min_length=1, max_length=64)]
    tier: Annotated[int, Field(ge=0)]
    seed: int
    wrong_answers: list[Annotated[str, Field(max_length=256)]]


_STUCK = TypeAdapter(list[StuckProblem])


def read_stuck(path: Path) -> Counter[str]:
    """Stuck problems per skill id from an export file."""
    entries = _STUCK.validate_json(path.read_bytes())
    return Counter(entry.skill for entry in entries)


def _cell(skill: SkillCoverage, field: str, have: int | None, target: str) -> str:
    if have is None:
        return "n/a"
    short = any(g.field == field for g in skill.gaps)
    return f"{have} / {target}" + (" ⚠" if short else "")


def _row(skill: SkillCoverage, stuck: Counter[str] | None) -> str:
    cells = [
        f"`{skill.skill_id}`",
        _cell(skill, "tiers", skill.tiers, TARGETS["tiers"]),
        _cell(skill, "misconceptions", skill.misconceptions, TARGETS["misconceptions"]),
        _cell(skill, "misconception feedback", skill.feedback, str(skill.misconceptions)),
        _cell(skill, "word templates", skill.word_templates, TARGETS["word templates"]),
        _cell(skill, "bank items", skill.bank_items, TARGETS["bank items"]),
        "yes" if skill.lesson else "no ⚠",
        _cell(skill, "hints", skill.hints, TARGETS["hints"]),
        _cell(skill, "explanations", skill.explanations, TARGETS["explanations"]),
    ]
    if stuck is not None:
        cells.append(str(stuck.get(skill.skill_id, 0)))
    gaps = len(skill.gaps)
    cells.append("done" if not gaps else f"{gaps} gap" if gaps == 1 else f"{gaps} gaps")
    return "| " + " | ".join(cells) + " |"


def plan_markdown(plan: PlanSummary) -> list[str]:
    lines = [
        "## Planned skills",
        "",
        "| Region | Built | Planned | Total |",
        "|---|---|---|---|",
    ]
    for region in plan.regions:
        total = region.built + region.planned
        lines.append(f"| {region.name} | {region.built} | {region.planned} | {total} |")
    lines += ["", "| Batch | Skills | Grades | Regions |", "|---|---|---|---|"]
    for batch in plan.batches:
        regions = ", ".join(f"{k} {v}" for k, v in batch.regions.items())
        lines.append(
            f"| {batch.batch} | {batch.skills} | {', '.join(batch.grade_bands)} | {regions} |"
        )
    return [*lines, ""]


def markdown(
    coverage: PackCoverage, stuck: Counter[str] | None = None, plan: PlanSummary | None = None
) -> str:
    head = [
        "Skill", "Tiers", "Mistakes", "Feedback", "Word", "Bank", "Lesson", "Hints",
        "Explanations",
    ]  # fmt: skip
    if stuck is not None:
        head.append("Stuck")
    head.append("Status")
    lines = [f"# {coverage.title} ({coverage.pack_id} {coverage.version})", ""]
    for region in coverage.regions:
        state = "declared complete" if region.complete else "in progress"
        lines += [f"## {region.name} ({state})", ""]
        if not region.skills:
            lines += ["No skills yet.", ""]
            continue
        lines.append("| " + " | ".join(head) + " |")
        lines.append("|" + "---|" * len(head))
        lines += [_row(skill, stuck) for skill in region.skills]
        lines.append("")
    skills = coverage.skills()
    gaps = Counter(gap.field for skill in skills for gap in skill.gaps)
    lines += [
        "## Totals",
        "",
        f"- Skills: {len(skills)}, meeting every target: {sum(s.complete for s in skills)}",
        f"- Lessons: {sum(s.lesson for s in skills)}",
        f"- Word templates: {sum(s.word_templates or 0 for s in skills)}",
        f"- Bank items: {sum(s.bank_items or 0 for s in skills)}",
    ]
    if stuck is not None:
        lines.append(f"- Stuck problems: {sum(stuck.values())}")
    if gaps:
        lines.append("- Skills short of each target: " + ", ".join(
            f"{field} {count}" for field, count in sorted(gaps.items())
        ))  # fmt: skip
    if plan is not None:
        lines += ["", *plan_markdown(plan)]
    return "\n".join(lines) + "\n"


def as_json(
    coverage: PackCoverage, stuck: Counter[str] | None = None, plan: PlanSummary | None = None
) -> dict[str, Any]:
    data = dataclasses.asdict(coverage)
    if plan is not None:
        data["planned"] = dataclasses.asdict(plan)
    for region in data["regions"]:
        for skill in region["skills"]:
            if stuck is not None:
                skill["stuck"] = stuck.get(skill["skill_id"], 0)
    return data


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="content-report", description="Content coverage.")
    parser.add_argument("packs", nargs="*", help="pack directories (default: content/packs/*)")
    parser.add_argument("--json", action="store_true", help="print JSON instead of Markdown")
    parser.add_argument("--stuck", type=Path, help="stuck-problem export (JSON) to count")
    args = parser.parse_args(argv)
    stuck: Counter[str] | None = None
    if args.stuck is not None:
        try:
            stuck = read_stuck(args.stuck)
        except (OSError, ValidationError) as err:
            print(f"cannot read {args.stuck}: {err}", file=sys.stderr)
            return 2
    reports: list[tuple[PackCoverage, PlanSummary | None]] = []
    for pack_dir in pack_dirs(args.packs):
        try:
            pack = load_pack(pack_dir)
            plan = load_planned(pack_dir)
            summary = None if plan is None else plan_summary(pack, plan)
            reports.append((pack_coverage(pack, all_generators()), summary))
        except ContentError as err:
            print(f"{pack_dir}/{err}", file=sys.stderr)
            return 2
    if args.json:
        print(json.dumps({"packs": [as_json(r, stuck, p) for r, p in reports]}, indent=2))
    else:
        print("\n".join(markdown(r, stuck, p) for r, p in reports), end="")
    return 0


if __name__ == "__main__":
    sys.exit(main())
