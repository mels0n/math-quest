# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false
"""Decide whether a kid's LaTeX answer is correct, in the wrong form, wrong or unreadable."""

from dataclasses import dataclass
from enum import StrEnum
from typing import cast

import sympy

from mathquest.engine.checker.forms import satisfies_form
from mathquest.engine.checker.latex import Unreadable, parse
from mathquest.engine.checker.sympy_bridge import to_sympy
from mathquest.engine.types import Problem


class Verdict(StrEnum):
    CORRECT = "correct"
    INCORRECT = "incorrect"
    WRONG_FORM = "wrong_form"
    UNREADABLE = "unreadable"


@dataclass(frozen=True)
class CheckResult:
    verdict: Verdict
    misconception: str | None = None


MAX_SOLVE_DEGREE = 4


def _rational_only(expr: sympy.Expr) -> bool:
    """True for rational functions with rational coefficients (no radicals, pi, functions)."""
    if not all(a.is_Rational or a.is_Symbol for a in expr.atoms()):
        return False
    return all(p.exp.is_Integer for p in expr.atoms(sympy.Pow))


def _is_zero(difference: sympy.Expr) -> bool:
    """Exact zero test. For rational functions over Q, cancellation is decisive."""
    if difference == 0:
        return True
    if _rational_only(difference):
        return bool(sympy.cancel(difference) == 0)
    if sympy.expand(difference) == 0:
        return True
    return bool(sympy.simplify(difference) == 0)


def _expr_equal(a: sympy.Basic, b: sympy.Basic) -> bool:
    return a == b or _is_zero(cast(sympy.Expr, a) - cast(sympy.Expr, b))


def _difference(eq: sympy.Equality) -> sympy.Expr:
    return sympy.Add(cast(sympy.Expr, eq.lhs), sympy.Mul(-1, cast(sympy.Expr, eq.rhs)))


def _same_roots(found: sympy.Set, expected: sympy.FiniteSet) -> bool:
    if not isinstance(found, sympy.FiniteSet) or len(found) != len(expected):
        return False
    return all(any(_expr_equal(f, e) for f in found) for e in expected) and all(
        any(_expr_equal(f, e) for e in expected) for f in found
    )


def _solution_set_matches(
    student: sympy.Equality, symbol: sympy.Symbol, expected: sympy.Set
) -> bool:
    """Whether the student's equation has exactly the expected solutions in ``symbol``.

    Substitution proves every expected value solves it; the solve (polynomials
    of bounded degree only) proves there are no others.
    """
    if not isinstance(expected, sympy.FiniteSet):
        return False
    diff = _difference(student)
    if not all(_is_zero(cast(sympy.Expr, diff.subs(symbol, e))) for e in expected):
        return False
    if diff.free_symbols != {symbol}:
        return False
    try:
        poly = sympy.Poly(diff, symbol)
    except sympy.PolynomialError as err:
        raise Unreadable("unsupported equation") from err
    degree = poly.degree()
    if degree < 1:
        return False
    if degree == len(expected):
        return True
    if degree > MAX_SOLVE_DEGREE:
        raise Unreadable("equation too hard")
    return _same_roots(sympy.solveset(diff, symbol, domain=sympy.S.Complexes), expected)


def _constant_multiple(student: sympy.Equality, answer: sympy.Equality) -> bool:
    a, s = _difference(answer), _difference(student)
    if a == 0 or not (_rational_only(a) and _rational_only(s)):
        return False
    ratio = sympy.cancel(s / a)
    return ratio.is_number and ratio != 0


def _equation_equivalent(student: sympy.Expr | sympy.Equality, answer: sympy.Equality) -> bool:
    symbols = sorted(answer.free_symbols, key=str)
    expected: sympy.Set | None = None
    if len(symbols) == 1:
        expected = sympy.solveset(_difference(answer), symbols[0], domain=sympy.S.Complexes)
    if isinstance(expected, sympy.FiniteSet):
        symbol = cast(sympy.Symbol, symbols[0])
        if isinstance(student, sympy.Equality):
            return _solution_set_matches(student, symbol, expected)
        return len(expected) == 1 and _expr_equal(student, cast(sympy.Expr, next(iter(expected))))
    return isinstance(student, sympy.Equality) and _constant_multiple(student, answer)


def _equivalent(student: sympy.Expr | sympy.Equality, answer: sympy.Basic) -> bool:
    if isinstance(answer, sympy.Equality):
        return _equation_equivalent(student, answer)
    if isinstance(student, sympy.Equality) or not isinstance(answer, sympy.Expr):
        return False
    return _expr_equal(student, answer)


def check(problem: Problem, latex: str) -> CheckResult:
    """Judge ``latex`` against ``problem``. Never raises: any failure is UNREADABLE."""
    try:
        node = parse(latex)
        value = to_sympy(node)
        if _equivalent(value, problem.answer):
            if satisfies_form(node, value, problem.form):
                return CheckResult(Verdict.CORRECT)
            return CheckResult(Verdict.WRONG_FORM)
        for misconception in problem.misconceptions:
            if _equivalent(value, misconception.answer):
                return CheckResult(Verdict.INCORRECT, misconception.key)
        return CheckResult(Verdict.INCORRECT)
    except Exception:
        return CheckResult(Verdict.UNREADABLE)
