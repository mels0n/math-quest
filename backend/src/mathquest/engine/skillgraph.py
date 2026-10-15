"""Skill dependency graph loaded from a content pack."""

from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
from typing import Any

import yaml

from mathquest.engine.types import KEYPAD_PROFILES, KeypadProfile


class ContentError(Exception):
    """Raised when a content pack is malformed or internally inconsistent."""


@dataclass(frozen=True)
class Skill:
    id: str
    name: str
    region: str
    prerequisites: tuple[str, ...]
    fluency: bool
    anchor: bool
    keypad: KeypadProfile = "numpad"


class SkillGraph:
    def __init__(self, skills: list[Skill]) -> None:
        by_id: dict[str, Skill] = {}
        for skill in skills:
            if skill.id in by_id:
                raise ContentError(f"duplicate skill id: {skill.id}")
            by_id[skill.id] = skill
        for skill in skills:
            for prereq in skill.prerequisites:
                if prereq not in by_id:
                    raise ContentError(f"skill {skill.id} has unknown prerequisite: {prereq}")
        self.skills: Mapping[str, Skill] = MappingProxyType(by_id)
        self._order = self._toposort(skills)
        self._rank = {skill_id: i for i, skill_id in enumerate(self._order)}

    @staticmethod
    def _toposort(skills: list[Skill]) -> list[str]:
        """Kahn's algorithm; ties break by declaration order."""
        remaining = {s.id: set(s.prerequisites) for s in skills}
        order: list[str] = []
        while remaining:
            ready = [sid for sid in remaining if not remaining[sid]]
            if not ready:
                cyclic = ", ".join(sorted(remaining))
                raise ContentError(f"prerequisite cycle among skills: {cyclic}")
            sid = ready[0]
            order.append(sid)
            del remaining[sid]
            for deps in remaining.values():
                deps.discard(sid)
        return order

    def prerequisites(self, skill_id: str) -> tuple[str, ...]:
        return self.skills[skill_id].prerequisites

    def topo_order(self) -> list[str]:
        return list(self._order)

    def ready(self, mastered: set[str]) -> list[str]:
        """Unmastered skills whose prerequisites are all mastered, in topological order."""
        return [
            sid
            for sid in self._order
            if sid not in mastered and all(p in mastered for p in self.skills[sid].prerequisites)
        ]


def _keypad(raw: object, skill_id: str) -> KeypadProfile:
    for profile in KEYPAD_PROFILES:
        if profile == raw:
            return profile
    raise ContentError(f"skill {skill_id}: unknown keypad profile: {raw}")


def _parse_skill(raw: Any) -> Skill:
    if not isinstance(raw, dict):
        raise ContentError("each skill entry must be a mapping")
    entry: dict[str, Any] = raw  # pyright: ignore[reportUnknownVariableType]
    try:
        prereqs = entry.get("prerequisites", [])
        if not isinstance(prereqs, list):
            raise ContentError(f"skill {entry['id']}: prerequisites must be a list")
        keypad = _keypad(entry["keypad"], str(entry["id"]))
        return Skill(
            id=str(entry["id"]),
            name=str(entry["name"]),
            region=str(entry["region"]),
            prerequisites=tuple(str(p) for p in prereqs),  # pyright: ignore[reportUnknownVariableType, reportUnknownArgumentType]
            fluency=bool(entry.get("fluency", False)),
            anchor=bool(entry.get("anchor", False)),
            keypad=keypad,
        )
    except KeyError as exc:
        raise ContentError(f"skill entry missing field: {exc.args[0]}") from exc


def load_pack(path: Path) -> SkillGraph:
    """Load `skills.yaml` from a pack directory."""
    file = path / "skills.yaml"
    try:
        data = yaml.safe_load(file.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        raise ContentError(f"cannot read {file}: {exc}") from exc
    if not isinstance(data, dict) or not isinstance(data.get("skills"), list):  # pyright: ignore[reportUnknownMemberType]
        raise ContentError(f"{file}: expected a top-level 'skills' list")
    return SkillGraph([_parse_skill(raw) for raw in data["skills"]])  # pyright: ignore[reportUnknownVariableType]
