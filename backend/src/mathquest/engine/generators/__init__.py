"""Registry of problem generators, keyed by generator id.

A skill names its generator in ``skills.yaml``; existing skills use a generator of the
same id.
"""

from collections.abc import Mapping
from types import MappingProxyType

from mathquest.engine.generators import (
    clock,
    compare_1000,
    comparing,
    counting,
    early,
    fractions,
    graphs,
    groups,
    hundreds,
    mental,
    parity,
    place_value,
    stories,
    stories_100,
    strategies,
    subtraction,
    tables,
    tens,
)
from mathquest.engine.types import Generator

_REGISTRY: Mapping[str, Generator] = MappingProxyType(
    {
        g.generator_id: g
        for g in [
            *early.generators(),
            *place_value.generators(),
            *fractions.generators(),
            *counting.generators(),
            *comparing.generators(),
            *strategies.generators(),
            *tens.generators(),
            *stories.generators(),
            *subtraction.generators(),
            *mental.generators(),
            *clock.generators(),
            *graphs.generators(),
            *parity.generators(),
            *compare_1000.generators(),
            *stories_100.generators(),
            *hundreds.generators(),
            *groups.generators(),
            *tables.generators(),
        ]
    }
)


def get_generator(generator_id: str) -> Generator:
    """Return the generator registered as ``generator_id``; KeyError when there is none."""
    return _REGISTRY[generator_id]


def all_generators() -> Mapping[str, Generator]:
    return _REGISTRY
