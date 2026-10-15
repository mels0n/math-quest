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
    """Whether the student's equation is the answer's scaled by a nonzero constant."""
    a, s = _difference(answer), _difference(student)
    if a == 0:
        return False
    if _expr_equal(s, a) or _expr_equal(s, -a):
        return True
    ratio = (
        sympy.cancel(s / a) if _rational_only(s) and _rational_only(a) else sympy.simplify(s / a)
    )
    if ratio.is_number:
        return bool(ratio != 0 and ratio.is_finite is not False)
    for symbol in sorted(a.free_symbols, key=str):
        scale = sympy.simplify(sympy.diff(s, symbol) / sympy.diff(a, symbol))
        if scale.is_number and scale != 0 and scale.is_finite is not False:
            return _is_zero(s - scale * a)
    return False


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


def check_choice(problem: Problem, choice: int) -> CheckResult:
    """Judge a multiple-choice answer by its index. Nothing is parsed."""
    if problem.correct_choice is None:
        return CheckResult(Verdict.UNREADABLE)
    if choice == problem.correct_choice:
        return CheckResult(Verdict.CORRECT)
    return CheckResult(Verdict.INCORRECT)


class AnswerKindError(ValueError):
    """An answer of the wrong kind for its problem; ``code`` names the problem."""

    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


def check_answer_kind(problem: Problem, latex: str | None, choice: int | None) -> None:
    """Exactly the kind of answer the problem takes: LaTeX for a typed problem, a choice
    index inside the shown choices for a multiple-choice one. Raises AnswerKindError
    ("latex_expected", "choice_expected" or "choice_out_of_range")."""
    if problem.choices is None:
        if latex is None or choice is not None:
            raise AnswerKindError("latex_expected")
        return
    if choice is None or latex is not None:
        raise AnswerKindError("choice_expected")
    if not 0 <= choice < len(problem.choices):
        raise AnswerKindError("choice_out_of_range")
