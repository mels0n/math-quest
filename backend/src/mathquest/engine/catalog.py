"""A loaded content pack bound to the generator registry.

The content package is pure data and never imports generators; this module joins the
two and checks what only the registry can answer: every skill's generator exists, its
tier count matches the skill's declared tiers, and every misconception key that the
skill's explanations give feedback for is one the generator declares. The app builds a
Catalog at boot, so a pack that fails any of these stops the app from starting.
"""

import dataclasses
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType

from mathquest.engine.content import ContentError, Pack, Skill, Slots, load_pack, load_slots
from mathquest.engine.generators import all_generators
from mathquest.engine.skillgraph import SkillGraph
from mathquest.engine.types import Generator, Problem, Variant


@dataclass(frozen=True)
class SkillSource:
    """Problems for one skill: its generator, presented as the skill."""

    skill: Skill
    generator: Generator

    @property
    def skill_id(self) -> str:
        return self.skill.id

    @property
    def tier_difficulties(self) -> tuple[float, ...]:
        return self.generator.tier_difficulties

    def generate(
        self,
        seed: int,
        tier: int,
        variant: Variant = "bare",
        template_id: str | None = None,
    ) -> Problem:
        problem = self.generator.generate(seed, tier, variant, template_id)
        return dataclasses.replace(problem, skill_id=self.skill.id)


@dataclass(frozen=True)
class Catalog:
    pack: Pack
    slots: Slots
    graph: SkillGraph
    sources: Mapping[str, SkillSource]

    def source(self, skill_id: str) -> SkillSource:
        """The problem source of ``skill_id``; KeyError for an unknown skill."""
        return self.sources[skill_id]


def build_catalog(
    pack: Pack, slots: Slots, registry: Mapping[str, Generator] | None = None
) -> Catalog:
    """Bind ``pack`` to ``registry`` (default: the built-in generators) and check it."""
    generators = all_generators() if registry is None else registry
    sources: dict[str, SkillSource] = {}
    for i, skill in enumerate(pack.skills.values()):
        where = f"skills.yaml: skills[{i}]"
        generator = generators.get(skill.generator)
        if generator is None:
            raise ContentError(f"{where}.generator: unknown generator {skill.generator}")
        have = len(generator.tier_difficulties)
        if have != len(skill.tiers):
            raise ContentError(
                f"{where}.tiers: {len(skill.tiers)} tiers declared but generator "
                f"{skill.generator} has {have}"
            )
        sources[skill.id] = SkillSource(skill=skill, generator=generator)
    for sid, explanations in pack.explanations.items():
        generator = sources[sid].generator
        for key in explanations.misconceptions:
            if key not in generator.misconception_keys:
                raise ContentError(
                    f"explanations/{sid}.yaml: misconceptions.{key}: generator "
                    f"{generator.generator_id} never produces this misconception"
                )
    return Catalog(
        pack=pack,
        slots=slots,
        graph=SkillGraph(pack.skills.values()),
        sources=MappingProxyType(sources),
    )


def load_catalog(content_dir: Path, pack_id: str) -> Catalog:
    """Load ``content_dir/packs/<pack_id>`` and ``content_dir/slots.yaml`` and bind them."""
    pack = load_pack(content_dir / "packs" / pack_id)
    return build_catalog(pack, load_slots(content_dir / "slots.yaml"))
