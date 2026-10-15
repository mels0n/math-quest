# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false
r"""The template language of kid-facing content text.

Hints, explanations, misconception feedback, lesson text and word problems are written
as templates and rendered into a prompt (a tuple of text and math parts).

Syntax:

- ``{a}`` inserts the value named ``a``: a number or word the generator chose (its
  ``values``), or a filled word-problem slot. Names are letters, digits and
  underscores, starting with a letter or underscore.
- ``{obj}`` inserts an object or unit slot in the plural, ``{obj.one}`` in the
  singular and ``{obj.a}`` in the singular after its article ("an apple", "a pear").
  The article is the noun's own ``article`` when the slot list gives one, else "an"
  before a vowel letter and "a" otherwise, with the exceptions in ``article``.
- ``{n obj}`` inserts a number and a countable that agrees with it: "1 rock",
  "5 rocks". ``n`` is a number value and ``obj`` an object or unit slot.
- ``{{= expr }}`` inserts a computed number. ``expr`` is written in the LaTeX subset
  the answer checker reads (``a + b``, ``a - b``, ``a \cdot b``, ``\frac{a}{b}``,
  ``(a + b) / 2`` ...). Each name in it is replaced by its value and the result is
  parsed by the engine's own parser (``checker.latex``) and evaluated exactly by
  ``checker.sympy_bridge``. Nothing is ever handed to ``sympify``. A name is a whole
  word, so a product is ``a \cdot b``, never ``ab``.
- ``\(`` and ``\)`` wrap a math part. Everything else is a text part. Inside a math
  part, braces that are not a slot are ordinary LaTeX braces (``x^{2}``); in text a
  lone ``{`` or ``}`` is an error, so an unfilled slot can never reach a learner.
- A slot is replaced by the bare value, braces and all, so a value used as a LaTeX
  argument keeps its own braces: ``\frac{{a}}{{b}}``, ``x^{{n}}``. Writing
  ``\frac{a}{b}`` would turn ``12`` and ``5`` into ``\frac125``, so a math slot
  directly after ``\frac``, ``\dfrac``, ``\sqrt``, ``^``, ``_`` or ``}`` is an error.

Number formatting: an integer is written in plain digits (``-3`` for a negative). A
computed value that is not an integer is written as ``\frac{p}{q}`` and is only allowed
inside a math part; a fraction in a text part, a non-rational result (a root, pi), or a
word inside a math part is an error. Any name without a value is an error.

Rendering is pure: the same template and values always give the same prompt. Slot
filling, which needs a seeded random choice, lives with word problems.
"""

import re
from collections.abc import Mapping
from dataclasses import dataclass
from functools import lru_cache
from typing import Protocol

import sympy

from mathquest.engine.checker.latex import Unreadable, parse
from mathquest.engine.checker.sympy_bridge import to_sympy
from mathquest.engine.types import MathPart, Prompt, PromptPart, TextPart


class TemplateError(ValueError):
    """A template is malformed, or names a value it was not given."""


class Countable(Protocol):
    """An object or unit slot: singular and plural words, and an optional article."""

    @property
    def one(self) -> str: ...

    @property
    def many(self) -> str: ...

    @property
    def article(self) -> str | None: ...


# A vowel letter that sounds like a consonant ("a unicorn"), and the reverse ("an hour").
_A_BEFORE = ("uni", "use", "usu", "uten", "eu", "ewe", "one", "once", "ukulele")
_AN_BEFORE = ("hour", "honest", "honor", "heir")


def article(word: str) -> str:
    """ "a" or "an" for ``word`` by its first sound, from its spelling."""
    lower = word.lower()
    if lower.startswith(_AN_BEFORE):
        return "an"
    if lower.startswith(_A_BEFORE):
        return "a"
    return "an" if lower[:1] in ("a", "e", "i", "o", "u") else "a"


type Value = int | str | Countable


@dataclass(frozen=True)
class _Lit:
    text: str


@dataclass(frozen=True)
class _Slot:
    name: str
    form: str = ""
    """"" for the plain value, "one" for a singular, "a" for a singular with article."""
    count: str | None = None
    """For ``{n obj}``: the number value that ``name`` agrees with."""


@dataclass(frozen=True)
class _Calc:
    source: str


type _Piece = _Lit | _Slot | _Calc


@dataclass(frozen=True)
class _Run:
    math: bool
    pieces: tuple[_Piece, ...]


_TOKEN = re.compile(
    r"\{\{=(?P<calc>.*?)\}\}"
    r"|\{(?:(?P<count>[A-Za-z_][A-Za-z0-9_]*) )?(?P<name>[A-Za-z_][A-Za-z0-9_]*)"
    r"(?:\.(?P<form>one|a))?\}"
    r"|(?P<open>\\\()|(?P<close>\\\))|(?P<brace>[{}])",
    re.DOTALL,
)
_ARGUMENT_BEFORE = (r"\frac", r"\dfrac", r"\sqrt", "^", "_", "}")
_WORD = re.compile(r"\\[A-Za-z]+|[A-Za-z_][A-Za-z0-9_]*")


def _names_in(source: str) -> tuple[str, ...]:
    return tuple(m.group() for m in _WORD.finditer(source) if not m.group().startswith("\\"))


def _substitute(source: str, numbers: Mapping[str, int]) -> str:
    def one(match: re.Match[str]) -> str:
        word = match.group()
        if word.startswith("\\"):
            return word
        if word not in numbers:
            raise TemplateError(f"unknown name in computed value: {word}")
        return f"({numbers[word]})"

    return _WORD.sub(one, source)


def evaluate(source: str, numbers: Mapping[str, int]) -> sympy.Expr:
    """The exact value of expression ``source`` with each name replaced by its number."""
    try:
        value = to_sympy(parse(_substitute(source, numbers)))
    except Unreadable as err:
        raise TemplateError(f"cannot compute {source.strip()!r}: {err}") from None
    if not isinstance(value, sympy.Expr) or isinstance(value, sympy.Equality):
        raise TemplateError(f"{source.strip()!r} is not a number")
    return value


def expression_names(source: str) -> frozenset[str]:
    """Every value name used in expression ``source`` (LaTeX commands are not names)."""
    return frozenset(_names_in(source))


def check_expression(source: str) -> str:
    """Raise ``TemplateError`` unless ``source`` is an expression the parser reads."""
    if not source.strip():
        raise TemplateError("empty computed value")
    try:
        parse(_substitute(source, dict.fromkeys(_names_in(source), 1)))
    except Unreadable as err:
        raise TemplateError(f"cannot read {source.strip()!r}: {err}") from None
    return source


@lru_cache(maxsize=4096)
def _parse(template: str) -> tuple[_Run, ...]:
    runs: list[_Run] = []
    pieces: list[_Piece] = []
    math = False
    pos = 0

    def flush() -> None:
        nonlocal pieces
        if pieces or math:
            runs.append(_Run(math, tuple(pieces)))
        pieces = []

    for match in _TOKEN.finditer(template):
        if match.start() > pos:
            pieces.append(_Lit(template[pos : match.start()]))
        pos = match.end()
        if match.group("open"):
            if math:
                raise TemplateError(r"math part opened twice (\( inside \( ... \))")
            flush()
            math = True
        elif match.group("close"):
            if not math:
                raise TemplateError(r"\) without a matching \(")
            flush()
            math = False
        elif match.group("brace"):
            if not math:
                raise TemplateError(f"stray {match.group('brace')!r} in text")
            pieces.append(_Lit(match.group("brace")))
        elif match.group("name"):
            name = match.group("name")
            before = "".join(p.text for p in pieces if isinstance(p, _Lit)).rstrip()
            if math and before.endswith(_ARGUMENT_BEFORE):
                raise TemplateError(f"write {{{{{name}}}}} to use {name} as a LaTeX argument")
            count, form = match.group("count"), match.group("form") or ""
            if count is not None and form:
                raise TemplateError(f"{{{count} {name}}} picks the form itself; drop .{form}")
            if count is not None and math:
                raise TemplateError(f"words cannot go in a math part: {count} {name}")
            pieces.append(_Slot(name, form, count))
        else:
            pieces.append(_Calc(check_expression(match.group("calc"))))
    if math:
        raise TemplateError(r"math part opened with \( but never closed")
    if pos < len(template):
        pieces.append(_Lit(template[pos:]))
    flush()
    return tuple(runs)


def check_template(template: str) -> str:
    """Raise ``TemplateError`` unless ``template`` is well formed. Returns it unchanged."""
    _parse(template)
    return template


def names(template: str) -> frozenset[str]:
    """Every value name a template uses, in slots and in computed values."""
    found: set[str] = set()
    for run in _parse(template):
        for piece in run.pieces:
            if isinstance(piece, _Slot):
                found.add(piece.name)
                if piece.count is not None:
                    found.add(piece.count)
            elif isinstance(piece, _Calc):
                found.update(_names_in(piece.source))
    return frozenset(found)


def format_number(value: sympy.Expr, *, math: bool) -> str:
    """Integers as digits; other rationals as ``\\frac{p}{q}``, only inside math."""
    if not isinstance(value, sympy.Rational):
        raise TemplateError(f"computed value {value} is not a whole number or fraction")
    if value.is_integer:
        return str(int(value))
    if not math:
        raise TemplateError(f"the fraction {value} must be inside a math part")
    sign = "-" if value < 0 else ""
    return rf"{sign}\frac{{{abs(int(value.p))}}}{{{int(value.q)}}}"


def _numbers(values: Mapping[str, Value]) -> dict[str, int]:
    return {k: v for k, v in values.items() if isinstance(v, int) and not isinstance(v, bool)}


def _fill(piece: _Piece, values: Mapping[str, Value], math: bool) -> str:
    if isinstance(piece, _Lit):
        return piece.text
    if isinstance(piece, _Calc):
        return format_number(evaluate(piece.source, _numbers(values)), math=math)
    if piece.name not in values:
        raise TemplateError(f"unknown name: {piece.name}")
    value = values[piece.name]
    if piece.count is not None:
        return _counted(piece, values)
    if isinstance(value, int):
        if piece.form:
            raise TemplateError(f"{piece.name} is a number; .{piece.form} is for objects and units")
        return str(value)
    if math:
        raise TemplateError(f"words cannot go in a math part: {piece.name}")
    if isinstance(value, str):
        if piece.form:
            raise TemplateError(f"{piece.name} is a word; .{piece.form} is for objects and units")
        return value
    if piece.form == "one":
        return value.one
    if piece.form == "a":
        return f"{value.article or article(value.one)} {value.one}"
    return value.many


def _counted(piece: _Slot, values: Mapping[str, Value]) -> str:
    assert piece.count is not None
    if piece.count not in values:
        raise TemplateError(f"unknown name: {piece.count}")
    number, noun = values[piece.count], values[piece.name]
    if not isinstance(number, int):
        raise TemplateError(f"{piece.count} is not a number, so it cannot count {piece.name}")
    if isinstance(noun, (int, str)):
        raise TemplateError(f"{piece.name} is not an object or unit, so it cannot be counted")
    return f"{number} {noun.one if number == 1 else noun.many}"


def render(template: str, values: Mapping[str, Value]) -> Prompt:
    """Render ``template`` with ``values`` into prompt parts."""
    parts: list[PromptPart] = []
    for run in _parse(template):
        filled = "".join(_fill(piece, values, run.math) for piece in run.pieces)
        if run.math:
            latex = filled.strip()
            if not latex:
                raise TemplateError("empty math part")
            if r"\text" in latex:
                raise TemplateError(r"words belong in text, not \text in a math part")
            parts.append(MathPart(latex))
        elif filled:
            parts.append(TextPart(filled))
    return tuple(parts)


def plain(prompt: Prompt) -> str:
    """A prompt flattened to one string (text as is, math as its LaTeX), for checks."""
    return "".join(p.text if isinstance(p, TextPart) else p.latex for p in prompt)
