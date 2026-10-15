"""Skill dependency graph, built from a loaded content pack's skills."""

from collections.abc import Iterable, Mapping
from types import MappingProxyType

from mathquest.engine.content.errors import ContentError
from mathquest.engine.content.graph import find_cycle
from mathquest.engine.content.schema import Skill


class SkillGraph:
    def __init__(self, skills: Iterable[Skill]) -> None:
        listed = list(skills)
        by_id: dict[str, Skill] = {}
        for skill in listed:
            if skill.id in by_id:
                raise ContentError(f"duplicate skill id: {skill.id}")
            by_id[skill.id] = skill
        for skill in listed:
            for prereq in skill.prerequisites:
                if prereq not in by_id:
                    raise ContentError(f"skill {skill.id} has unknown prerequisite: {prereq}")
        cycle = find_cycle(by_id)
        if cycle is not None:
            raise ContentError(f"prerequisite cycle among skills: {' -> '.join(cycle)}")
        self.skills: Mapping[str, Skill] = MappingProxyType(by_id)
        self._order = self._toposort(listed)
        self._rank = {skill_id: i for i, skill_id in enumerate(self._order)}

    @staticmethod
    def _toposort(skills: list[Skill]) -> list[str]:
        """Kahn's algorithm; ties break by declaration order."""
        remaining = {s.id: set(s.prerequisites) for s in skills}
        order: list[str] = []
        while remaining:
            ready = [sid for sid in remaining if not remaining[sid]]
            sid = ready[0]  # never empty: find_cycle ran first
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
