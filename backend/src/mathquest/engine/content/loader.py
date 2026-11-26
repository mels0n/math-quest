"""Load and validate a content pack.

Pack layout (``content/packs/<pack>/``)::

    pack.yaml                 id, title, version, complete_regions
    skills.yaml               skills: [...]
    world.yaml                regions: [...]
    lessons/<skill>.yaml
    hints/<skill>.yaml
    explanations/<skill>.yaml
    word_problems/<skill>.yaml
    bank/<skill>.yaml

Each file is validated against its schema, then the files are checked against each
other: every skill's region is in the world, prerequisites exist and form no cycle,
boss skill sets name real skills, every per-skill file names a known skill and is
named after it, word problems only exist for skills marked ``word_problems_fit`` and
bank items only for ``banked`` skills, and every skill of a region listed in
``complete_regions`` has its lesson, hints and explanations (plus word problems and
bank items where its flags ask for them).

Every failure is a ``ContentError`` whose message names the file relative to the pack
and the path inside it, such as ``lessons/add_within_20.yaml: screens[1].visual.kind``.
"""

from collections.abc import Mapping
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, ValidationError

from mathquest.engine.content.errors import ContentError
from mathquest.engine.content.graph import find_cycle
from mathquest.engine.content.schema import (
    Bank,
    Explanations,
    HintLadder,
    Lesson,
    Pack,
    PackMeta,
    Skill,
    SkillList,
    Slots,
    WordProblems,
    World,
)


def _where(loc: tuple[int | str, ...]) -> str:
    out = ""
    for step in loc:
        if isinstance(step, int):
            out += f"[{step}]"
        else:
            out += f".{step}" if out else step
    return out or "(top level)"


def _fail(file: str, loc: tuple[int | str, ...], message: str) -> ContentError:
    return ContentError(f"{file}: {_where(loc)}: {message}")


def _read(root: Path, rel: str) -> Any:
    path = root / rel
    try:
        return yaml.safe_load(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise ContentError(f"{rel}: file is missing") from None
    except (OSError, UnicodeDecodeError, yaml.YAMLError) as exc:
        raise ContentError(f"{rel}: cannot read: {exc}") from None


def _validate[M: BaseModel](model: type[M], data: Any, rel: str) -> M:
    try:
        return model.model_validate(data)
    except ValidationError as exc:
        problems = [
            f"{rel}: {_where(tuple(e['loc']))}: {e['msg']}" for e in exc.errors(include_url=False)
        ]
        raise ContentError("; ".join(problems)) from None


def load_validated[M: BaseModel](model: type[M], root: Path, rel: str) -> M:
    """Read ``rel`` under ``root`` and validate it as ``model``; a ``ContentError`` if not."""
    return _validate(model, _read(root, rel), rel)


def load_slots(path: Path) -> Slots:
    """Load the shared slot lists (``content/slots.yaml``)."""
    return _validate(Slots, _read(path.parent, path.name), path.name)


def _skills(root: Path, region_ids: set[str]) -> dict[str, Skill]:
    rel = "skills.yaml"
    listed = _validate(SkillList, _read(root, rel), rel).skills
    skills: dict[str, Skill] = {}
    for i, skill in enumerate(listed):
        if skill.id in skills:
            raise _fail(rel, ("skills", i, "id"), f"duplicate skill id {skill.id}")
        if skill.region not in region_ids:
            raise _fail(rel, ("skills", i, "region"), f"unknown region {skill.region}")
        skills[skill.id] = skill
    for i, skill in enumerate(listed):
        for j, prereq in enumerate(skill.prerequisites):
            if prereq not in skills:
                raise _fail(rel, ("skills", i, "prerequisites", j), f"unknown skill {prereq}")
    cycle = find_cycle(skills)
    if cycle is not None:
        raise _fail(rel, ("skills",), f"prerequisite cycle: {' -> '.join(cycle)}")
    return skills


def _per_skill[M: Lesson | HintLadder | Explanations | WordProblems | Bank](
    root: Path, folder: str, model: type[M], skills: Mapping[str, Skill]
) -> dict[str, M]:
    out: dict[str, M] = {}
    directory = root / folder
    if not directory.is_dir():
        return out
    for path in sorted(directory.glob("*.yaml")):
        rel = f"{folder}/{path.name}"
        item = _validate(model, _read(root, rel), rel)
        if item.skill != path.stem:
            raise _fail(rel, ("skill",), f"{item.skill} does not match the file name")
        if item.skill not in skills:
            raise _fail(rel, ("skill",), f"unknown skill {item.skill}")
        out[item.skill] = item
    return out


def _check_teaching(pack: Pack) -> None:
    for sid, lesson in pack.lessons.items():
        tiers = len(pack.skills[sid].tiers)
        if lesson.try_it.tier >= tiers:
            raise _fail(
                f"lessons/{sid}.yaml", ("try_it", "tier"), f"skill {sid} has only {tiers} tiers"
            )
    for sid in pack.word_problems:
        if not pack.skills[sid].word_problems_fit:
            raise _fail(
                f"word_problems/{sid}.yaml", ("skill",), f"{sid} has word_problems_fit: false"
            )
    for sid, word in pack.word_problems.items():
        tiers = len(pack.skills[sid].tiers)
        for i, template in enumerate(word.templates):
            if template.tiers is not None and any(not 0 <= t < tiers for t in template.tiers):
                raise _fail(
                    f"word_problems/{sid}.yaml",
                    ("templates", i, "tiers"),
                    f"skill {sid} has only {tiers} tiers",
                )
        if any(t.tiers is not None for t in word.templates):
            for tier in range(tiers):
                if not any(t.tiers is None or tier in t.tiers for t in word.templates):
                    raise _fail(
                        f"word_problems/{sid}.yaml",
                        ("templates",),
                        f"no template serves tier {tier} of {sid}",
                    )
    for sid, bank in pack.bank.items():
        tiers = len(pack.skills[sid].tiers)
        for i, item in enumerate(bank.items):
            if item.tier is not None and item.tier >= tiers:
                raise _fail(
                    f"bank/{sid}.yaml",
                    ("items", i, "tier"),
                    f"skill {sid} has only {tiers} tiers",
                )
    for sid in pack.bank:
        if not pack.skills[sid].banked:
            raise _fail(f"bank/{sid}.yaml", ("skill",), f"{sid} has banked: false")
    for i, skill in enumerate(pack.skills.values()):
        if skill.keypad != "choice":
            continue
        bank = pack.bank.get(skill.id)
        if (
            skill.bank_share < 1.0
            or bank is None
            or any(item.answer.kind != "choice" for item in bank.items)
        ):
            raise _fail(
                "skills.yaml",
                ("skills", i, "keypad"),
                "a choice keypad needs bank_share 1 and a bank of choice items only",
            )


def _check_complete(pack: Pack) -> None:
    for i, region in enumerate(pack.complete_regions):
        for skill in pack.skills.values():
            if skill.region != region:
                continue
            needed: dict[str, Mapping[str, object]] = {
                "lesson": pack.lessons,
                "hints": pack.hints,
                "explanations": pack.explanations,
            }
            if skill.word_problems_fit:
                needed["word problems"] = pack.word_problems
            if skill.banked:
                needed["bank items"] = pack.bank
            for what, present in needed.items():
                if skill.id not in present:
                    raise _fail(
                        "pack.yaml",
                        ("complete_regions", i),
                        f"region {region} is declared complete but {skill.id} has no {what}",
                    )


def load_pack(path: Path) -> Pack:
    """Load, validate and cross-check the pack in directory ``path``."""
    meta = _validate(PackMeta, _read(path, "pack.yaml"), "pack.yaml")
    if meta.id != path.name:
        raise _fail("pack.yaml", ("id",), f"{meta.id} does not match the directory {path.name}")
    world = _validate(World, _read(path, "world.yaml"), "world.yaml")
    region_ids = {r.id for r in world.regions}
    for i, region in enumerate(meta.complete_regions):
        if region not in region_ids:
            raise _fail("pack.yaml", ("complete_regions", i), f"unknown region {region}")
    skills = _skills(path, region_ids)
    for i, region in enumerate(world.regions):
        for j, sid in enumerate(region.boss_skill_set):
            if sid not in skills:
                raise _fail(
                    "world.yaml", ("regions", i, "boss_skill_set", j), f"unknown skill {sid}"
                )
    pack = Pack(
        id=meta.id,
        title=meta.title,
        version=meta.version,
        complete_regions=meta.complete_regions,
        skills=skills,
        world=world,
        lessons=_per_skill(path, "lessons", Lesson, skills),
        hints=_per_skill(path, "hints", HintLadder, skills),
        explanations=_per_skill(path, "explanations", Explanations, skills),
        word_problems=_per_skill(path, "word_problems", WordProblems, skills),
        bank=_per_skill(path, "bank", Bank, skills),
    )
    _check_teaching(pack)
    _check_complete(pack)
    return pack
