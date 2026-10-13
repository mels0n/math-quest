import pytest

from mathquest.engine.checker.forms import satisfies_form
from mathquest.engine.checker.latex import parse
from mathquest.engine.checker.sympy_bridge import to_sympy
from mathquest.engine.types import AnswerForm


def ok(latex: str, form: AnswerForm) -> bool:
    node = parse(latex)
    value = to_sympy(node)
    return satisfies_form(node, value, form)


@pytest.mark.parametrize(
    ("latex", "form", "expected"),
    [
        ("5", AnswerForm.ANY, True),
        ("7", AnswerForm.INTEGER, True),
        ("-7", AnswerForm.INTEGER, True),
        ("7.0", AnswerForm.INTEGER, False),
        (r"\frac{14}{2}", AnswerForm.INTEGER, False),
        ("x=7", AnswerForm.INTEGER, True),
        ("2x=7", AnswerForm.INTEGER, False),
        ("5", AnswerForm.LOWEST_TERMS, True),
        (r"\frac{3}{4}", AnswerForm.LOWEST_TERMS, True),
        (r"-\frac{3}{4}", AnswerForm.LOWEST_TERMS, True),
        (r"\frac{-3}{4}", AnswerForm.LOWEST_TERMS, True),
        ("3/4", AnswerForm.LOWEST_TERMS, True),
        (r"\frac{6}{8}", AnswerForm.LOWEST_TERMS, False),
        (r"\frac{4}{1}", AnswerForm.LOWEST_TERMS, False),
        (r"\frac{0}{5}", AnswerForm.LOWEST_TERMS, False),
        ("0.5", AnswerForm.LOWEST_TERMS, False),
        (r"1\frac{1}{2}", AnswerForm.LOWEST_TERMS, True),
        (r"1\frac{2}{4}", AnswerForm.LOWEST_TERMS, False),
        (r"1\frac{1}{2}", AnswerForm.MIXED_NUMBER, True),
        (r"-1\frac{1}{2}", AnswerForm.MIXED_NUMBER, True),
        (r"\frac{3}{2}", AnswerForm.MIXED_NUMBER, False),
        (r"\frac{1}{2}", AnswerForm.MIXED_NUMBER, True),
        (r"\frac{2}{4}", AnswerForm.MIXED_NUMBER, False),
        ("3", AnswerForm.MIXED_NUMBER, True),
        ("1.5", AnswerForm.MIXED_NUMBER, False),
        (r"1\frac{3}{2}", AnswerForm.MIXED_NUMBER, False),
        (r"\sqrt{8}", AnswerForm.SIMPLIFIED_RADICAL, False),
        (r"2\sqrt{2}", AnswerForm.SIMPLIFIED_RADICAL, True),
        (r"\sqrt{12}", AnswerForm.SIMPLIFIED_RADICAL, False),
        (r"\sqrt{4}", AnswerForm.SIMPLIFIED_RADICAL, False),
        (r"\sqrt{6}", AnswerForm.SIMPLIFIED_RADICAL, True),
        (r"\sqrt{50}", AnswerForm.SIMPLIFIED_RADICAL, False),
        (r"\frac{1}{\sqrt{2}}", AnswerForm.SIMPLIFIED_RADICAL, False),
        (r"\frac{\sqrt{2}}{2}", AnswerForm.SIMPLIFIED_RADICAL, True),
        (r"3+2\sqrt{5}", AnswerForm.SIMPLIFIED_RADICAL, True),
        (r"\sqrt[3]{16}", AnswerForm.SIMPLIFIED_RADICAL, False),
        (r"\sqrt[3]{18}", AnswerForm.SIMPLIFIED_RADICAL, True),
        (r"\sqrt{x}", AnswerForm.SIMPLIFIED_RADICAL, True),
        ("(x+3)(x-2)", AnswerForm.FACTORED, True),
        ("-(x+3)(x-2)", AnswerForm.FACTORED, True),
        ("2(x+3)", AnswerForm.FACTORED, True),
        ("x(x+3)", AnswerForm.FACTORED, True),
        ("(x+3)^2", AnswerForm.FACTORED, True),
        ("(x^2+1)(x+3)", AnswerForm.FACTORED, True),
        ("(x^2-4)(x+1)", AnswerForm.FACTORED, False),
        ("x^2+x-6", AnswerForm.FACTORED, False),
        ("(x+3)", AnswerForm.FACTORED, False),
        ("-(x+3)^2", AnswerForm.FACTORED, True),
        (r"\frac{6\sqrt{2}}{3}", AnswerForm.SIMPLIFIED_RADICAL, False),
        (r"\frac{2\sqrt{2}}{4}", AnswerForm.SIMPLIFIED_RADICAL, False),
        (r"\frac{3\sqrt{2}}{2}", AnswerForm.SIMPLIFIED_RADICAL, True),
        (r"\frac{2+4\sqrt{2}}{2}", AnswerForm.SIMPLIFIED_RADICAL, False),
        (r"\sqrt{2}+\sqrt{2}", AnswerForm.SIMPLIFIED_RADICAL, False),
        (r"\sqrt{2}+\sqrt{3}", AnswerForm.SIMPLIFIED_RADICAL, True),
        (r"2\sqrt{2}-\sqrt{2}", AnswerForm.SIMPLIFIED_RADICAL, False),
        (r"1+2\sqrt{2}", AnswerForm.SIMPLIFIED_RADICAL, True),
        (r"\sqrt{2^{2}}", AnswerForm.SIMPLIFIED_RADICAL, False),
        ("x^2+x-6", AnswerForm.EXPANDED, True),
        ("(x+3)(x-2)", AnswerForm.EXPANDED, False),
        ("x(x+3)", AnswerForm.EXPANDED, False),
        ("(x+1)^2", AnswerForm.EXPANDED, False),
        ("2(x+3)", AnswerForm.EXPANDED, False),
        ("x^2+(x(x+1))", AnswerForm.EXPANDED, False),
        ("3x-6", AnswerForm.EXPANDED, True),
    ],
)
def test_satisfies_form(latex: str, form: AnswerForm, expected: bool) -> None:
    assert ok(latex, form) is expected
