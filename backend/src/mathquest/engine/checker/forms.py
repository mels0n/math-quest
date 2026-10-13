# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false
"""Answer-form rules: does the written form of an answer satisfy what was asked.

These rules read the parsed tree (the form the kid wrote), not just its value.
A leading minus is sign handling: ``Neg`` around a number, fraction, mixed
number or a product factor never changes the form.
"""

import math

import sympy

from mathquest.engine.checker.latex import (
    Add,
    Const,
    Div,
    Eq,
    Group,
    Mixed,
    Mul,
    Neg,
    Node,
    Num,
    Pow,
    Sqrt,
    Var,
)
from mathquest.engine.checker.sympy_bridge import to_sympy
from mathquest.engine.types import AnswerForm

_TRIAL_LIMIT = 10_000


def satisfies_form(node: Node, value: sympy.Expr | sympy.Equality, form: AnswerForm) -> bool:
    """True when ``node`` is written in the requested ``form``.

    For an equation the form applies to the side opposite a lone variable
    (``x=7`` is judged as ``7``); any other equation fails every form but ANY.
    """
    if form is AnswerForm.ANY:
        return True
    if isinstance(node, Eq):
        side = _solved_side(node)
        return side is not None and satisfies_form(side, to_sympy(side), form)
    if isinstance(value, sympy.Equality):
        return False
    match form:
        case AnswerForm.INTEGER:
            return _is_integer(_unneg(node))
        case AnswerForm.LOWEST_TERMS:
            return _lowest_terms(node)
        case AnswerForm.MIXED_NUMBER:
            return _mixed_number(node, value)
        case AnswerForm.SIMPLIFIED_RADICAL:
            return _simplified_radical(node)
        case AnswerForm.FACTORED:
            return _factored(node)
        case AnswerForm.EXPANDED:
            return not _has_unexpanded_product(node)
    return False


def _solved_side(eq: Eq) -> Node | None:
    if isinstance(eq.lhs, Var):
        return eq.rhs
    if isinstance(eq.rhs, Var):
        return eq.lhs
    return None


def _unneg(node: Node) -> Node:
    while isinstance(node, Neg):
        node = node.x
    return node


def _int_value(node: Node) -> int | None:
    """Value of an integer literal, allowing a leading minus; otherwise None."""
    inner = _unneg(node)
    if isinstance(inner, Num) and "." not in inner.value:
        value = int(inner.value)
        return -value if (_neg_count(node) % 2) else value
    return None


def _neg_count(node: Node) -> int:
    count = 0
    while isinstance(node, Neg):
        count += 1
        node = node.x
    return count


def _is_integer(node: Node) -> bool:
    return isinstance(node, Num) and "." not in node.value


def _proper_lowest_fraction(frac: Div) -> bool:
    n, d = _int_value(frac.n), _int_value(frac.d)
    return n is not None and d is not None and 0 < n < d and math.gcd(n, d) == 1


def _lowest_fraction(frac: Div) -> bool:
    n, d = _int_value(frac.n), _int_value(frac.d)
    return n is not None and d is not None and d > 1 and math.gcd(n, d) == 1


def _lowest_terms(node: Node) -> bool:
    inner = _unneg(node)
    if _is_integer(inner):
        return True
    if isinstance(inner, Div):
        return _lowest_fraction(inner)
    if isinstance(inner, Mixed):
        return _is_integer(inner.whole) and _proper_lowest_fraction(inner.frac)
    return False


def _mixed_number(node: Node, value: sympy.Expr) -> bool:
    inner = _unneg(node)
    if not isinstance(value, sympy.Rational):
        return False
    if value.is_integer:
        return _is_integer(inner)
    if abs(value) < 1:
        return isinstance(inner, Div) and _lowest_fraction(inner)
    return (
        isinstance(inner, Mixed)
        and _is_integer(inner.whole)
        and _proper_lowest_fraction(inner.frac)
    )


def _has_var(node: Node) -> bool:
    match node:
        case Var():
            return True
        case Neg(x) | Group(x):
            return _has_var(x)
        case Add(items) | Mul(items, _):
            return any(_has_var(i) for i in items)
        case Div(n, d, _):
            return _has_var(n) or _has_var(d)
        case Pow(base, exp):
            return _has_var(base) or _has_var(exp)
        case Sqrt(x, index):
            return _has_var(x) or (index is not None and _has_var(index))
        case Mixed(whole, frac):
            return _has_var(whole) or _has_var(frac)
        case Eq(lhs, rhs):
            return _has_var(lhs) or _has_var(rhs)
        case _:
            return False


def _has_sqrt(node: Node) -> bool:
    match node:
        case Sqrt():
            return True
        case Neg(x) | Group(x):
            return _has_sqrt(x)
        case Add(items) | Mul(items, _):
            return any(_has_sqrt(i) for i in items)
        case Div(n, d, _):
            return _has_sqrt(n) or _has_sqrt(d)
        case Pow(base, exp):
            return _has_sqrt(base) or _has_sqrt(exp)
        case Mixed(whole, frac):
            return _has_sqrt(whole) or _has_sqrt(frac)
        case _:
            return False


def _has_power_of_n_factor(n: int, index: int) -> bool:
    """True when some prime power ``p**index`` divides ``n``.

    Trial division is bounded; a large prime factor beyond the bound is not
    inspected, which only matters for radicands far outside the problem range.
    """
    if n < 2:
        return False
    root = round(n ** (1 / index))
    for candidate in (root - 1, root, root + 1):
        if candidate > 1 and candidate**index == n:
            return True
    p = 2
    while p <= _TRIAL_LIMIT and p**index <= n:
        if n % (p**index) == 0:
            return True
        p += 1
    return False


def _radicand_simplified(node: Node, index: int) -> bool:
    match node:
        case Num(value):
            if "." in value:
                return False
            n = int(value)
            return n >= 2 and not _has_power_of_n_factor(n, index)
        case Var():
            return True
        case Mul(factors, _):
            numbers: list[int] = []
            for f in factors:
                if isinstance(f, Num):
                    if "." in f.value:
                        return False
                    numbers.append(int(f.value))
                elif not _radicand_simplified(f, index):
                    return False
            return not numbers or not _has_power_of_n_factor(math.prod(numbers), index)
        case Add(terms):
            return _has_var(node) and all(_term_simplified(t, index) for t in terms)
        case Pow(Var(), Num(e)):
            return "." not in e and int(e) < index
        case _:
            return False


def _term_simplified(term: Node, index: int) -> bool:
    return _radicand_simplified(term, index) if _has_var(term) else _is_plain(term)


def _is_plain(node: Node) -> bool:
    return isinstance(_unneg(node), Num | Const)


def _simplified_radical(node: Node) -> bool:
    match node:
        case Sqrt(x, index):
            n = 2
            if index is not None:
                if not (
                    isinstance(index, Num) and "." not in index.value and int(index.value) >= 2
                ):
                    return False
                n = int(index.value)
            return _radicand_simplified(x, n)
        case Div(n, d, _):
            return not _has_sqrt(d) and _simplified_radical(n) and _simplified_radical(d)
        case Pow(base, exp):
            return (
                not _has_sqrt(exp)
                and not isinstance(_unneg(exp), Div)
                and not (isinstance(exp, Num) and "." in exp.value)
                and _simplified_radical(base)
            )
        case Neg(x) | Group(x):
            return _simplified_radical(x)
        case Add(items) | Mul(items, _):
            return all(_simplified_radical(i) for i in items)
        case Mixed(whole, frac):
            return _simplified_radical(whole) and _simplified_radical(frac)
        case _:
            return True


def _factor_ok(node: Node) -> bool:
    inner = _unneg(node)
    match inner:
        case Num() | Var():
            return True
        case Group(x):
            return _poly_ok(x)
        case Pow(Group(x), Num(e)) if "." not in e:
            return _poly_ok(x)
        case Pow(Var(), Num(e)) if "." not in e:
            return True
        case _:
            return False


def _poly_ok(node: Node) -> bool:
    """Degree at most 1, or irreducible over the rationals."""
    expr = to_sympy(node)
    if isinstance(expr, sympy.Equality):
        return False
    symbols = sorted(expr.free_symbols, key=str)
    if not symbols:
        return True
    try:
        poly = sympy.Poly(expr, *symbols)
    except sympy.PolynomialError:
        return False
    if poly.total_degree() <= 1:
        return True
    factors = sympy.factor_list(expr)[1]
    return len(factors) == 1 and factors[0][1] == 1


def _factored(node: Node) -> bool:
    if isinstance(node, Pow):
        return isinstance(node.base, Group) and _factor_ok(node)
    return isinstance(node, Mul) and all(_factor_ok(f) for f in node.factors)


def _is_group(node: Node) -> bool:
    inner = _unneg(node)
    return isinstance(inner, Group) or (isinstance(inner, Pow) and isinstance(inner.base, Group))


def _has_unexpanded_product(node: Node) -> bool:
    match node:
        case Mul(factors, _):
            for i, f in enumerate(factors):
                if _is_group(f) and any(_has_var(g) for j, g in enumerate(factors) if j != i):
                    return True
            return any(_has_unexpanded_product(f) for f in factors)
        case Pow(Group(x), exp):
            if _has_var(x) and not (isinstance(exp, Num) and exp.value == "1"):
                return True
            return _has_unexpanded_product(x) or _has_unexpanded_product(exp)
        case Neg(x) | Group(x):
            return _has_unexpanded_product(x)
        case Add(items):
            return any(_has_unexpanded_product(i) for i in items)
        case Div(n, d, _):
            return _has_unexpanded_product(n) or _has_unexpanded_product(d)
        case Pow(base, exp):
            return _has_unexpanded_product(base) or _has_unexpanded_product(exp)
        case Sqrt(x, index):
            return _has_unexpanded_product(x) or (
                index is not None and _has_unexpanded_product(index)
            )
        case _:
            return False
