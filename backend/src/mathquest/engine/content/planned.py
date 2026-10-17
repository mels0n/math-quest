"""The build plan: skills that are designed but have no generator yet.

``planned_skills.yaml`` sits beside ``skills.yaml`` in a pack. It lists the skills still
to build, with the same fields as ``skills.yaml`` minus ``generator``, plus the Common
Core ``standards`` each covers and the ``batch`` it is built in. ``load_pack`` never
reads it, so a planned skill cannot reach play or placement; a batch moves its skills
into ``skills.yaml`` when their generators exist.

``lint_planned(pack, plan)`` checks the plan against the built skills, as one graph:

``planned-ids``
    Ids are unique and do not collide with a built skill (a skill that has been built
    must leave the plan). Two skills sharing a kid-facing name is a warning.
``planned-scope``
    Every region is in ``world.yaml`` and in the plan's scope; every grade band is in
    the scope.
``planned-graph``
    Every prerequisite and ``unlocks`` target exists, the combined graph has no cycle
    and every skill can be reached from a root, a skill without prerequisites belongs
    in batch 1, and no prerequisite lies in a later region or grade band.
``planned-batch``
    Batches are numbered 1 to N without gaps and every prerequisite is built in the same
    or an earlier batch (or is already built). A batch of more than ``MAX_BATCH`` skills
    is a warning.
``planned-anchors``
    Within the scope's regions, anchors in topological order never fall to an earlier
    grade band, and every grade band of the scope has one.
``planned-tiers``
    At least ``MIN_TIERS`` tiers.
``planned-standards``
    A skill does not cite a standard from a later grade or the same one twice.
``planned-text``
    Names and tier labels are short and use no dash (em dash, en dash, ``--`` or a
    spaced hyphen).

The standards codes themselves, the keypad and the field names are checked when the
file loads, so a malformed plan is a ``ContentError`` rather than a finding.
"""

from collections.abc import Iterator, Mapping, Sequence
from dataclasses import dataclass
from itertools import pairwise
from pathlib import Path

from mathquest.engine.content.coverage import MIN_TIERS
from mathquest.engine.content.graph import find_cycle
from mathquest.engine.content.lint import Finding
from mathquest.engine.content.loader import load_validated
from mathquest.engine.content.schema import GRADE_BANDS, Pack, PlannedList, PlannedSkill

PLAN_FILE = "planned_skills.yaml"
MAX_BATCH = 12
MAX_NAME = 32
MAX_LABEL = 40
DASHES = (chr(0x2014), chr(0x2013), "--", " - ")

_FILE = PLAN_FILE


@dataclass(frozen=True)
class _Node:
    """What the graph checks need to know about any skill, built or planned."""

    id: str
    region: str
    band: int
    anchor: bool
    prerequisites: tuple[str, ...]


def load_planned(pack_dir: Path) -> PlannedList | None:
    """The pack's plan, or None when it has none. A ``ContentError`` if it is malformed."""
    if not (pack_dir / PLAN_FILE).is_file():
        return None
    return load_validated(PlannedList, pack_dir, PLAN_FILE)


def _band(label: str) -> int:
    return GRADE_BANDS.index(label)


def _standard_band(code: str) -> int:
    grade = code.split(".", 1)[0]
    return 0 if grade == "K" else int(grade)


def _first_by_id(plan: PlannedList) -> dict[str, tuple[int, PlannedSkill]]:
    found: dict[str, tuple[int, PlannedSkill]] = {}
    for i, skill in enumerate(plan.planned):
        found.setdefault(skill.id, (i, skill))
    return found


def _nodes(pack: Pack, plan: PlannedList) -> dict[str, _Node]:
    """Built skills in file order, then planned skills by batch (file order within a
    batch): the order the skills have once built. Unlocks edges are added as
    prerequisites of their targets."""
    nodes: dict[str, _Node] = {
        s.id: _Node(s.id, s.region, _band(s.grade_band), s.anchor, s.prerequisites)
        for s in pack.skills.values()
    }
    planned = sorted(_first_by_id(plan).values(), key=lambda pair: pair[1].batch)
    for _, p in planned:
        if p.id not in nodes:
            nodes[p.id] = _Node(p.id, p.region, _band(p.grade_band), p.anchor, p.prerequisites)
    for _, p in planned:
        for target in p.unlocks:
            node = nodes.get(target)
            if node is not None and p.id not in node.prerequisites and target != p.id:
                nodes[target] = _Node(
                    node.id, node.region, node.band, node.anchor, (*node.prerequisites, p.id)
                )
    return nodes


def lint_planned(pack: Pack, plan: PlannedList) -> list[Finding]:
    """Every finding for ``plan`` checked against ``pack``'s built skills."""
    nodes = _nodes(pack, plan)
    out: list[Finding] = []
    out += _ids(pack, plan)
    out += _scope(pack, plan)
    out += _graph(pack, plan, nodes)
    out += _batches(pack, plan)
    out += _anchors(pack, plan, nodes)
    out += _tiers(plan)
    out += _standards(plan)
    out += _text(plan)
    return out


def _error(path: str, rule: str, message: str) -> Finding:
    return Finding("error", _FILE, path, rule, message)


# --- ids and scope ---------------------------------------------------------------


def _ids(pack: Pack, plan: PlannedList) -> Iterator[Finding]:
    seen: set[str] = set()
    names = {s.name.lower(): s.id for s in pack.skills.values()}
    for i, p in enumerate(plan.planned):
        if p.id in pack.skills:
            yield _error(
                f"planned[{i}].id",
                "planned-ids",
                f"{p.id} is already built; remove it from the plan",
            )
        elif p.id in seen:
            yield _error(f"planned[{i}].id", "planned-ids", f"duplicate planned skill id {p.id}")
        seen.add(p.id)
        other = names.setdefault(p.name.lower(), p.id)
        if other != p.id:
            yield Finding(
                "warning", _FILE, f"planned[{i}].name", "planned-ids",
                f"{p.id} has the same name as {other}",
            )  # fmt: skip


def _scope(pack: Pack, plan: PlannedList) -> Iterator[Finding]:
    regions = {r.id for r in pack.world.regions}
    for j, region in enumerate(plan.scope.regions):
        if region not in regions:
            yield _error(f"scope.regions[{j}]", "planned-scope", f"unknown region {region}")
    for i, p in enumerate(plan.planned):
        if p.region not in regions:
            yield _error(f"planned[{i}].region", "planned-scope", f"unknown region {p.region}")
        elif p.region not in plan.scope.regions:
            yield _error(
                f"planned[{i}].region", "planned-scope", f"region {p.region} is outside the plan"
            )
        if p.grade_band not in plan.scope.grade_bands:
            yield _error(
                f"planned[{i}].grade_band",
                "planned-scope",
                f"grade band {p.grade_band} is outside the plan",
            )


# --- the graph -------------------------------------------------------------------


def _graph(pack: Pack, plan: PlannedList, nodes: Mapping[str, _Node]) -> Iterator[Finding]:
    order = {r.id: r.order for r in pack.world.regions}
    for i, p in enumerate(plan.planned):
        for j, prereq in enumerate(p.prerequisites):
            other = nodes.get(prereq)
            path = f"planned[{i}].prerequisites[{j}]"
            if other is None:
                yield _error(path, "planned-graph", f"unknown skill {prereq}")
            else:
                yield from _direction(path, other, nodes[p.id], order)
        for j, target in enumerate(p.unlocks):
            path = f"planned[{i}].unlocks[{j}]"
            node = nodes.get(target)
            if node is None:
                yield _error(path, "planned-graph", f"unknown skill {target}")
            elif target == p.id:
                yield _error(path, "planned-graph", f"{p.id} cannot unlock itself")
            else:
                yield from _direction(path, nodes[p.id], node, order)
    cycle = find_cycle(nodes)
    if cycle is not None:
        yield _error("planned", "planned-graph", f"prerequisite cycle: {' -> '.join(cycle)}")
        return
    reached = _reachable(nodes)
    batch = {p.id: p.batch for _, p in _first_by_id(plan).values()}
    for i, p in enumerate(plan.planned):
        if p.id not in reached:
            yield _error(
                f"planned[{i}]", "planned-graph", f"{p.id} cannot be reached from a root skill"
            )
        elif not nodes[p.id].prerequisites and batch[p.id] != 1:
            yield _error(
                f"planned[{i}].prerequisites",
                "planned-graph",
                f"{p.id} has no prerequisites, so it belongs in batch 1",
            )


def _direction(
    path: str, before: _Node, after: _Node, order: Mapping[str, int]
) -> Iterator[Finding]:
    """``before`` is a prerequisite of ``after``: it must not lie later on the map."""
    if order.get(before.region, 0) > order.get(after.region, 0):
        yield _error(
            path,
            "planned-graph",
            f"{before.id} is in {before.region}, later on the map than {after.id}",
        )
    if before.band > after.band:
        yield _error(
            path,
            "planned-graph",
            f"{before.id} is for grade {GRADE_BANDS[before.band]}, "
            f"later than {after.id} (grade {GRADE_BANDS[after.band]})",
        )


def _reachable(nodes: Mapping[str, _Node]) -> set[str]:
    """Skills whose prerequisites can all be learned, starting from the roots."""
    learned: set[str] = set()
    grew = True
    while grew:
        grew = False
        for node in nodes.values():
            if node.id not in learned and all(p in learned for p in node.prerequisites):
                learned.add(node.id)
                grew = True
    return learned


# --- batches ---------------------------------------------------------------------


def _batches(pack: Pack, plan: PlannedList) -> Iterator[Finding]:
    planned = {p.id: p for _, p in _first_by_id(plan).values()}
    present = sorted({p.batch for p in plan.planned})
    if present and present != list(range(1, present[-1] + 1)):
        yield _error(
            "planned", "planned-batch", f"batches must run 1 to {present[-1]} with none missing"
        )
    sizes = {b: sum(1 for p in plan.planned if p.batch == b) for b in present}
    for b, size in sizes.items():
        if size > MAX_BATCH:
            yield Finding(
                "warning", _FILE, "planned", "planned-batch",
                f"batch {b} has {size} skills; keep a batch to about 10",
            )  # fmt: skip
    for i, p in enumerate(plan.planned):
        for j, prereq in enumerate(p.prerequisites):
            other = planned.get(prereq)
            if other is not None and other.batch > p.batch:
                yield _error(
                    f"planned[{i}].prerequisites[{j}]",
                    "planned-batch",
                    f"{prereq} is in batch {other.batch}, after batch {p.batch} of {p.id}",
                )
        for j, target in enumerate(p.unlocks):
            other = planned.get(target)
            if other is not None and other.batch < p.batch:
                yield _error(
                    f"planned[{i}].unlocks[{j}]",
                    "planned-batch",
                    f"{target} is in batch {other.batch}, before batch {p.batch} of {p.id}",
                )


# --- anchors ---------------------------------------------------------------------


def _topological(nodes: Mapping[str, _Node]) -> list[str]:
    """Kahn's algorithm, ties broken by declaration order, like the skill graph's."""
    remaining = {sid: set(node.prerequisites) & nodes.keys() for sid, node in nodes.items()}
    out: list[str] = []
    while remaining:
        ready = [sid for sid, deps in remaining.items() if not deps]
        if not ready:  # a cycle, reported by the graph rule
            break
        out.append(ready[0])
        del remaining[ready[0]]
        for deps in remaining.values():
            deps.discard(out[-1])
    return out


def _anchors(pack: Pack, plan: PlannedList, nodes: Mapping[str, _Node]) -> Iterator[Finding]:
    inside = {sid: n for sid, n in nodes.items() if n.region in plan.scope.regions}
    spine = [sid for sid in _topological(inside) if inside[sid].anchor]
    for before, after in pairwise(spine):
        if inside[after].band < inside[before].band:
            yield _error(
                "planned",
                "planned-anchors",
                f"anchor {after} (grade {GRADE_BANDS[inside[after].band]}) comes after "
                f"{before} (grade {GRADE_BANDS[inside[before].band]}) in the spine",
            )
    have = {inside[sid].band for sid in spine}
    for grade in plan.scope.grade_bands:
        if _band(grade) not in have:
            yield _error("scope.grade_bands", "planned-anchors", f"no anchor for grade {grade}")


# --- per-skill checks ------------------------------------------------------------


def _tiers(plan: PlannedList) -> Iterator[Finding]:
    for i, p in enumerate(plan.planned):
        if len(p.tiers) < MIN_TIERS:
            yield _error(
                f"planned[{i}].tiers",
                "planned-tiers",
                f"{p.id} has {len(p.tiers)} tiers; at least {MIN_TIERS} are needed",
            )


def _standards(plan: PlannedList) -> Iterator[Finding]:
    for i, p in enumerate(plan.planned):
        for j, code in enumerate(p.standards):
            path = f"planned[{i}].standards[{j}]"
            if _standard_band(code) > _band(p.grade_band):
                yield _error(path, "planned-standards", f"{code} is from a later grade than {p.id}")
            if code in p.standards[:j]:
                yield _error(path, "planned-standards", f"{code} is listed twice")


def _dashed(text: str) -> bool:
    return any(d in text for d in DASHES)


def _text(plan: PlannedList) -> Iterator[Finding]:
    for i, p in enumerate(plan.planned):
        yield from _one_text(f"planned[{i}].name", p.name, MAX_NAME)
        for j, tier in enumerate(p.tiers):
            yield from _one_text(f"planned[{i}].tiers[{j}].label", tier.label, MAX_LABEL)


def _one_text(path: str, text: str, limit: int) -> Iterator[Finding]:
    if _dashed(text):
        yield _error(path, "planned-text", "use no dash; a full stop or a comma works")
    if len(text) > limit:
        yield _error(path, "planned-text", f"{len(text)} characters; keep it to {limit}")


# --- report ----------------------------------------------------------------------


@dataclass(frozen=True)
class RegionPlan:
    region_id: str
    name: str
    built: int
    planned: int


@dataclass(frozen=True)
class BatchPlan:
    batch: int
    skills: int
    regions: dict[str, int]
    grade_bands: tuple[str, ...]


@dataclass(frozen=True)
class PlanSummary:
    regions: tuple[RegionPlan, ...]
    batches: tuple[BatchPlan, ...]

    @property
    def planned(self) -> int:
        return sum(r.planned for r in self.regions)


def plan_summary(pack: Pack, plan: PlannedList) -> PlanSummary:
    """Built and planned skills per region in map order, and the plan per batch."""
    built = [s.region for s in pack.skills.values()]
    regions = tuple(
        RegionPlan(
            r.id,
            r.name,
            built.count(r.id),
            sum(1 for p in plan.planned if p.region == r.id),
        )
        for r in sorted(pack.world.regions, key=lambda r: r.order)
    )
    batches: list[BatchPlan] = []
    for b in sorted({p.batch for p in plan.planned}):
        members: Sequence[PlannedSkill] = [p for p in plan.planned if p.batch == b]
        per_region = {r.region_id: 0 for r in regions}
        for p in members:
            per_region[p.region] += 1
        grades = sorted({p.grade_band for p in members}, key=_band)
        batches.append(
            BatchPlan(b, len(members), {k: v for k, v in per_region.items() if v}, tuple(grades))
        )
    return PlanSummary(regions, tuple(batches))
