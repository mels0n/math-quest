import contextlib
import time

import pytest
from hypothesis import given
from hypothesis import strategies as st

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
    parse,
)

CASES: list[tuple[str, Node]] = [
    (r"\frac{6}{8}", Div(Num("6"), Num("8"), "frac")),
    (r"\dfrac{6}{8}", Div(Num("6"), Num("8"), "frac")),
    (r"1\frac{1}{2}", Mixed(Num("1"), Div(Num("1"), Num("2"), "frac"))),
    (r"3/2", Div(Num("3"), Num("2"), "slash")),
    (r"6\div3", Div(Num("6"), Num("3"), "div")),
    (r"2\sqrt{2}", Mul((Num("2"), Sqrt(Num("2"), None)), implicit=True)),
    (r"\sqrt[3]{8}", Sqrt(Num("8"), Num("3"))),
    (
        r"(x+3)(x-2)",
        Mul(
            (
                Group(Add((Var("x"), Num("3")))),
                Group(Add((Var("x"), Neg(Num("2"))))),
            ),
            implicit=True,
        ),
    ),
    (r"\left(x+1\right)", Group(Add((Var("x"), Num("1"))))),
    (r"x=7", Eq(Var("x"), Num("7"))),
    ("\N{MINUS SIGN}4", Neg(Num("4"))),
    (r"3\times4", Mul((Num("3"), Num("4")), implicit=False)),
    (r"3\cdot4", Mul((Num("3"), Num("4")), implicit=False)),
    (r"xy", Mul((Var("x"), Var("y")), implicit=True)),
    (r"2.5", Num("2.5")),
    (r"2\pi", Mul((Num("2"), Const("pi")), implicit=True)),
    (r"x^2", Pow(Var("x"), Num("2"))),
    (r"x^{2}", Pow(Var("x"), Num("2"))),
    (r"x^{-2}", Pow(Var("x"), Neg(Num("2")))),
    (r"-2^2", Neg(Pow(Num("2"), Num("2")))),
    (r"2\,x\ y", Mul((Num("2"), Var("x"), Var("y")), implicit=True)),
    (r"2\frac{x}{3}", Mul((Num("2"), Div(Var("x"), Num("3"), "frac")), implicit=True)),
    (r"x\frac{1}{2}", Mul((Var("x"), Div(Num("1"), Num("2"), "frac")), implicit=True)),
    (r"2^{1\frac{1}{2}}", Pow(Num("2"), Mul((Num("1"), Div(Num("1"), Num("2"), "frac")), True))),
    (r"2+3\cdot4", Add((Num("2"), Mul((Num("3"), Num("4")), implicit=False)))),
    (r"1-2-3", Add((Num("1"), Neg(Num("2")), Neg(Num("3"))))),
    (r"-1\frac{1}{2}", Neg(Mixed(Num("1"), Div(Num("1"), Num("2"), "frac")))),
    (r"2^{100}", Pow(Num("2"), Num("100"))),
    (r"\frac12", Div(Num("1"), Num("2"), "frac")),
    (r"\frac{1}2", Div(Num("1"), Num("2"), "frac")),
    (r"\frac1{2}", Div(Num("1"), Num("2"), "frac")),
    (r"\frac x2", Div(Var("x"), Num("2"), "frac")),
    (r"\sqrt2", Sqrt(Num("2"), None)),
    (r"\sqrt x", Sqrt(Var("x"), None)),
    (r"\sqrt\pi", Sqrt(Const("pi"), None)),
    (r"1\frac12", Mixed(Num("1"), Div(Num("1"), Num("2"), "frac"))),
    (r"1\frac{1}2", Mixed(Num("1"), Div(Num("1"), Num("2"), "frac"))),
]


@pytest.mark.parametrize(("src", "expected"), CASES)
def test_parse(src: str, expected: Node) -> None:
    assert parse(src) == expected


@pytest.mark.parametrize(
    "src",
    [
        "",
        "   ",
        r"\input{x}",
        "(",
        ")",
        "x" * 201,
        "(" * 21 + "x" + ")" * 21,
        r"2^{999}",
        r"2^{-101}",
        r"x^23",
        "x==2",
        "x+",
        r"\frac{1}",
        r"\sqrt{2",
        "1 2",
        "x_1",
        "2!",
        r"\left[x\right]",
        "{x}",
        r"\frac123",
        r"\frac1.5",
        r"\sqrt",
        r"\frac1",
    ],
)
def test_unreadable(src: str) -> None:
    with pytest.raises(Unreadable):
        parse(src)


def test_depth_limit_boundary() -> None:
    parse("(" * 20 + "x" + ")" * 20)


ALPHABET = [
    *"0123456789.xyzXY+-=()/ ,\N{MINUS SIGN}",
    r"\frac",
    r"\dfrac",
    r"\sqrt",
    r"\pi",
    r"\cdot",
    r"\times",
    r"\div",
    r"\left(",
    r"\right)",
    r"\,",
    r"\ ",
    "^",
    "{",
    "}",
    "_",
    "[",
    "]",
    "\\",
]


@given(st.lists(st.sampled_from(ALPHABET), max_size=60).map("".join))
def test_parse_never_raises_other_errors(src: str) -> None:
    try:
        result = parse(src)
    except Unreadable:
        return
    assert isinstance(
        result, Num | Var | Neg | Add | Mul | Div | Pow | Sqrt | Mixed | Eq | Group | Const
    )


def test_nested_frac_parse_is_not_exponential() -> None:
    src = r"2\frac{" * 18 + "x" + "}{1}" * 18
    assert len(src) <= 200
    start = time.perf_counter()
    with contextlib.suppress(Unreadable):
        parse(src)
    assert time.perf_counter() - start < 0.5


def test_numeric_frac_inside_nested_still_mixed() -> None:
    assert parse(r"\frac{1\frac{1}{2}}{3}") == Div(
        Mixed(Num("1"), Div(Num("1"), Num("2"), "frac")), Num("3"), "frac"
    )
