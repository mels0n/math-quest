"""The content template language."""

import pytest

from mathquest.engine.content.schema import Noun
from mathquest.engine.templates import (
    TemplateError,
    article,
    check_expression,
    check_template,
    names,
    render,
)
from mathquest.engine.types import MathPart, TextPart


def test_slots_and_plain_text() -> None:
    assert render("{name} has {a} apples.", {"name": "Mia", "a": 7}) == (
        TextPart("Mia has 7 apples."),
    )


def test_objects_plural_and_singular() -> None:
    shell = Noun(one="shell", many="shells")
    assert render("{o} and one {o.one}", {"o": shell}) == (TextPart("shells and one shell"),)


def test_math_parts_split_text() -> None:
    assert render(r"Add \({a} + {b}\) now.", {"a": 3, "b": 4}) == (
        TextPart("Add "),
        MathPart("3 + 4"),
        TextPart(" now."),
    )


def test_braces_in_math_are_latex_unless_they_name_a_value() -> None:
    assert render(r"\(\frac{{a}}{{b}} = x^{2} + y^{{a}}\)", {"a": 12, "b": 5}) == (
        MathPart(r"\frac{12}{5} = x^{2} + y^{12}"),
    )


@pytest.mark.parametrize("template", [r"\(\frac{a}{b}\)", r"\(x^{a}\)", r"\(\sqrt {a}\)"])
def test_a_bare_slot_as_a_latex_argument_is_an_error(template: str) -> None:
    with pytest.raises(TemplateError, match="as a LaTeX argument"):
        check_template(template)


def test_computed_values() -> None:
    values = {"a": 9, "b": 6}
    assert render("{a} plus {b} is {{= a + b }}.", values) == (TextPart("9 plus 6 is 15."),)
    assert render(r"{{= a - b}} and {{= a \cdot b }}", values) == (TextPart("3 and 54"),)
    assert render("{{= b - a }}", values) == (TextPart("-3"),)
    assert render(r"\({{= \frac{a}{b} }}\)", values) == (MathPart(r"\frac{3}{2}"),)
    assert render(r"\({{= (b - a) / 2 }}\)", values) == (MathPart(r"-\frac{3}{2}"),)
    assert render("{{= 8 + 5 }}", {}) == (TextPart("13"),)


def test_a_fraction_must_be_in_math() -> None:
    with pytest.raises(TemplateError, match="inside a math part"):
        render("{{= a / 2 }}", {"a": 3})


def test_non_rational_results_rejected() -> None:
    with pytest.raises(TemplateError, match="not a whole number or fraction"):
        render(r"\({{= \sqrt{a} }}\)", {"a": 2})


@pytest.mark.parametrize(
    ("template", "values", "message"),
    [
        ("{nope}", {}, "unknown name: nope"),
        ("{{= a + zz }}", {"a": 1}, "unknown name in computed value: zz"),
        ("{{= place + 1 }}", {"place": "tens"}, "unknown name in computed value: place"),
        (r"\({name}\)", {"name": "Mia"}, "words cannot go in a math part"),
        ("{a.one}", {"a": 2}, r"\.one is for objects"),
        ("{w.one}", {"w": "tens"}, r"\.one is for objects"),
        ("{{= a / 0 }}", {"a": 1}, "cannot compute"),
    ],
)
def test_render_errors(template: str, values: dict[str, int | str], message: str) -> None:
    with pytest.raises(TemplateError, match=message):
        render(template, values)


@pytest.mark.parametrize(
    ("template", "message"),
    [
        ("{ a }", "stray"),
        ("a } b", "stray"),
        ("{a", "stray"),
        (r"\(1 + 2", "never closed"),
        (r"1 + 2\)", "without a matching"),
        (r"\(1 \( 2\)\)", "opened twice"),
        ("{{= }}", "empty computed value"),
        ("{{= a + }}", "cannot read"),
        (r"{{= \sin a }}", "cannot read"),
    ],
)
def test_malformed_templates(template: str, message: str) -> None:
    with pytest.raises(TemplateError, match=message):
        check_template(template)


def test_names_lists_slots_and_computed_names() -> None:
    assert names(r"{name} has {a} {o.one}; {{= a + b \cdot c }}") == {"name", "a", "o", "b", "c"}


def test_expression_check() -> None:
    assert check_expression(r"\frac{a + b}{2}") == r"\frac{a + b}{2}"
    with pytest.raises(TemplateError):
        check_expression("a +")


@pytest.mark.parametrize(
    ("word", "expected"),
    [
        ("apple", "an"), ("pear", "a"), ("egg", "an"), ("unicorn", "a"), ("umbrella", "an"),
        ("hour", "an"), ("hat", "a"), ("one", "a"), ("ukulele", "a"), ("ice cube", "an"),
    ],
)  # fmt: skip
def test_article_follows_the_first_sound(word: str, expected: str) -> None:
    assert article(word) == expected


def test_article_form_and_override() -> None:
    apple = Noun(one="apple", many="apples")
    herb = Noun(one="herb", many="herbs", article="an")
    assert render("{o.a} and {h.a}", {"o": apple, "h": herb}) == (TextPart("an apple and an herb"),)


def test_count_form_agrees_with_the_number() -> None:
    rock = Noun(one="rock", many="rocks")
    assert render("{n o}, {m o}", {"n": 1, "m": 5, "o": rock}) == (TextPart("1 rock, 5 rocks"),)
    assert names("{n o} and {o.a}") == {"n", "o"}


@pytest.mark.parametrize(
    ("template", "values", "message"),
    [
        ("{n o}", {"n": "two", "o": Noun(one="rock", many="rocks")}, "not a number"),
        ("{n o}", {"n": 2, "o": "rock"}, "cannot be counted"),
        ("{n.a}", {"n": 2}, "is a number"),
        ("{w.a}", {"w": "word"}, "is a word"),
    ],
)
def test_count_and_article_errors(template: str, values: dict[str, object], message: str) -> None:
    with pytest.raises(TemplateError, match=message):
        render(template, values)  # pyright: ignore[reportArgumentType]


@pytest.mark.parametrize(
    ("template", "message"), [("{n o.one}", "drop .one"), (r"\({n o}\)", "math part")]
)
def test_count_form_is_text_only_and_picks_its_own_form(template: str, message: str) -> None:
    with pytest.raises(TemplateError, match=message):
        check_template(template)
