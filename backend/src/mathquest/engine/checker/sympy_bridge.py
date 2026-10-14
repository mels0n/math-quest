# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false
"""Evaluate a parsed answer tree with SymPy under hard size bounds.

Only trees produced by ``latex.parse`` reach this module; kid text is never
handed to SymPy directly. Evaluation is exact (decimals become rationals) and
bounded: exponents are evaluated first and rejected when large or when they
contain a power, and numeric results are rejected when their estimated digit
count is large.
"""

import math
from typing import cast

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
    Unreadable,
    Var,
)

MAX_ABS_EXPONENT = 100
MAX_ROOT_INDEX = 100
MAX_RESULT_DIGITS = 2000
MAX_EXPANDED_TERMS = 5000

_NON_FINITE = (sympy.zoo, sympy.nan, sympy.oo, -sympy.oo)


def to_sympy(node: Node) -> sympy.Expr | sympy.Equality:
    """Evaluate ``node`` exactly. Raises ``Unreadable`` for undefined or oversized values."""
    if isinstance(node, Eq):
        lhs, rhs = _expr(node.lhs), _expr(node.rhs)
        _check_expansion(lhs)
        _check_expansion(rhs)
        return cast(sympy.Equality, sympy.Eq(lhs, rhs, evaluate=False))
    result = _expr(node)
    _check_expansion(result)
    return result


def _expanded_terms(expr: sympy.Expr) -> int:
    """Upper bound on the term count of ``expr`` once multiplied out."""
    if isinstance(expr, sympy.Add):
        return sum(_expanded_terms(a) for a in expr.args)
    if isinstance(expr, sympy.Mul):
        total = 1
        for a in expr.args:
            total *= _expanded_terms(a)
            if total > MAX_EXPANDED_TERMS:
                return total
        return total
    if isinstance(expr, sympy.Pow) and expr.exp.is_Integer and expr.exp > 1:
        terms = _expanded_terms(expr.base)
        if terms == 1:
            return 1
        return math.comb(terms + int(expr.exp) - 1, int(expr.exp))
    return 1


def _check_expansion(expr: sympy.Expr) -> None:
    if _expanded_terms(expr) > MAX_EXPANDED_TERMS:
        raise Unreadable("expression too large")


def _contains_pow(node: Node) -> bool:
    match node:
        case Pow():
            return True
        case Neg(x) | Group(x):
            return _contains_pow(x)
        case Add(items) | Mul(items):
            return any(_contains_pow(i) for i in items)
        case Div(n, d, _):
            return _contains_pow(n) or _contains_pow(d)
        case Sqrt(x, index):
            return _contains_pow(x) or (index is not None and _contains_pow(index))
        case Mixed(_, frac):
            return _contains_pow(frac)
        case Eq(lhs, rhs):
            return _contains_pow(lhs) or _contains_pow(rhs)
        case _:
            return False


def _finite(value: sympy.Expr) -> sympy.Expr:
    if value.has(*_NON_FINITE):
        raise Unreadable("undefined value")
    return value


def _digits(value: sympy.Expr) -> float:
    if isinstance(value, sympy.Rational):
        return math.log10(max(abs(int(value.p)), int(value.q), 1))
    return 0.0


def _expr(node: Node) -> sympy.Expr:
    match node:
        case Num(value):
            return sympy.Rational(value)
        case Var(name):
            return sympy.Symbol(name)
        case Const():
            return sympy.pi
        case Neg(x):
            return -_expr(x)
        case Group(x):
            return _expr(x)
        case Add(terms):
            return sympy.Add(*(_expr(t) for t in terms))
        case Mul(factors, _):
            return sympy.Mul(*(_expr(f) for f in factors))
        case Div(n, d, _):
            denominator = _expr(d)
            if denominator == 0:
                raise Unreadable("division by zero")
            return _finite(_expr(n) / denominator)
        case Mixed(whole, frac):
            return _expr(whole) + _expr(frac)
        case Pow(base, exp):
            return _power(base, exp)
        case Sqrt(x, index):
            return _root(x, index)
        case Eq():
            raise Unreadable("nested equation")


def _power(base_node: Node, exp_node: Node) -> sympy.Expr:
    if _contains_pow(exp_node):
        raise Unreadable("power tower")
    exp = _expr(exp_node)
    if exp.is_number and abs(exp) > MAX_ABS_EXPONENT:
        raise Unreadable("exponent too large")
    base = _expr(base_node)
    if exp.is_number and _digits(base) * float(abs(exp)) > MAX_RESULT_DIGITS:
        raise Unreadable("result too large")
    return _finite(base**exp)


def _root(radicand_node: Node, index_node: Node | None) -> sympy.Expr:
    radicand = _expr(radicand_node)
    if index_node is None:
        return _finite(sympy.sqrt(radicand))
    index = _expr(index_node)
    if not (isinstance(index, sympy.Integer) and 2 <= index <= MAX_ROOT_INDEX):
        raise Unreadable("bad root index")
    n = int(index)
    if radicand.is_number and radicand.is_negative and n % 2 == 1:
        return _finite(cast(sympy.Expr, -sympy.root(-radicand, n)))
    return _finite(cast(sympy.Expr, sympy.root(radicand, n)))
