"""A loaded content pack bound to the generator registry.

The content package is pure data and never imports generators; this module joins the
two and checks what only the registry can answer: every skill's generator exists, its
tier count matches the skill's declared tiers, and every misconception key that the
skill's explanations give feedback for is one the generator declares, and every typed
bank answer is in the answer form the skill's generator asks for (an integer skill
cannot bank a fraction answer). ``check_binding`` lists every misfit (the content lint
reports them all); ``build_catalog`` raises on the first. The app builds a Catalog at
boot, so a pack that fails any of these stops the app from starting.
"""

import dataclasses
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType

from mathquest.engine.bank import expr_answer, find_item, pick_item, render_bank
from mathquest.engine.checker.forms import satisfies_form
from mathquest.engine.checker.latex import parse
from mathquest.engine.content import ContentError, Pack, Skill, Slots, load_pack, load_slots
from mathquest.engine.content.schema import Bank, WordProblems
from mathquest.engine.generators import all_generators
from mathquest.engine.skillgraph import SkillGraph
from mathquest.engine.types import VARIANTS, Generator, Problem, Variant
from mathquest.engine.wordproblems import find_template, pick_template, render_word


@dataclass(frozen=True)
class SkillSource:
    """Problems for one skill: its generator's, retold by its word problems and bank.

    ``generate(seed, tier, variant, template_id)`` is deterministic. For ``word`` and
    ``bank`` a ``template_id`` of None picks a template or item by seed; the chosen id
    is on the returned problem, and passing it back regenerates the same problem. A
    variant the skill has no content for, or an id that no longer exists, falls back
    to the bare problem.
    """

    skill: Skill
    generator: Generator
    slots: Slots
    word_problems: WordProblems | None = None
    bank: Bank | None = None

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
        bare = self.generator.generate(seed, tier)
        problem = dataclasses.replace(bare, skill_id=self.skill.id)
        if variant == "word" and self.word_problems is not None:
            template = (
                pick_template(self.word_problems, seed, tier)
                if template_id is None
                else find_template(self.word_problems, template_id)
            )
            if template is not None:
                return render_word(template, problem, self.slots)
        if variant == "bank" and self.bank is not None:
            item = (
                pick_item(self.bank, seed, tier)
                if template_id is None
                else find_item(self.bank, template_id)
            )
            if item is not None:
                return render_bank(item, problem)
        return problem

    def shows_generator(self, problem: Problem) -> bool:
        """``problem`` keeps the generator's numbers and answer: it is bare, or a word
        problem whose template does not compute its own answer. Hints, explanations and
        mistake feedback are written over the generator's values, so only such a problem
        gets them; a bank item or an expression template has an answer of its own."""
        if problem.variant == "bare":
            return True
        if problem.variant != "word" or self.word_problems is None:
            return False
        if problem.template_id is None:
            return False
        template = find_template(self.word_problems, problem.template_id)
        return template is not None and template.expression is None


@dataclass(frozen=True)
class Catalog:
    pack: Pack
    slots: Slots
    graph: SkillGraph
    sources: Mapping[str, SkillSource]

    def source(self, skill_id: str) -> SkillSource:
        """The problem source of ``skill_id``; KeyError for an unknown skill."""
        return self.sources[skill_id]

    def regenerate(
        self, skill_id: str, seed: int, tier: int, variant: str, template_id: str | None
    ) -> Problem:
        """An issued problem again from what is stored for it; an unknown variant name is
        read as bare. KeyError for an unknown skill."""
        chosen: Variant = "bare"
        for known in VARIANTS:
            if known == variant:
                chosen = known
        return self.sources[skill_id].generate(seed, tier, chosen, template_id)


@dataclass(frozen=True)
class BindingProblem:
    """A way ``pack`` does not fit the generator registry, located in a pack file."""

    file: str
    path: str
    message: str

    def __str__(self) -> str:
        return f"{self.file}: {self.path}: {self.message}"


def check_binding(pack: Pack, registry: Mapping[str, Generator]) -> list[BindingProblem]:
    """Every way ``pack`` does not fit ``registry``; empty when it binds."""
    found: list[BindingProblem] = []
    bound: dict[str, Generator] = {}
    for i, skill in enumerate(pack.skills.values()):
        generator = registry.get(skill.generator)
        if generator is None:
            found.append(
                BindingProblem(
                    "skills.yaml", f"skills[{i}].generator", f"unknown generator {skill.generator}"
                )
            )
            continue
        have = len(generator.tier_difficulties)
        if have != len(skill.tiers):
            found.append(
                BindingProblem(
                    "skills.yaml",
                    f"skills[{i}].tiers",
                    f"{len(skill.tiers)} tiers declared but generator {skill.generator} has {have}",
                )
            )
            continue
        bound[skill.id] = generator
    for sid, explanations in pack.explanations.items():
        generator = bound.get(sid)
        if generator is None:
            continue
        for key in explanations.misconceptions:
            if key not in generator.misconception_keys:
                found.append(
                    BindingProblem(
                        f"explanations/{sid}.yaml",
                        f"misconceptions.{key}",
                        f"generator {generator.generator_id} never produces this misconception",
                    )
                )
    for sid, bank in pack.bank.items():
        generator = bound.get(sid)
        if generator is None:
            continue
        form = generator.generate(0, 0).form
        for i, item in enumerate(bank.items):
            if item.answer.kind != "expr":
                continue
            node = parse(str(item.answer.value))
            if not satisfies_form(node, expr_answer(item), form):
                found.append(
                    BindingProblem(
                        f"bank/{sid}.yaml",
                        f"items[{i}].answer.value",
                        f"not in the skill's answer form ({form.value})",
                    )
                )
    return found


def build_catalog(
    pack: Pack, slots: Slots, registry: Mapping[str, Generator] | None = None
) -> Catalog:
    """Bind ``pack`` to ``registry`` (default: the built-in generators); raise on a misfit."""
    generators = all_generators() if registry is None else registry
    problems = check_binding(pack, generators)
    if problems:
        raise ContentError(str(problems[0]))
    sources = {
        skill.id: SkillSource(
            skill=skill,
            generator=generators[skill.generator],
            slots=slots,
            word_problems=pack.word_problems.get(skill.id),
            bank=pack.bank.get(skill.id),
        )
        for skill in pack.skills.values()
    }
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
