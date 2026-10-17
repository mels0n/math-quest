"""Skill dependency graph, built from a loaded content pack's skills."""

from collections.abc import Collection, Iterable, Mapping
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

    def ancestors(self, skill_id: str) -> set[str]:
        """Every prerequisite of the skill, transitively (not the skill itself)."""
        found: set[str] = set()
        stack = list(self.skills[skill_id].prerequisites)
        while stack:
            sid = stack.pop()
            if sid not in found:
                found.add(sid)
                stack.extend(self.skills[sid].prerequisites)
        return found

    def topo_order(self) -> list[str]:
        return list(self._order)

    def implied(self, mastered: Collection[str]) -> set[str]:
        """Skills the learner can be taken to know without playing them: every prerequisite,
        direct or transitive, of a skill they have mastered, that is not mastered itself.
        ``ready`` applies this only to skills never played; a started skill that is not
        mastered is offered whatever is above it. Content added later under skills a learner
        already knows must not send them back to it
        (docs/adr/0020-readiness-for-existing-learners.md)."""
        known = set(mastered)
        found: set[str] = set()
        for sid in known:
            if sid in self.skills:
                found |= self.ancestors(sid)
        return found - known

    def ready(self, mastered: Collection[str], started: Collection[str] = ()) -> list[str]:
        """Unmastered skills to offer, in topological order: every skill the learner has
        started and not mastered (whatever prerequisites it gained since, and whatever is
        mastered above it), and every never-played skill whose prerequisites are all mastered
        or implied (see ``implied``) and which is not itself implied."""
        done = set(mastered)
        begun = set(started) - done
        known = done | (self.implied(done) - begun)
        return [
            sid
            for sid in self._order
            if sid not in done
            and (
                sid in begun
                or (sid not in known and all(p in known for p in self.skills[sid].prerequisites))
            )
        ]
