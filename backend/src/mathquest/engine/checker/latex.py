"""Unevaluated LaTeX parser for kid answers.

Turns the LaTeX a MathLive editor emits into a tree that keeps the written form
(``6/8`` stays distinct from ``3/4``, ``1\\frac{1}{2}`` is a mixed number), so
later code can check both value and form. Nothing is evaluated here, and this
module imports no algebra library.

Supported: digits, decimals (``3.25``; ``.5`` reads as ``0.5``), single-letter
variables, ``+ - =``, parentheses (also ``\\left( \\right)``),
``\\cdot \\times \\div /``, ``^{...}`` and a single character ``^d``, ``\\frac``,
``\\dfrac``, ``\\sqrt``, ``\\sqrt[n]{x}``, ``\\pi``, the unicode minus, whitespace and
the ``\\,`` and ``\\ `` spacing commands.
``\\frac`` and ``\\sqrt`` arguments may be braced or a single token (one digit,
letter or ``\\pi``), so ``\\frac12`` and ``\\sqrt2`` work.
Anything else raises ``Unreadable``.

Rules worth knowing:
- Precedence, loosest to tightest: ``=``, ``+ -``, multiplication and division
  (explicit operators and juxtaposition, left associative), unary minus, ``^``.
  So ``-2^2`` is ``Neg(Pow(2, 2))``. A binary minus negates the whole following
  term: ``a-b\\cdot c`` is ``Add(a, Neg(Mul(b, c)))``.
- Juxtaposition is implicit multiplication, including ``xy``.
- ``Mixed`` is produced only for an integer literal directly followed by a
  ``\\frac`` whose numerator and denominator are both number literals, and only
  where an operand begins (start of a term or right after an explicit
  operator). ``2\\frac{x}{3}`` is implicit multiplication; ``x2\\frac{1}{2}``
  and anything inside an exponent are not mixed numbers.
- An unbraced exponent is exactly one digit, letter or ``\\pi``; ``x^23`` is
  rejected as ambiguous.
- Limits: 200 characters, nesting depth 20, absolute literal exponent 100.
"""

import re
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Literal

MAX_LENGTH = 200
MAX_DEPTH = 20
MAX_EXPONENT = Decimal(100)


class Unreadable(Exception):
    """The input is outside the supported LaTeX subset."""


@dataclass(frozen=True)
class Num:
    value: str


@dataclass(frozen=True)
class Var:
    name: str


@dataclass(frozen=True)
class Const:
    name: Literal["pi"]


@dataclass(frozen=True)
class Neg:
    x: "Node"


@dataclass(frozen=True)
class Add:
    terms: tuple["Node", ...]


@dataclass(frozen=True)
class Mul:
    factors: tuple["Node", ...]
    implicit: bool


@dataclass(frozen=True)
class Div:
    n: "Node"
    d: "Node"
    kind: Literal["frac", "slash", "div"]


@dataclass(frozen=True)
class Pow:
    base: "Node"
    exp: "Node"


@dataclass(frozen=True)
class Sqrt:
    x: "Node"
    index: "Node | None"


@dataclass(frozen=True)
class Mixed:
    whole: Num
    frac: Div


@dataclass(frozen=True)
class Eq:
    lhs: "Node"
    rhs: "Node"


@dataclass(frozen=True)
class Group:
    x: "Node"


type Node = Num | Var | Const | Neg | Add | Mul | Div | Pow | Sqrt | Mixed | Eq | Group

# Token kinds: NUM, VAR, PI, FRAC, SQRT, CDOT (\cdot, \times), DIV (\div), and
# the literal characters + - = / ^ ( ) { } [ ].
_NUM_RE = re.compile(r"\d+(?:\.\d+)?|\.\d+")
_CMD_RE = re.compile(r"\\([A-Za-z]+)")
_SINGLE = set("+-=/^(){}[]")


@dataclass(frozen=True)
class _Tok:
    kind: str
    text: str


def _tokenize(src: str) -> list[_Tok]:
    toks: list[_Tok] = []
    i = 0
    n = len(src)
    while i < n:
        c = src[i]
        if c.isspace():
            i += 1
        elif c == "\N{MINUS SIGN}":
            toks.append(_Tok("-", c))
            i += 1
        elif c in _SINGLE:
            toks.append(_Tok(c, c))
            i += 1
        elif (c.isascii() and c.isdigit()) or (c == "." and src[i + 1 : i + 2].isdigit()):
            m = _NUM_RE.match(src, i)
            assert m is not None
            text = m.group()
            # A decimal typed point first (".5") is the same number as "0.5".
            toks.append(_Tok("NUM", "0" + text if text.startswith(".") else text))
            i = m.end()
        elif c.isascii() and c.isalpha():
            toks.append(_Tok("VAR", c))
            i += 1
        elif c == "\\":
            if src[i + 1 : i + 2] in (",", " "):
                i += 2
                continue
            m = _CMD_RE.match(src, i)
            if m is None:
                raise Unreadable("bad command")
            i = m.end()
            name = m.group(1)
            if name in ("frac", "dfrac"):
                toks.append(_Tok("FRAC", name))
            elif name == "sqrt":
                toks.append(_Tok("SQRT", name))
            elif name == "pi":
                toks.append(_Tok("PI", name))
            elif name in ("cdot", "times"):
                toks.append(_Tok("CDOT", name))
            elif name == "div":
                toks.append(_Tok("DIV", name))
            elif name in ("left", "right"):
                want = "(" if name == "left" else ")"
                j = i
                while j < n and src[j].isspace():
                    j += 1
                if src[j : j + 1] != want:
                    raise Unreadable("unsupported delimiter")
                toks.append(_Tok(want, want))
                i = j + 1
            else:
                raise Unreadable("unsupported command")
        else:
            raise Unreadable("unsupported character")
    return toks


_OPERAND_START = {"NUM", "VAR", "PI", "FRAC", "SQRT", "("}


class _Parser:
    def __init__(self, toks: list[_Tok]) -> None:
        self.toks = toks
        self.pos = 0
        self.depth = 0
        self.in_exponent = 0

    def peek(self) -> str | None:
        return self.toks[self.pos].kind if self.pos < len(self.toks) else None

    def next(self) -> _Tok:
        if self.pos >= len(self.toks):
            raise Unreadable("unexpected end")
        tok = self.toks[self.pos]
        self.pos += 1
        return tok

    def expect(self, kind: str) -> None:
        if self.next().kind != kind:
            raise Unreadable(f"expected {kind}")

    def enter(self) -> None:
        self.depth += 1
        if self.depth > MAX_DEPTH:
            raise Unreadable("nested too deeply")

    def leave(self) -> None:
        self.depth -= 1

    def parse_all(self) -> Node:
        node = self.parse_eq()
        if self.pos != len(self.toks):
            raise Unreadable("trailing input")
        return node

    def parse_eq(self) -> Node:
        lhs = self.parse_add()
        if self.peek() == "=":
            self.next()
            return Eq(lhs, self.parse_add())
        return lhs

    def parse_add(self) -> Node:
        terms = [self.parse_term()]
        while self.peek() in ("+", "-"):
            if self.next().kind == "+":
                terms.append(self.parse_term())
            else:
                terms.append(Neg(self.parse_term()))
        return terms[0] if len(terms) == 1 else Add(tuple(terms))

    def parse_term(self) -> Node:
        left = self.parse_unary(allow_mixed=True)
        while True:
            kind = self.peek()
            if kind == "CDOT":
                self.next()
                left = self._mul(left, self.parse_unary(allow_mixed=True), implicit=False)
            elif kind == "DIV":
                self.next()
                left = Div(left, self.parse_unary(allow_mixed=True), "div")
            elif kind == "/":
                self.next()
                left = Div(left, self.parse_unary(allow_mixed=True), "slash")
            elif kind in _OPERAND_START:
                if kind == "NUM" and self.toks[self.pos - 1].kind == "NUM":
                    raise Unreadable("adjacent numbers")
                left = self._mul(left, self.parse_power(allow_mixed=False), implicit=True)
            else:
                return left

    @staticmethod
    def _mul(left: Node, right: Node, *, implicit: bool) -> Node:
        if isinstance(left, Mul) and left.implicit == implicit:
            return Mul((*left.factors, right), implicit)
        return Mul((left, right), implicit)

    def parse_unary(self, *, allow_mixed: bool) -> Node:
        if self.peek() == "-":
            self.next()
            self.enter()
            try:
                return Neg(self.parse_unary(allow_mixed=allow_mixed))
            finally:
                self.leave()
        return self.parse_power(allow_mixed=allow_mixed)

    def parse_power(self, *, allow_mixed: bool) -> Node:
        tok = self.peek()
        if (
            allow_mixed
            and not self.in_exponent
            and tok == "NUM"
            and self.toks[self.pos + 1 : self.pos + 2]
        ):
            mixed = self.try_mixed()
            if mixed is not None:
                return mixed
        base = self.parse_atom()
        if self.peek() != "^":
            return base
        self.next()
        exp = self.parse_exponent()
        _check_exponent(exp)
        return Pow(base, exp)

    def try_mixed(self) -> Mixed | None:
        whole = self.toks[self.pos]
        if "." in whole.text or not self.frac_has_num_args(self.pos + 1):
            return None
        self.pos += 1
        frac = self.parse_frac()
        assert isinstance(frac.n, Num) and isinstance(frac.d, Num)
        return Mixed(Num(whole.text), frac)

    def frac_has_num_args(self, i: int) -> bool:
        """Token lookahead (no parsing): is a FRAC at ``i`` followed by two number arguments?"""
        if self.kind_at(i) != "FRAC":
            return False
        i += 1
        first = self.toks[i] if i < len(self.toks) else None
        if first is None:
            return False
        if first.kind == "NUM":
            if "." in first.text:
                return False
            if len(first.text) >= 2:
                return True
            i += 1
        elif first.kind == "{" and self.kind_at(i + 1) == "NUM" and self.kind_at(i + 2) == "}":
            i += 3
        else:
            return False
        second = self.toks[i] if i < len(self.toks) else None
        if second is None:
            return False
        if second.kind == "NUM":
            return "." not in second.text
        return second.kind == "{" and self.kind_at(i + 1) == "NUM" and self.kind_at(i + 2) == "}"

    def kind_at(self, i: int) -> str | None:
        return self.toks[i].kind if i < len(self.toks) else None

    def parse_exponent(self) -> Node:
        self.in_exponent += 1
        try:
            return self._exponent_body()
        finally:
            self.in_exponent -= 1

    def _exponent_body(self) -> Node:
        if self.peek() == "{":
            return self.parse_braced()
        tok = self.next()
        if tok.kind == "NUM" and len(tok.text) == 1:
            return Num(tok.text)
        if tok.kind == "VAR":
            return Var(tok.text)
        if tok.kind == "PI":
            return Const("pi")
        raise Unreadable("bad exponent")

    def parse_braced(self) -> Node:
        self.expect("{")
        self.enter()
        try:
            node = self.parse_add()
        finally:
            self.leave()
        self.expect("}")
        return node

    def parse_arg(self) -> Node:
        """A braced group or exactly one token (a digit, letter or command)."""
        if self.peek() == "{":
            return self.parse_braced()
        tok = self.next()
        if tok.kind == "NUM":
            if len(tok.text) > 1:
                if "." in tok.text:
                    raise Unreadable("bad argument")
                self.toks[self.pos - 1 : self.pos] = [
                    _Tok("NUM", tok.text[0]),
                    _Tok("NUM", tok.text[1:]),
                ]
                return Num(tok.text[0])
            return Num(tok.text)
        if tok.kind == "VAR":
            return Var(tok.text)
        if tok.kind == "PI":
            return Const("pi")
        raise Unreadable("bad argument")

    def parse_frac(self) -> Div:
        self.expect("FRAC")
        n = self.parse_arg()
        d = self.parse_arg()
        return Div(n, d, "frac")

    def parse_atom(self) -> Node:
        tok = self.next()
        if tok.kind == "NUM":
            return Num(tok.text)
        if tok.kind == "VAR":
            return Var(tok.text)
        if tok.kind == "PI":
            return Const("pi")
        if tok.kind == "(":
            self.enter()
            try:
                inner = self.parse_add()
            finally:
                self.leave()
            self.expect(")")
            return Group(inner)
        if tok.kind == "FRAC":
            self.pos -= 1
            return self.parse_frac()
        if tok.kind == "SQRT":
            index: Node | None = None
            if self.peek() == "[":
                self.next()
                self.enter()
                try:
                    index = self.parse_add()
                finally:
                    self.leave()
                self.expect("]")
            return Sqrt(self.parse_arg(), index)
        raise Unreadable("unexpected token")


def _check_exponent(exp: Node) -> None:
    inner = exp.x if isinstance(exp, Neg) else exp
    if isinstance(inner, Num):
        try:
            big = abs(Decimal(inner.value)) > MAX_EXPONENT
        except InvalidOperation as err:
            raise Unreadable("bad number") from err
        if big:
            raise Unreadable("exponent too large")


def parse(latex: str) -> Node:
    """Parse kid-entered LaTeX into an unevaluated tree or raise ``Unreadable``."""
    if len(latex) > MAX_LENGTH:
        raise Unreadable("too long")
    toks = _tokenize(latex)
    if not toks:
        raise Unreadable("empty")
    try:
        return _Parser(toks).parse_all()
    except RecursionError as err:
        raise Unreadable("nested too deeply") from err
