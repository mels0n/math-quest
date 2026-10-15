"""How much content each skill has, against the per-skill targets.

Targets per skill: a generator with at least 3 tiers and at least 2 misconceptions,
with feedback written for every misconception it names; at least 15 word templates when
word problems fit the skill; at least 30 bank items when the skill is banked; one
lesson; three hints; three or four explanations.

The numbers are the same everywhere they are shown: the coverage report, the content
lint (where gaps in a complete region are errors) and the admin preview. The generator
registry is passed in, so this module imports no generators.
"""

from collections.abc import Mapping
from dataclasses import dataclass

from mathquest.engine.content.schema import Pack, Skill
from mathquest.engine.types import Generator

MIN_TIERS = 3
MIN_MISCONCEPTIONS = 2
MIN_WORD_TEMPLATES = 15
MIN_BANK_ITEMS = 30
HINT_LEVELS = 3
MIN_EXPLANATIONS = 3
MAX_EXPLANATIONS = 4

TARGETS = {
    "tiers": f"{MIN_TIERS}+",
    "misconceptions": f"{MIN_MISCONCEPTIONS}+",
    "word templates": f"{MIN_WORD_TEMPLATES}+",
    "bank items": f"{MIN_BANK_ITEMS}+",
    "lesson": "1",
    "hints": str(HINT_LEVELS),
    "explanations": f"{MIN_EXPLANATIONS}-{MAX_EXPLANATIONS}",
}
"""Each target as shown to people; misconception feedback is one per misconception."""


@dataclass(frozen=True)
class Gap:
    """One target a skill misses: ``have`` of ``want`` for ``field``."""

    field: str
    have: int
    want: int

    def __str__(self) -> str:
        return f"{self.field} {self.have} of {self.want}"


@dataclass(frozen=True)
class SkillCoverage:
    skill_id: str
    name: str
    region: str
    tiers: int
    misconceptions: int
    feedback: int
    """Misconceptions of the generator that have feedback written."""
    word_templates: int | None
    """None when word problems do not fit the skill."""
    bank_items: int | None
    """None when the skill is not banked."""
    lesson: bool
    hints: int
    explanations: int
    gaps: tuple[Gap, ...]

    @property
    def complete(self) -> bool:
        return not self.gaps


@dataclass(frozen=True)
class RegionCoverage:
    region_id: str
    name: str
    complete: bool
    """Declared complete in ``pack.yaml``: every gap here is a lint error."""
    skills: tuple[SkillCoverage, ...]


@dataclass(frozen=True)
class PackCoverage:
    pack_id: str
    title: str
    version: str
    regions: tuple[RegionCoverage, ...]

    def skills(self) -> tuple[SkillCoverage, ...]:
        return tuple(s for r in self.regions for s in r.skills)


def skill_coverage(pack: Pack, skill: Skill, generator: Generator | None) -> SkillCoverage:
    tiers = len(skill.tiers) if generator is None else len(generator.tier_difficulties)
    keys = () if generator is None else generator.misconception_keys
    misconceptions = len(keys)
    word = pack.word_problems.get(skill.id)
    bank = pack.bank.get(skill.id)
    hints = pack.hints.get(skill.id)
    explanations = pack.explanations.get(skill.id)
    counts: dict[str, tuple[int, int]] = {
        "tiers": (tiers, MIN_TIERS),
        "misconceptions": (misconceptions, MIN_MISCONCEPTIONS),
    }
    word_templates = None
    if skill.word_problems_fit:
        word_templates = 0 if word is None else len(word.templates)
        counts["word templates"] = (word_templates, MIN_WORD_TEMPLATES)
    bank_items = None
    if skill.banked:
        bank_items = 0 if bank is None else len(bank.items)
        counts["bank items"] = (bank_items, MIN_BANK_ITEMS)
    lesson = skill.id in pack.lessons
    hint_count = 0 if hints is None else len(hints.levels)
    explanation_count = 0 if explanations is None else len(explanations.approaches)
    written = {} if explanations is None else explanations.misconceptions
    feedback = sum(1 for key in keys if key in written)
    counts["misconception feedback"] = (feedback, misconceptions)
    counts["lesson"] = (int(lesson), 1)
    counts["hints"] = (hint_count, HINT_LEVELS)
    counts["explanations"] = (explanation_count, MIN_EXPLANATIONS)
    return SkillCoverage(
        skill_id=skill.id,
        name=skill.name,
        region=skill.region,
        tiers=tiers,
        misconceptions=misconceptions,
        feedback=feedback,
        word_templates=word_templates,
        bank_items=bank_items,
        lesson=lesson,
        hints=hint_count,
        explanations=explanation_count,
        gaps=tuple(Gap(f, have, want) for f, (have, want) in counts.items() if have < want),
    )


def pack_coverage(pack: Pack, registry: Mapping[str, Generator]) -> PackCoverage:
    """Coverage of every skill in ``pack``, grouped by region in map order."""
    regions: list[RegionCoverage] = []
    for region in sorted(pack.world.regions, key=lambda r: r.order):
        skills = tuple(
            skill_coverage(pack, skill, registry.get(skill.generator))
            for skill in pack.skills.values()
            if skill.region == region.id
        )
        regions.append(
            RegionCoverage(
                region_id=region.id,
                name=region.name,
                complete=region.id in pack.complete_regions,
                skills=skills,
            )
        )
    return PackCoverage(
        pack_id=pack.id, title=pack.title, version=pack.version, regions=tuple(regions)
    )
