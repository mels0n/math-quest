# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false
"""Decide whether a kid's LaTeX answer is correct, in the wrong form, wrong or unreadable."""

from dataclasses import dataclass
from enum import StrEnum
from typing import cast

import sympy

from mathquest.engine.checker.forms import satisfies_form
from mathquest.engine.checker.latex import parse
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


def _is_zero(difference: sympy.Expr) -> bool:
    """Exact zero test: cheap structural checks first, then full simplification."""
    if difference == 0 or sympy.expand(difference) == 0:
        return True
    return bool(sympy.simplify(difference) == 0)


def _expr_equal(a: sympy.Expr, b: sympy.Expr) -> bool:
    return a == b or _is_zero(a - b)


def _difference(eq: sympy.Equality) -> sympy.Expr:
    return sympy.Add(cast(sympy.Expr, eq.lhs), sympy.Mul(-1, cast(sympy.Expr, eq.rhs)))


def _solutions(eq: sympy.Equality, symbol: sympy.Symbol) -> sympy.Set:
    return sympy.solveset(_difference(eq), symbol, domain=sympy.S.Complexes)


def _equation_equivalent(student: sympy.Expr | sympy.Equality, answer: sympy.Equality) -> bool:
    symbols = sorted(answer.free_symbols, key=str)
    if len(symbols) != 1:
        if not isinstance(student, sympy.Equality):
            return False
        a, s = _difference(answer), _difference(student)
        return _is_zero(s - a) or _is_zero(s + a)
    symbol = cast(sympy.Symbol, symbols[0])
    expected = _solutions(answer, symbol)
    if isinstance(student, sympy.Equality):
        return _solutions(student, symbol) == expected
    if isinstance(expected, sympy.FiniteSet) and len(expected) == 1:
        return _expr_equal(student, cast(sympy.Expr, next(iter(expected))))
    return False


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
