# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false
import time

import pytest
import sympy

from mathquest.engine.checker.check import CheckResult, Verdict, check
from mathquest.engine.checker.latex import Unreadable, parse
from mathquest.engine.checker.sympy_bridge import to_sympy
from mathquest.engine.types import AnswerForm, Misconception, Problem

x = sympy.Symbol("x")


def make_problem(
    answer: sympy.Basic,
    form: AnswerForm = AnswerForm.ANY,
    misconceptions: tuple[Misconception, ...] = (),
) -> Problem:
    return Problem(
        skill_id="test",
        tier=1,
        seed=0,
        prompt_latex="",
        answer=answer,  # pyright: ignore[reportArgumentType]
        form=form,
        misconceptions=misconceptions,
        difficulty=0.5,
        keypad="numbers",
    )


def verdict(problem: Problem, latex: str) -> Verdict:
    return check(problem, latex).verdict


@pytest.mark.parametrize(
    "latex", [r"1\frac{1}{2}", "1.5", r"\frac{3}{2}", "3/2", r"\frac{6}{4}", r"3\div2"]
)
def test_any_form_accepts_equivalent_values(latex: str) -> None:
    assert verdict(make_problem(sympy.Rational(3, 2)), latex) is Verdict.CORRECT


@pytest.mark.parametrize(
    ("latex", "expected"),
    [
        (r"\frac{3}{4}", Verdict.CORRECT),
        (r"\frac{6}{8}", Verdict.WRONG_FORM),
        ("0.75", Verdict.WRONG_FORM),
        (r"\frac{5}{6}", Verdict.INCORRECT),
    ],
)
def test_lowest_terms(latex: str, expected: Verdict) -> None:
    problem = make_problem(sympy.Rational(3, 4), AnswerForm.LOWEST_TERMS)
    assert verdict(problem, latex) is expected


@pytest.mark.parametrize(
    ("latex", "expected"),
    [
        (r"1\frac{1}{2}", Verdict.CORRECT),
        (r"\frac{3}{2}", Verdict.WRONG_FORM),
        ("1.5", Verdict.WRONG_FORM),
        (r"1\frac{2}{4}", Verdict.WRONG_FORM),
        (r"1\frac{3}{2}", Verdict.INCORRECT),
    ],
)
def test_mixed_number(latex: str, expected: Verdict) -> None:
    problem = make_problem(sympy.Rational(3, 2), AnswerForm.MIXED_NUMBER)
    assert verdict(problem, latex) is expected


@pytest.mark.parametrize(
    ("latex", "expected"),
    [
        (r"2\sqrt{2}", Verdict.CORRECT),
        (r"\sqrt{8}", Verdict.WRONG_FORM),
        (r"\sqrt{2}", Verdict.INCORRECT),
    ],
)
def test_simplified_radical(latex: str, expected: Verdict) -> None:
    problem = make_problem(2 * sympy.sqrt(2), AnswerForm.SIMPLIFIED_RADICAL)
    assert verdict(problem, latex) is expected


@pytest.mark.parametrize(
    ("latex", "expected"),
    [
        ("(x+3)(x-2)", Verdict.CORRECT),
        ("(x-2)(x+3)", Verdict.CORRECT),
        ("x^2+x-6", Verdict.WRONG_FORM),
        ("(x+3)(x+2)", Verdict.INCORRECT),
    ],
)
def test_factored(latex: str, expected: Verdict) -> None:
    problem = make_problem(x**2 + x - 6, AnswerForm.FACTORED)
    assert verdict(problem, latex) is expected


@pytest.mark.parametrize(
    ("latex", "expected"),
    [
        ("x=7", Verdict.CORRECT),
        ("7=x", Verdict.CORRECT),
        ("7", Verdict.CORRECT),
        ("2x=14", Verdict.CORRECT),
        ("x=8", Verdict.INCORRECT),
        ("8", Verdict.INCORRECT),
    ],
)
def test_equation_answer(latex: str, expected: Verdict) -> None:
    assert verdict(make_problem(sympy.Eq(x, 7)), latex) is expected


def test_equation_student_for_expression_answer_is_incorrect() -> None:
    assert verdict(make_problem(sympy.Integer(7)), "x=7") is Verdict.INCORRECT


def test_misconception_is_reported() -> None:
    problem = make_problem(
        sympy.Integer(52), misconceptions=(Misconception("forgot_carry", sympy.Integer(42)),)
    )
    assert check(problem, "42") == CheckResult(Verdict.INCORRECT, "forgot_carry")
    assert check(problem, "52") == CheckResult(Verdict.CORRECT, None)
    assert check(problem, "7") == CheckResult(Verdict.INCORRECT, None)


@pytest.mark.parametrize(
    "latex",
    ["", r"\frac{1}{0}", r"\input{a}", "1/0", r"\frac{1}{1-1}", "0^{-1}", r"\sqrt[0]{4}", "2^{x"],
)
def test_hostile_input_is_unreadable(latex: str) -> None:
    assert verdict(make_problem(sympy.Integer(1)), latex) is Verdict.UNREADABLE


@pytest.mark.parametrize(
    "latex",
    ["2^{500+500}", "2^{--999}", "9^{9^{9}}", "x^{x^{x}}", "((9^{100})^{100})^{100}"],
)
def test_unbounded_power_is_unreadable_and_fast(latex: str) -> None:
    start = time.perf_counter()
    assert verdict(make_problem(sympy.Integer(1)), latex) is Verdict.UNREADABLE
    assert time.perf_counter() - start < 1


def test_huge_radicand_is_fast() -> None:
    start = time.perf_counter()
    check(make_problem(sympy.Integer(1)), r"\sqrt{" + "9" * 150 + "}")
    assert time.perf_counter() - start < 2


def test_to_sympy_decimals_are_exact() -> None:
    assert to_sympy(parse("0.75")) == sympy.Rational(3, 4)


def test_to_sympy_mixed_and_division_by_zero() -> None:
    assert to_sympy(parse(r"-1\frac{1}{2}")) == sympy.Rational(-3, 2)
    with pytest.raises(Unreadable):
        to_sympy(parse(r"1/(2-2)"))


def test_to_sympy_odd_root_of_negative_is_real() -> None:
    assert to_sympy(parse(r"\sqrt[3]{-8}")) == -2


def test_check_never_raises() -> None:
    problem = make_problem(sympy.Integer(1))
    for latex in ["0^{0}", r"\sqrt[x]{2}", "x/x", "xyz^2", r"\pi^{\pi}", "-" * 150 + "1"]:
        assert isinstance(check(problem, latex), CheckResult)


@pytest.mark.parametrize(
    "latex",
    ["(x+y+z+w)^{100}", "(a+b)(c+d)(e+f)(g+h)(i+j)(k+l)(m+n)(o+p)(q+r)(s+t)(u+v)(w+x)(y+z)(a+c)"],
)
def test_expansion_blowup_is_unreadable_and_fast(latex: str) -> None:
    start = time.perf_counter()
    assert verdict(make_problem(sympy.Integer(1)), latex) is Verdict.UNREADABLE
    assert time.perf_counter() - start < 1
