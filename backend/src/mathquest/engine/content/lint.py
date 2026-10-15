# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false
r"""Content lint: checks a loaded pack beyond what loading enforces.

``lint(pack, registry, slots=..., words=...)`` returns findings, each an error or a
warning naming the pack file, the path inside it and the rule. The rules:

``graph``
    Prerequisites exist, the graph has no cycle and every skill is reachable from a
    root (a skill with no prerequisites).
``generator``
    Every skill's generator is registered with the skill's tier count, and every
    misconception given feedback in its explanations is one the generator declares.
``teaching``
    Every skill has a lesson, hints and explanations: an error in a region listed in
    ``complete_regions``, a warning elsewhere.
``coverage``
    In a complete region, every skill meets the tier, misconception, word template and
    bank item targets of ``coverage``. Elsewhere the coverage report shows the gaps.
``answers``
    Every word template renders for ``WORD_SEEDS`` seeds at every tier, with no slot
    left unfilled, and the answer it carries is accepted by the answer checker. Every
    bank item likewise. A template that uses the generator's answer but leaves out one
    of the generator's numbers is a warning (the learner may not be able to work it
    out).
``computed``
    Hints, explanations and misconception feedback render for ``TEACHING_SEEDS`` seeds
    at every tier, so every ``{{= expr }}`` in them computes. Lessons and worked
    examples render once with no values, so their computed numbers use only literals.
``duplicate``
    Two word templates, two bank items or two explanation approaches whose normalized
    token sets have a Jaccard similarity above ``DUPLICATE_SIMILARITY``: an error within
    a skill, a warning across skills.
``reading``
    For grade bands K, 1 and 2: a sentence longer than ``MAX_SENTENCE_WORDS`` words is
    an error; a word outside the simple word list (plus numbers, slots and the skill's
    ``vocabulary``) is a warning.
``dashes``
    No em dash, no en dash and no ``--`` in kid-facing text.
``slots``
    A word template names only generator values and its declared slots, declares only
    slot kinds the slot lists have, and uses every slot it declares.

Lint binds the pack to a generator registry passed in, through the same
``SkillSource`` the app uses, so what it renders is what a learner sees.
"""

import re
from collections.abc import Callable, Iterator, Mapping
from dataclasses import dataclass
from functools import lru_cache, partial
from pathlib import Path
from typing import Literal

import sympy

from mathquest.engine.catalog import SkillSource
from mathquest.engine.checker.check import Verdict, check
from mathquest.engine.content.coverage import skill_coverage
from mathquest.engine.content.loader import _cycle  # pyright: ignore[reportPrivateUsage]
from mathquest.engine.content.schema import GRADE_BANDS, Pack, Part, Skill, Slots
from mathquest.engine.teaching import (
    render_explanations,
    render_feedback,
    render_hints,
    render_lesson,
)
from mathquest.engine.templates import TemplateError, expression_names, names
from mathquest.engine.types import AnswerForm, Generator, Problem, TextPart, Variant

Level = Literal["error", "warning"]

WORD_SEEDS = 200
TEACHING_SEEDS = 50
DUPLICATE_SIMILARITY = 0.85
MAX_SENTENCE_WORDS = 12
EARLY_BANDS = frozenset({"K", "1", "2"})
SLOT_KINDS = frozenset({"names", "objects", "units", "contexts", "number"})
_COUNTED_GAPS = frozenset({"tiers", "misconceptions", "word templates", "bank items"})

assert set(GRADE_BANDS) >= EARLY_BANDS


@dataclass(frozen=True)
class Finding:
    level: Level
    file: str
    path: str
    rule: str
    message: str

    def __str__(self) -> str:
        return f"{self.file}:{self.path}: {self.rule}: {self.message}"


@dataclass(frozen=True)
class _Text:
    """One piece of kid-facing text, in template syntax."""

    file: str
    path: str
    source: str
    band: str
    skill: Skill | None


def load_word_list(path: Path) -> frozenset[str]:
    """One word per line; blank lines and lines starting with ``#`` are skipped."""
    words: set[str] = set()
    for line in path.read_text(encoding="utf-8").splitlines():
        word = line.strip().lower()
        if word and not word.startswith("#"):
            words.add(word)
    return frozenset(words)


def lint(
    pack: Pack,
    registry: Mapping[str, Generator],
    *,
    slots: Slots,
    words: frozenset[str],
) -> list[Finding]:
    """Every finding for ``pack``, errors and warnings, in rule order."""
    out: list[Finding] = []
    out += _graph(pack)
    sources, generator_findings = _sources(pack, registry, slots)
    out += generator_findings
    out += _teaching(pack)
    out += _coverage(pack, registry)
    out += _slots(pack, sources)
    out += _answers(pack, sources)
    out += _computed(pack, sources)
    texts = list(_kid_texts(pack))
    out += _duplicates(pack)
    out += _reading(texts, words)
    out += _dashes(texts)
    return out


def errors(findings: list[Finding]) -> list[Finding]:
    return [f for f in findings if f.level == "error"]


# --- rule 1: graph ---------------------------------------------------------------


def _graph(pack: Pack) -> Iterator[Finding]:
    ids = list(pack.skills)
    missing = False
    for i, skill in enumerate(pack.skills.values()):
        for j, prereq in enumerate(skill.prerequisites):
            if prereq not in pack.skills:
                missing = True
                yield Finding(
                    "error",
                    "skills.yaml",
                    f"skills[{i}].prerequisites[{j}]",
                    "graph",
                    f"unknown prerequisite {prereq}",
                )
    if missing:
        return
    cycle = _cycle(pack.skills)
    if cycle is not None:
        yield Finding(
            "error", "skills.yaml", "skills", "graph", f"prerequisite cycle: {' -> '.join(cycle)}"
        )
    dependents: dict[str, list[str]] = {sid: [] for sid in ids}
    for skill in pack.skills.values():
        for prereq in skill.prerequisites:
            dependents[prereq].append(skill.id)
    reached: set[str] = set()
    stack = [sid for sid, s in pack.skills.items() if not s.prerequisites]
    while stack:
        sid = stack.pop()
        if sid in reached:
            continue
        reached.add(sid)
        stack.extend(
            d for d in dependents[sid] if all(p in reached for p in pack.skills[d].prerequisites)
        )
    for i, sid in enumerate(ids):
        if sid not in reached:
            yield Finding(
                "error",
                "skills.yaml",
                f"skills[{i}]",
                "graph",
                f"{sid} cannot be reached from a skill without prerequisites",
            )


# --- rule 2: generators ----------------------------------------------------------


def _sources(
    pack: Pack, registry: Mapping[str, Generator], slots: Slots
) -> tuple[dict[str, SkillSource], list[Finding]]:
    sources: dict[str, SkillSource] = {}
    found: list[Finding] = []
    for i, skill in enumerate(pack.skills.values()):
        generator = registry.get(skill.generator)
        if generator is None:
            found.append(
                Finding(
                    "error",
                    "skills.yaml",
                    f"skills[{i}].generator",
                    "generator",
                    f"no generator is registered as {skill.generator}",
                )
            )
            continue
        have = len(generator.tier_difficulties)
        if have != len(skill.tiers):
            found.append(
                Finding(
                    "error",
                    "skills.yaml",
                    f"skills[{i}].tiers",
                    "generator",
                    f"{len(skill.tiers)} tiers declared but {skill.generator} has {have}",
                )
            )
            continue
        sources[skill.id] = SkillSource(
            skill=skill,
            generator=generator,
            slots=slots,
            word_problems=pack.word_problems.get(skill.id),
            bank=pack.bank.get(skill.id),
        )
    for sid, explanations in pack.explanations.items():
        generator = registry.get(pack.skills[sid].generator)
        if generator is None:
            continue
        for key in explanations.misconceptions:
            if key not in generator.misconception_keys:
                found.append(
                    Finding(
                        "error",
                        f"explanations/{sid}.yaml",
                        f"misconceptions.{key}",
                        "generator",
                        f"{generator.generator_id} never produces this misconception",
                    )
                )
    return sources, found


# --- rule 3 and coverage: completeness -------------------------------------------


def _teaching(pack: Pack) -> Iterator[Finding]:
    for i, skill in enumerate(pack.skills.values()):
        complete = skill.region in pack.complete_regions
        level: Level = "error" if complete else "warning"
        where = f"region {skill.region} is declared complete" if complete else "not written yet"
        for what, present in (
            ("lesson", pack.lessons),
            ("hints", pack.hints),
            ("explanations", pack.explanations),
        ):
            if skill.id not in present:
                yield Finding(
                    level, "skills.yaml", f"skills[{i}]", "teaching",
                    f"{skill.id} has no {what} ({where})",
                )  # fmt: skip


def _coverage(pack: Pack, registry: Mapping[str, Generator]) -> Iterator[Finding]:
    for i, skill in enumerate(pack.skills.values()):
        if skill.region not in pack.complete_regions:
            continue
        coverage = skill_coverage(pack, skill, registry.get(skill.generator))
        for gap in coverage.gaps:
            if gap.field in _COUNTED_GAPS:
                yield Finding(
                    "error", "skills.yaml", f"skills[{i}]", "coverage",
                    f"{skill.id} has {gap} (region {skill.region} is declared complete)",
                )  # fmt: skip


# --- rule 9: template slots ------------------------------------------------------


def _value_names(source: SkillSource) -> frozenset[str]:
    """Value names every generated problem of the skill has (checked on a few seeds)."""
    common: set[str] | None = None
    for tier in range(len(source.tier_difficulties)):
        for seed in range(5):
            keys = set(source.generator.generate(seed, tier).values)
            common = keys if common is None else common & keys
    return frozenset(common or ())


def _slots(pack: Pack, sources: Mapping[str, SkillSource]) -> Iterator[Finding]:
    for sid, word in pack.word_problems.items():
        source = sources.get(sid)
        if source is None:
            continue
        values = _value_names(source)
        for i, template in enumerate(word.templates):
            file, at = f"word_problems/{sid}.yaml", f"templates[{i}]"
            used = names(template.text_template)
            if template.expression is not None:
                used |= expression_names(template.expression)
            for name in sorted(used - values - set(template.slots)):
                yield Finding(
                    "error", file, f"{at}.text_template", "slots",
                    f"{name} is neither a value of {source.generator.generator_id} "
                    "nor a declared slot",
                )  # fmt: skip
            for name, kind in sorted(template.slots.items()):
                if kind not in SLOT_KINDS:
                    yield Finding(
                        "error", file, f"{at}.slots.{name}", "slots", f"unknown slot kind {kind}"
                    )
                if name in values:
                    yield Finding(
                        "error", file, f"{at}.slots.{name}", "slots",
                        f"slot {name} hides the generator value of the same name",
                    )  # fmt: skip
                elif name not in used:
                    yield Finding(
                        "error", file, f"{at}.slots.{name}", "slots",
                        f"slot {name} is declared but never used",
                    )  # fmt: skip


# --- rule 4: word problems and bank items carry checkable answers ----------------


def _answer_latex(answer: sympy.Expr) -> str:
    return str(sympy.latex(answer))


@lru_cache(maxsize=4096)
def _accepted(problem_answer: sympy.Expr, form: AnswerForm) -> bool:
    probe = Problem(
        skill_id="lint",
        tier=0,
        seed=0,
        prompt=(),
        answer=problem_answer,
        form=form,
        misconceptions=(),
        difficulty=0.0,
    )
    return check(probe, _answer_latex(problem_answer)).verdict is Verdict.CORRECT


def _unfilled(problem: Problem) -> str | None:
    for part in problem.prompt:
        if isinstance(part, TextPart) and ("{" in part.text or "}" in part.text):
            return part.text
    return None


def _answers(pack: Pack, sources: Mapping[str, SkillSource]) -> Iterator[Finding]:
    for sid, word in pack.word_problems.items():
        source = sources.get(sid)
        if source is None:
            continue
        values = _value_names(source)
        numbers = {
            k for k, v in source.generator.generate(0, 0).values.items() if isinstance(v, int)
        }
        for i, template in enumerate(word.templates):
            file, at = f"word_problems/{sid}.yaml", f"templates[{i}]"
            if template.expression is None:
                left_out = sorted((numbers & values) - names(template.text_template))
                if left_out:
                    yield Finding(
                        "warning", file, f"{at}.text_template", "answers",
                        f"uses the generator's answer but never shows {', '.join(left_out)}",
                    )  # fmt: skip
            yield from _render_all(
                file, f"{at}.text_template", source, WORD_SEEDS, "word", template.id
            )
    for sid, bank in pack.bank.items():
        source = sources.get(sid)
        if source is None:
            continue
        for i, item in enumerate(bank.items):
            yield from _render_all(f"bank/{sid}.yaml", f"items[{i}]", source, 1, "bank", item.id)


def _render_all(
    file: str,
    at: str,
    source: SkillSource,
    seeds: int,
    variant: Variant,
    template_id: str,
) -> Iterator[Finding]:
    """Render every (seed, tier); report only the first failure."""
    for tier in range(len(source.tier_difficulties)):
        for seed in range(seeds):
            try:
                problem = source.generate(seed, tier, variant, template_id)
            except TemplateError as err:
                yield Finding("error", file, at, "answers", f"seed {seed} tier {tier}: {err}")
                return
            if (text := _unfilled(problem)) is not None:
                yield Finding(
                    "error", file, at, "answers",
                    f"seed {seed} tier {tier}: unfilled slot in {text!r}",
                )  # fmt: skip
                return
            if problem.choices is not None:
                continue
            if not _accepted(problem.answer, problem.form):
                yield Finding(
                    "error", file, at, "answers",
                    f"seed {seed} tier {tier}: the answer {_answer_latex(problem.answer)} is not "
                    f"accepted as {problem.form.value}",
                )  # fmt: skip
                return


# --- rule 5: computed numbers in teaching text -----------------------------------


def _computed(pack: Pack, sources: Mapping[str, SkillSource]) -> Iterator[Finding]:
    for sid, lesson in pack.lessons.items():
        try:
            render_lesson(lesson)
        except TemplateError as err:
            yield Finding("error", f"lessons/{sid}.yaml", "(top level)", "computed", str(err))
    for sid, source in sources.items():
        checks: list[tuple[str, str, Callable[[Problem], object]]] = []
        ladder = pack.hints.get(sid)
        if ladder is not None:
            checks.append((f"hints/{sid}.yaml", "levels", partial(render_hints, ladder)))
        explanations = pack.explanations.get(sid)
        if explanations is not None:
            file = f"explanations/{sid}.yaml"
            checks.append((file, "approaches", partial(render_explanations, explanations)))
            for key in explanations.misconceptions:
                feedback = partial(render_feedback, explanations, key=key)
                checks.append((file, f"misconceptions.{key}", feedback))
        for file, at, run in checks:
            yield from _render_teaching(file, at, source, run)


def _render_teaching(
    file: str, at: str, source: SkillSource, run: Callable[[Problem], object]
) -> Iterator[Finding]:
    """Render for every (seed, tier); report only the first failure."""
    for tier in range(len(source.tier_difficulties)):
        for seed in range(TEACHING_SEEDS):
            try:
                run(source.generate(seed, tier))
            except TemplateError as err:
                yield Finding("error", file, at, "computed", f"seed {seed} tier {tier}: {err}")
                return


# --- kid-facing text --------------------------------------------------------------


def _parts_source(parts: tuple[Part, ...]) -> str:
    return " ".join(p.value if p.kind == "text" else rf"\({p.value}\)" for p in parts)


def _kid_texts(pack: Pack) -> Iterator[_Text]:
    for i, skill in enumerate(pack.skills.values()):
        yield _Text("skills.yaml", f"skills[{i}].name", skill.name, skill.grade_band, skill)
    for i, region in enumerate(pack.world.regions):
        yield _Text("world.yaml", f"regions[{i}].name", region.name, "", None)
    for sid, lesson in pack.lessons.items():
        skill, file = pack.skills[sid], f"lessons/{sid}.yaml"
        band = skill.grade_band
        for i, screen in enumerate(lesson.screens):
            yield _Text(file, f"screens[{i}].title", screen.title, band, skill)
            yield _Text(file, f"screens[{i}].body_md", screen.body_md, band, skill)
        example = lesson.worked_example
        yield _Text(file, "worked_example.prompt", _parts_source(example.prompt), band, skill)
        for i, step in enumerate(example.steps):
            yield _Text(file, f"worked_example.steps[{i}]", step, band, skill)
    for sid, ladder in pack.hints.items():
        skill = pack.skills[sid]
        for i, level in enumerate(ladder.levels):
            yield _Text(
                f"hints/{sid}.yaml", f"levels[{i}].text_template", level.text_template,
                skill.grade_band, skill,
            )  # fmt: skip
    for sid, explanations in pack.explanations.items():
        skill, file = pack.skills[sid], f"explanations/{sid}.yaml"
        for i, approach in enumerate(explanations.approaches):
            yield _Text(file, f"approaches[{i}].body_md", approach.body_md, skill.grade_band, skill)
        for key, feedback in explanations.misconceptions.items():
            yield _Text(file, f"misconceptions.{key}", feedback, skill.grade_band, skill)
    for sid, word in pack.word_problems.items():
        skill = pack.skills[sid]
        for i, template in enumerate(word.templates):
            yield _Text(
                f"word_problems/{sid}.yaml", f"templates[{i}].text_template",
                template.text_template, template.grade_band, skill,
            )  # fmt: skip
    for sid, bank in pack.bank.items():
        skill, file = pack.skills[sid], f"bank/{sid}.yaml"
        for i, item in enumerate(bank.items):
            yield _Text(
                file, f"items[{i}].prompt", _parts_source(item.prompt), skill.grade_band, skill
            )
            for j, choice in enumerate(item.choices or ()):
                yield _Text(
                    file, f"items[{i}].choices[{j}]", _parts_source(choice), skill.grade_band, skill
                )


_MATH = re.compile(r"\\\(.*?\\\)", re.DOTALL)
_CALC = re.compile(r"\{\{=.*?\}\}", re.DOTALL)
_SLOT = re.compile(r"\{[A-Za-z_][A-Za-z0-9_]*(?:\.one)?\}")


def _words_only(source: str) -> str:
    """Text with math, computed numbers and slots each replaced by `#` (one word)."""
    return _SLOT.sub(" # ", _CALC.sub(" # ", _MATH.sub(" # ", source)))


# --- rule 6: duplicates ----------------------------------------------------------


def _tokens(source: str) -> frozenset[str]:
    text = _SLOT.sub(" slot ", _CALC.sub(" 0 ", source)).lower()
    text = re.sub(r"\d+", " # ", text)
    text = re.sub(r"\\[a-z]+", " ", text)
    return frozenset(re.findall(r"[a-z#']+", text))


def _similarity(a: frozenset[str], b: frozenset[str]) -> float:
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


@dataclass(frozen=True)
class _Item:
    file: str
    path: str
    skill: str
    tokens: frozenset[str]


def _duplicates(pack: Pack) -> Iterator[Finding]:
    groups: dict[str, list[_Item]] = {"word template": [], "bank item": [], "explanation": []}
    for sid, word in pack.word_problems.items():
        for i, t in enumerate(word.templates):
            groups["word template"].append(
                _Item(f"word_problems/{sid}.yaml", f"templates[{i}]", sid, _tokens(t.text_template))
            )
    for sid, bank in pack.bank.items():
        for i, item in enumerate(bank.items):
            text = " ".join(
                [_parts_source(item.prompt), *(_parts_source(c) for c in item.choices or ())]
            )
            groups["bank item"].append(_Item(f"bank/{sid}.yaml", f"items[{i}]", sid, _tokens(text)))
    for sid, explanations in pack.explanations.items():
        for i, a in enumerate(explanations.approaches):
            groups["explanation"].append(
                _Item(f"explanations/{sid}.yaml", f"approaches[{i}]", sid, _tokens(a.body_md))
            )
    for what, items in groups.items():
        for a, b in _similar_pairs(items):
            same = a.skill == b.skill
            other = b.path if same else f"{b.file}:{b.path}"
            yield Finding(
                "error" if same else "warning", a.file, a.path, "duplicate",
                f"{what} is nearly the same as {other}",
            )  # fmt: skip


def _similar_pairs(items: list[_Item]) -> Iterator[tuple[_Item, _Item]]:
    """Pairs above the threshold. Sizes far apart cannot reach it, so they are skipped."""
    ordered = sorted(enumerate(items), key=lambda pair: len(pair[1].tokens))
    for x, (i, a) in enumerate(ordered):
        for j, b in ordered[x + 1 :]:
            if len(a.tokens) <= DUPLICATE_SIMILARITY * len(b.tokens):
                break
            if _similarity(a.tokens, b.tokens) > DUPLICATE_SIMILARITY:
                yield (a, b) if i < j else (b, a)


# --- rule 7: reading level -------------------------------------------------------

_LIST_MARK = re.compile(r"^\s*(?:\d+[.)]|[-*])\s+")
_SENTENCE_END = re.compile(r"(?<=[.!?])\s+")
_WORD = re.compile(r"[A-Za-z]+(?:'[A-Za-z]+)?")


def _sentences(source: str) -> Iterator[str]:
    for line in _words_only(source).splitlines():
        line = _LIST_MARK.sub("", line).strip()
        for sentence in _SENTENCE_END.split(line):
            if sentence.strip():
                yield sentence.strip()


def _known(word: str, words: frozenset[str]) -> bool:
    if word in words:
        return True
    if word.endswith("'s"):
        return _known(word[:-2], words)
    candidates: list[str] = []
    for suffix, replacements in (
        ("ies", ("y",)),
        ("ied", ("y",)),
        ("es", ("", "e")),
        ("s", ("",)),
        ("ed", ("", "e")),
        ("ing", ("", "e")),
        ("er", ("", "e")),
        ("est", ("", "e")),
        ("ly", ("",)),
    ):
        if word.endswith(suffix) and len(word) > len(suffix) + 1:
            stem = word[: -len(suffix)]
            candidates.extend(stem + r for r in replacements)
            if len(stem) > 2 and stem[-1] == stem[-2]:
                candidates.append(stem[:-1])  # hopping -> hop
    return any(c in words for c in candidates)


def _reading(texts: list[_Text], words: frozenset[str]) -> Iterator[Finding]:
    for text in texts:
        if text.band not in EARLY_BANDS or text.skill is None:
            continue
        allowed = words | frozenset(text.skill.vocabulary)
        for sentence in _sentences(text.source):
            count = len(sentence.split())
            sentence = " ".join(sentence.split())
            if count > MAX_SENTENCE_WORDS:
                yield Finding(
                    "error", text.file, text.path, "reading",
                    f"{count} words in one sentence (at most {MAX_SENTENCE_WORDS} for "
                    f"grade {text.band}): {sentence!r}",
                )  # fmt: skip
        unknown = sorted(
            {
                w.lower()
                for w in _WORD.findall(_words_only(text.source))
                if not _known(w.lower(), allowed)
            }
        )
        if unknown:
            yield Finding(
                "warning", text.file, text.path, "reading",
                f"not in the grade {text.band} word list: {', '.join(unknown)}",
            )  # fmt: skip


# --- rule 8: dashes --------------------------------------------------------------


def _dashes(texts: list[_Text]) -> Iterator[Finding]:
    for text in texts:
        if "\u2014" in text.source:
            yield Finding("error", text.file, text.path, "dashes", "em dash in kid-facing text")
        if "\u2013" in text.source:
            yield Finding("error", text.file, text.path, "dashes", "en dash in kid-facing text")
        if "--" in _MATH.sub(" ", text.source):
            yield Finding("error", text.file, text.path, "dashes", "'--' used as a dash")
