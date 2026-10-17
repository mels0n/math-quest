"""The one prerequisite-cycle check, used by the pack loader and the skill graph."""

from collections.abc import Mapping
from typing import Protocol


class HasPrerequisites(Protocol):
    @property
    def prerequisites(self) -> tuple[str, ...]: ...


def find_cycle(skills: Mapping[str, HasPrerequisites]) -> list[str] | None:
    """A prerequisite cycle as skill ids (the first repeated at the end), or None.

    Prerequisites that are not in ``skills`` are ignored; callers check them first.
    """
    state: dict[str, int] = {}  # 1 visiting, 2 done
    stack: list[str] = []

    def visit(sid: str) -> list[str] | None:
        state[sid] = 1
        stack.append(sid)
        for prereq in skills[sid].prerequisites:
            if prereq not in skills:
                continue
            if state.get(prereq) == 1:
                return [*stack[stack.index(prereq) :], prereq]
            if prereq not in state and (found := visit(prereq)) is not None:
                return found
        stack.pop()
        state[sid] = 2
        return None

    for sid in skills:
        if sid not in state and (found := visit(sid)) is not None:
            return found
    return None
