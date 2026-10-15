# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false
r"""Content lint: checks a loaded pack beyond what loading enforces.

``lint(pack, registry, slots=..., words=...)`` returns findings, each an error or a
warning naming the pack file, the path inside it and the rule. The rules:

``generator``
    The pack binds to the registry (``catalog.check_binding``): every skill's generator
    is registered with the skill's tier count, every misconception given feedback is
    one the generator declares, and typed bank answers are in the skill's answer form.
``teaching``
    Every skill has a lesson, hints and explanations: an error in a region listed in
    ``complete_regions``, a warning elsewhere.
``coverage``
    In a complete region, every skill meets the tier, misconception, misconception
    feedback, word template and bank item targets of ``coverage``. Elsewhere a mistake
    the generator names without feedback written is a warning, and the coverage report
    shows the other gaps.
``answers``
    Every word template renders for ``WORD_SEEDS`` seeds at every tier, with no slot
    left unfilled, and the answer it carries is accepted by the answer checker. Every
    bank item likewise. A template that uses the generator's answer but never shows one
    of the generator's numbers (or a number always equal to one it shows) is a warning:
    the learner may not be able to work it out. Whether the story's operation matches
    the answer (a "gives away" story on an adding skill) is left to the reviewer.
``grammar``
    In every rendered word problem and bank item: "1" followed by a plural object or
    unit, "a" before a vowel sound or "an" before a consonant sound is an error. A
    sentence that starts with a digit is a warning.
``computed``
    Hints, explanations and misconception feedback render for ``TEACHING_SEEDS`` seeds
    at every tier, so every ``{{= expr }}`` in them computes. Lessons and worked
    examples render once with no values, so their computed numbers use only literals.
``duplicate``
    Two word templates, two bank items or two explanation approaches whose normalized
    word sequences match above ``DUPLICATE_SIMILARITY`` (``difflib`` ratio; words in
    order, so swapping one noun or verb still counts as a copy): an error within a
    skill, a warning across skills.
``reading``
    For grade bands K, 1 and 2: a sentence longer than ``MAX_SENTENCE_WORDS`` words is
    an error; a word outside the simple word list (plus numbers, slots and the skill's
    ``vocabulary``) is a warning. Lines wrapped inside a paragraph are joined first.
``dashes``
    No em dash, no en dash, no ``--`` and no spaced hyphen (" - ") used as a dash in
    kid-facing text outside math, nor any dash in the slot lists or the word list.
``slots``
    A word template names only generator values and its declared slots, and uses every
    slot it declares (slot kinds are checked by the schema).

Lint runs on a pack the loader accepted, so the prerequisite graph already has no
cycle and no unknown skill, and every skill is reachable from one without
prerequisites. It binds the pack to a generator registry passed in, through the same
``SkillSource`` the app uses, so what it renders is what a learner sees.
"""

import re
from collections.abc import Callable, Iterator, Mapping
from dataclasses import dataclass
from difflib import SequenceMatcher
from functools import lru_cache, partial
from pathlib import Path
from typing import Literal

import sympy

from mathquest.engine.catalog import SkillSource, check_binding
from mathquest.engine.checker.check import Verdict, check
from mathquest.engine.content.coverage import skill_coverage
from mathquest.engine.content.schema import GRADE_BANDS, Pack, Part, Skill, Slots
from mathquest.engine.teaching import (
    render_explanations,
    render_feedback,
    render_hints,
    render_lesson,
)
from mathquest.engine.templates import TemplateError, article, expression_names, names, plain
from mathquest.engine.types import AnswerForm, Generator, Problem, TextPart, Variant

Level = Literal["error", "warning"]

WORD_SEEDS = 200
TEACHING_SEEDS = 50
DUPLICATE_SIMILARITY = 0.75
MAX_SENTENCE_WORDS = 12
EARLY_BANDS = frozenset({"K", "1", "2"})
_COUNTED_GAPS = frozenset(
    {"tiers", "misconceptions", "misconception feedback", "word templates", "bank items"}
)

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
    sources, generator_findings = _sources(pack, registry, slots)
    out += generator_findings
    out += _teaching(pack)
    out += _coverage(pack, registry)
    out += _slots(pack, sources)
    out += _answers(pack, sources, _plurals(slots))
    out += _computed(pack, sources)
    texts = list(_kid_texts(pack))
    out += _duplicates(pack)
    out += _reading(texts, words)
    out += _dashes(texts)
    out += _list_dashes(slots, words)
    return out


def errors(findings: list[Finding]) -> list[Finding]:
    return [f for f in findings if f.level == "error"]


# --- rule 2: generators ----------------------------------------------------------


def _sources(
    pack: Pack, registry: Mapping[str, Generator], slots: Slots
) -> tuple[dict[str, SkillSource], list[Finding]]:
    """Sources for the skills that bind, and a finding for every binding problem."""
    problems = check_binding(pack, registry)
    found = [Finding("error", p.file, p.path, "generator", p.message) for p in problems]
    unbound = {p.path.split(".")[0] for p in problems if p.file == "skills.yaml"}
    sources = {
        skill.id: SkillSource(
            skill=skill,
            generator=registry[skill.generator],
            slots=slots,
            word_problems=pack.word_problems.get(skill.id),
            bank=pack.bank.get(skill.id),
        )
        for i, skill in enumerate(pack.skills.values())
        if f"skills[{i}]" not in unbound
    }
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
        complete = skill.region in pack.complete_regions
        coverage = skill_coverage(pack, skill, registry.get(skill.generator))
        for gap in coverage.gaps:
            if complete and gap.field in _COUNTED_GAPS:
                yield Finding(
                    "error", "skills.yaml", f"skills[{i}]", "coverage",
                    f"{skill.id} has {gap} (region {skill.region} is declared complete)",
                )  # fmt: skip
            elif gap.field == "misconception feedback":
                yield Finding(
                    "warning", "skills.yaml", f"skills[{i}]", "coverage",
                    f"{skill.id} has {gap}: write feedback for every mistake it names",
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
            for name in sorted(template.slots):
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


def _plurals(slots: Slots) -> frozenset[str]:
    nouns = (*slots.objects, *slots.length_units, *slots.time_units, *slots.money_units)
    return frozenset(n.many.lower() for n in nouns if n.many != n.one)


def _always_shown(source: SkillSource, used: frozenset[str], name: str) -> bool:
    """``name`` is not used but always equals a number the template does show."""
    for tier in range(len(source.tier_difficulties)):
        for seed in range(20):
            values = source.generator.generate(seed, tier).values
            shown = {values[u] for u in used if u in values}
            if values[name] not in shown:
                return False
    return True


def _answers(
    pack: Pack, sources: Mapping[str, SkillSource], plurals: frozenset[str]
) -> Iterator[Finding]:
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
                used = names(template.text_template)
                left_out = sorted(
                    n for n in (numbers & values) - used if not _always_shown(source, used, n)
                )
                if left_out:
                    yield Finding(
                        "warning", file, f"{at}.text_template", "answers",
                        f"uses the generator's answer but never shows {', '.join(left_out)}",
                    )  # fmt: skip
            yield from _render_all(
                file, f"{at}.text_template", source, WORD_SEEDS, "word", template.id, plurals
            )
    for sid, bank in pack.bank.items():
        source = sources.get(sid)
        if source is None:
            continue
        for i, item in enumerate(bank.items):
            yield from _render_all(
                f"bank/{sid}.yaml", f"items[{i}]", source, 1, "bank", item.id, plurals
            )


_ARTICLE = re.compile(r"\b(a|an) ([A-Za-z]+)", re.IGNORECASE)
_DIGIT_START = re.compile(r"(?:^|[.!?]\s+)\d")


def _grammar(text: str, plurals: frozenset[str]) -> str | None:
    """The first agreement or article slip in rendered ``text``, or None."""
    for plural in plurals:
        if re.search(rf"(?<![\d.])1 {re.escape(plural)}\b", text):
            return f"'1 {plural}' needs the singular"
    for match in _ARTICLE.finditer(text):
        written, word = match.group(1).lower(), match.group(2)
        if written != article(word):
            return f"'{match.group(0)}' should be '{article(word)} {word}'"
    return None


def _render_all(
    file: str,
    at: str,
    source: SkillSource,
    seeds: int,
    variant: Variant,
    template_id: str,
    plurals: frozenset[str],
) -> Iterator[Finding]:
    """Render every (seed, tier); report only the first failure of each rule."""
    grammar_seen = digit_seen = False
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
            shown = " ".join(p.text for p in problem.prompt if isinstance(p, TextPart)).strip()
            if not grammar_seen and (slip := _grammar(shown, plurals)) is not None:
                grammar_seen = True
                yield Finding("error", file, at, "grammar", f"seed {seed} tier {tier}: {slip}")
            if not digit_seen and _DIGIT_START.search(plain(problem.prompt).strip()):
                digit_seen = True
                yield Finding(
                    "warning", file, at, "grammar",
                    "a sentence starts with a number; start with a word instead",
                )  # fmt: skip
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
_SLOT = re.compile(r"\{(?:[A-Za-z_][A-Za-z0-9_]* )?[A-Za-z_][A-Za-z0-9_]*(?:\.(?:one|a))?\}")


def _words_only(source: str) -> str:
    """Text with math, computed numbers and slots each replaced by `#` (one word)."""
    return _SLOT.sub(" # ", _CALC.sub(" # ", _MATH.sub(" # ", source)))


# --- rule 6: duplicates ----------------------------------------------------------


def _tokens(source: str) -> tuple[str, ...]:
    text = _SLOT.sub(" slot ", _CALC.sub(" 0 ", source)).lower()
    text = re.sub(r"\d+", " # ", text)
    text = re.sub(r"\\[a-z]+", " ", text)
    return tuple(re.findall(r"[a-z#']+", text))


@dataclass(frozen=True)
class _Item:
    file: str
    path: str
    skill: str
    tokens: tuple[str, ...]


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
    """Pairs above the threshold, in input order. A pair whose lengths alone cap the
    ratio at the threshold is skipped before any matching."""
    ordered = sorted(enumerate(items), key=lambda pair: len(pair[1].tokens))
    for x, (i, a) in enumerate(ordered):
        for j, b in ordered[x + 1 :]:
            la, lb = len(a.tokens), len(b.tokens)
            if not la or 2 * la / (la + lb) <= DUPLICATE_SIMILARITY:
                break
            matcher = SequenceMatcher(None, a.tokens, b.tokens, autojunk=False)
            if matcher.quick_ratio() > DUPLICATE_SIMILARITY and (
                matcher.ratio() > DUPLICATE_SIMILARITY
            ):
                yield (a, b) if i < j else (b, a)


# --- rule 7: reading level -------------------------------------------------------

_LIST_MARK = re.compile(r"^\s*(?:\d+[.)]|[-*])\s+")
_SENTENCE_END = re.compile(r"(?<=[.!?])\s+")
_WORD = re.compile(r"[A-Za-z]+(?:'[A-Za-z]+)?")


def _paragraphs(source: str) -> Iterator[str]:
    """Paragraphs and list items, with lines wrapped inside them joined."""
    current: list[str] = []
    for line in _words_only(source).splitlines():
        if not line.strip() or _LIST_MARK.match(line):
            if current:
                yield " ".join(current)
            current = [_LIST_MARK.sub("", line).strip()] if line.strip() else []
        else:
            current.append(line.strip())
    if current:
        yield " ".join(current)


def _sentences(source: str) -> Iterator[str]:
    for paragraph in _paragraphs(source):
        for sentence in _SENTENCE_END.split(paragraph):
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
        words = _MATH.sub(" ", text.source)
        if "--" in words:
            yield Finding("error", text.file, text.path, "dashes", "'--' used as a dash")
        elif _SPACED_HYPHEN.search(words):
            yield Finding("error", text.file, text.path, "dashes", "' - ' used as a dash")


_SPACED_HYPHEN = re.compile(r"\S\s+-\s+\S")
_ANY_DASH = re.compile("\u2014|\u2013|--|\\s-\\s")


def _list_dashes(slots: Slots, words: frozenset[str]) -> Iterator[Finding]:
    """Dashes in the shared slot lists and the word list (paths from the pack folder)."""
    entries: list[tuple[str, str]] = [(f"names[{i}]", n) for i, n in enumerate(slots.names)]
    entries += [(f"contexts[{i}]", c) for i, c in enumerate(slots.contexts)]
    for kind in ("objects", "length_units", "time_units", "money_units"):
        for i, noun in enumerate(getattr(slots, kind)):
            entries += [(f"{kind}[{i}].one", noun.one), (f"{kind}[{i}].many", noun.many)]
    for path, value in entries:
        if _ANY_DASH.search(f" {value} "):
            yield Finding("error", "../../slots.yaml", path, "dashes", f"dash in {value!r}")
    for word in sorted(words):
        if "\u2014" in word or "\u2013" in word or "-" in word:
            yield Finding("error", "../../lint/k2_words.txt", word, "dashes", "dash in a word")
