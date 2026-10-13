"""Registry of problem generators, one per skill."""

from collections.abc import Mapping
from types import MappingProxyType

from mathquest.engine.generators import early, fractions, place_value
from mathquest.engine.types import Generator

_REGISTRY: Mapping[str, Generator] = MappingProxyType(
    {
        g.skill_id: g
        for g in [*early.generators(), *place_value.generators(), *fractions.generators()]
    }
)


def get_generator(skill_id: str) -> Generator:
    """Return the generator for ``skill_id``; KeyError when there is none."""
    return _REGISTRY[skill_id]


def all_generators() -> Mapping[str, Generator]:
    return _REGISTRY
