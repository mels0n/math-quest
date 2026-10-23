# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false
"""Teaching content of the twelve batch 2 skills: complete, renders for every problem, tells
each story in the shape its id names, and keeps the bank honest."""

import re
from collections import Counter
from pathlib import Path

import pytest

from mathquest.engine.catalog import load_catalog
from mathquest.engine.content.coverage import skill_coverage
from mathquest.engine.content.schema import BankItem, WordProblems, WordTemplate
from mathquest.engine.teaching import (
    render_explanations,
    render_feedback,
    render_hints,
    render_lesson,
)
from mathquest.engine.templates import plain
from mathquest.engine.types import Prompt, TextPart
from mathquest.engine.wordproblems import pick_template
from tests.engine.test_generators import holds, side_value

CONTENT = Path(__file__).resolve().parents[2] / "content"
CATALOG = load_catalog(CONTENT, "k8-core")
PACK = CATALOG.pack
SKILLS = (
    "count_on",
    "make_ten_strategy",
    "add_three_numbers",
    "missing_number_20",
    "fact_families_20",
    "doubles_near_doubles",
    "ten_more_ten_less",
    "sub_tens_within_100",
    "add_within_100_basic",
    "equal_or_not",
    "skip_count_2_5",
    "word_problems_20",
)
SEEDS = 60


def text_of(prompt: Prompt) -> str:
    return "".join(p.text for p in prompt if isinstance(p, TextPart))


@pytest.mark.parametrize("skill_id", SKILLS)
def test_skill_meets_every_coverage_target(skill_id: str) -> None:
    source = CATALOG.source(skill_id)
    coverage = skill_coverage(PACK, source.skill, source.generator)
    assert coverage.gaps == ()
    assert coverage.misconceptions >= 2
    assert coverage.feedback == coverage.misconceptions


@pytest.mark.parametrize("skill_id", SKILLS)
def test_lesson_has_screens_a_worked_example_and_a_try_it(skill_id: str) -> None:
    lesson = render_lesson(PACK.lessons[skill_id])
    assert 2 <= len(lesson.screens) <= 4
    assert lesson.worked_steps
    assert lesson.try_it_tier == 0


@pytest.mark.parametrize("skill_id", SKILLS)
def test_hints_and_feedback_render_for_every_problem_and_never_give_the_answer_away(
    skill_id: str,
) -> None:
    source = CATALOG.source(skill_id)
    explanations = PACK.explanations[skill_id]
    for tier in range(len(source.tier_difficulties)):
        for seed in range(SEEDS):
            problem = source.generate(seed, tier)
            hints = [plain(h) for h in render_hints(PACK.hints[skill_id], problem)]
            assert len(hints) == 3
            assert str(problem.answer) in hints[2]
            assert len(render_explanations(explanations, problem)) >= 3
            for wrong in problem.misconceptions:
                feedback = render_feedback(explanations, problem, wrong.key)
                assert feedback is not None, (skill_id, wrong.key)
                assert f"= {problem.answer}" not in plain(feedback)


def test_story_hints_never_hand_over_the_operation() -> None:
    """Choosing add or take away is what the skill practises, so the first two hints and
    every piece of feedback and explanation stay off it."""
    source = CATALOG.source("word_problems_20")
    banned = re.compile(r"\b(add|plus|subtract|minus|take away|takes away)\b", re.IGNORECASE)
    explanations = PACK.explanations["word_problems_20"]
    for tier in range(3):
        for seed in range(SEEDS):
            problem = source.generate(seed, tier)
            hints = [plain(h) for h in render_hints(PACK.hints["word_problems_20"], problem)]
            assert not banned.search(hints[0] + " " + hints[1]), hints
            for wrong in problem.misconceptions:
                feedback = render_feedback(explanations, problem, wrong.key)
                assert feedback is not None and not banned.search(plain(feedback)), feedback
            for approach in render_explanations(explanations, problem):
                assert not banned.search(plain(approach.body)), plain(approach.body)


# --- word problems -------------------------------------------------------------------------


def templates(skill_id: str) -> tuple[WordTemplate, ...]:
    return PACK.word_problems[skill_id].templates


@pytest.mark.parametrize("skill_id", ["add_three_numbers", "word_problems_20"])
def test_at_least_fifteen_templates_and_two_per_story_shape(skill_id: str) -> None:
    found = templates(skill_id)
    assert len(found) >= 15
    names = [t.id for t in found]
    assert len(set(names)) == len(names)
    per_shape = Counter(
        t.id.split("_", 1)[0] if skill_id == "add_three_numbers" else t.id.rsplit("_", 1)[0]
        for t in found
    )
    assert max(per_shape.values()) <= 2, per_shape
    assert len(per_shape) >= 7


def test_three_number_stories_use_the_generator_answer_and_show_every_number() -> None:
    for template in templates("add_three_numbers"):
        assert template.answer_from == "generator_answer"
        for name in ("a", "b", "c"):
            assert "{" + name in template.text_template, (template.id, name)


EXPRESSIONS = {
    "add_to": "a + b",
    "take_from": "m - n",
    "put_together": "a + b",
    "take_apart": "m - n",
    "compare_more": "m - n",
    "compare_fewer": "m - n",
    "change_add": "m - n",
    "change_take": "m - n",
    "start_add": "m - n",
    "start_take": "a + b",
}
WORD_SHAPES_BY_TIER = (
    ("add_to", "take_from"),
    ("put_together", "take_apart", "compare_more", "compare_fewer"),
    ("change_add", "change_take", "start_add", "start_take"),
)
KEYWORDS = {
    "add_to": ("more",),
    "take_from": ("take", "leave", "left", "give", "gives"),
    "put_together": ("in all", "play", "both", "together"),
    "take_apart": ("The rest",),
    "compare_more": ("How many more",),
    "compare_fewer": ("How many fewer",),
    "change_add": ("some more", "puts in some", "earns some"),
    "change_take": ("some", "got off"),
    "start_add": ("at first", "before"),
    "start_take": ("at first",),
}


def story_shape(template_id: str) -> str:
    """``compare_more_hill`` -> ``compare_more``; ``add_to_pond`` -> ``add_to``."""
    for shape in sorted(EXPRESSIONS, key=len, reverse=True):
        if template_id.startswith(shape + "_"):
            return shape
    raise AssertionError(template_id)


def test_every_story_template_computes_the_answer_its_shape_asks_for() -> None:
    shapes = Counter()
    for template in templates("word_problems_20"):
        shape = story_shape(template.id)
        shapes[shape] += 1
        assert template.answer_from == "expression"
        assert template.expression == EXPRESSIONS[shape], template.id
        assert any(k in template.text_template for k in KEYWORDS[shape]), template.id
    assert set(shapes) == set(EXPRESSIONS)
    assert max(shapes.values()) <= 2


def test_stories_agree_with_one_and_show_both_numbers() -> None:
    for skill_id in ("add_three_numbers", "word_problems_20"):
        source = CATALOG.source(skill_id)
        for template in templates(skill_id):
            for tier in range(3):
                for seed in range(120):
                    problem = source.generate(seed, tier, "word", template.id)
                    text = text_of(problem.prompt)
                    assert not re.search(r"\b1 (?!of\b)[a-z]+s\b", text), (template.id, text)
                    assert not re.search(r"\b1 more [a-z]+s\b", text), (template.id, text)
                    assert int(problem.answer) >= 1


def test_story_templates_serve_the_tier_of_their_shape() -> None:
    tiers_of = {
        "add_to": 0,
        "take_from": 0,
        "put_together": 1,
        "take_apart": 1,
        "compare_more": 1,
        "compare_fewer": 1,
    }
    for template in templates("word_problems_20"):
        expected = tiers_of.get(story_shape(template.id), 2)
        assert template.tiers == (expected,), template.id
    source = CATALOG.source("word_problems_20")
    for tier in range(3):
        for seed in range(200):
            problem = source.generate(seed, tier, "word")
            assert problem.template_id is not None
            assert story_shape(problem.template_id) in WORD_SHAPES_BY_TIER[tier]


def test_story_answers_follow_the_numbers_told() -> None:
    source = CATALOG.source("word_problems_20")
    for template in templates("word_problems_20"):
        for seed in range(80):
            problem = source.generate(seed, seed % 3, "word", template.id)
            adds = EXPRESSIONS[story_shape(template.id)] == "a + b"
            a, b = (int(problem.values[k]) for k in (("a", "b") if adds else ("m", "n")))
            shown = [int(n) for n in re.findall(r"\d+", text_of(problem.prompt))]
            assert sorted(shown) == sorted([a, b]), (template.id, shown, a, b)
            expected = a + b if adds else a - b
            assert problem.answer == expected
            assert 1 <= expected <= 20


@pytest.mark.parametrize("skill_id", ["add_three_numbers", "word_problems_20"])
def test_rendered_stories_keep_to_twelve_words_a_sentence(skill_id: str) -> None:
    """The lint counts a template's source, where ``{a obj}`` is one word; a child reads the
    filled-in sentence, so count that."""
    source = CATALOG.source(skill_id)
    for template in templates(skill_id):
        for seed in range(SEEDS):
            problem = source.generate(seed, seed % 3, "word", template.id)
            for sentence in re.split(r"(?<=[.!?])\s+", text_of(problem.prompt)):
                assert len(sentence.split()) <= 12, (template.id, sentence)


# --- the true or false bank -----------------------------------------------------------------


def bank_truth(item: BankItem) -> bool:
    """What the item's sentence, pair or two sentences say: the first choice is the right one
    when it is true."""
    math = [p.value for p in item.prompt if p.kind == "math"]
    if item.choices is not None and all(len(c) == 1 and c[0].kind == "math" for c in item.choices):
        sentences = [c[0].value for c in item.choices]
        truth = [holds(s, 0) for s in sentences]
        assert truth.count(True) == 1, sentences
        assert isinstance(item.answer.value, int)
        return truth[item.answer.value]
    if len(math) == 1:
        return holds(math[0], 0)
    first, second = math
    return side_value(first) == side_value(second)


def test_the_true_or_false_bank_is_sound() -> None:
    bank = PACK.bank["equal_or_not"]
    items = bank.items
    assert len(items) >= 30
    assert len({i.id for i in items}) == len(items)
    tiers = Counter(i.tier for i in items)
    assert set(tiers) == {0, 1, 2} and min(tiers.values()) >= 8
    truths = []
    for item in items:
        assert item.choices is not None and len(item.choices) == 2
        assert item.answer.kind == "choice" and item.answer.value in (0, 1)
        truth = bank_truth(item)
        truths.append(truth)
        if not (all(len(c) == 1 and c[0].kind == "math" for c in item.choices)):
            # The first choice is the "yes" label: it is the right one exactly when true.
            assert (item.answer.value == 0) == truth, item.id
    share = sum(truths) / len(truths)
    assert 0.4 <= share <= 0.6, share


def test_false_items_are_wrong_by_more_than_one() -> None:
    """A child who learns "false means off by one" has learned nothing about equality."""
    gaps: list[int] = []
    for item in PACK.bank["equal_or_not"].items:
        math = [p.value for p in item.prompt if p.kind == "math"]
        if not math or bank_truth(item):
            continue
        sides = math[0].split("=") if len(math) == 1 else math
        gaps.append(abs(side_value(sides[0]) - side_value(sides[1])))
    assert len(set(gaps)) >= 4, sorted(gaps)
    assert gaps.count(1) / len(gaps) <= 0.4, sorted(gaps)


def test_the_true_or_false_bank_is_served_to_every_tier_with_two_choices() -> None:
    source = CATALOG.source("equal_or_not")
    for tier in range(3):
        served = [source.generate(seed, tier, "bank") for seed in range(200)]
        assert all(p.variant == "bank" and p.choices is not None for p in served)
        assert all(len(p.choices or ()) == 2 for p in served)
        assert len({p.template_id for p in served}) >= 8
        assert {p.correct_choice for p in served} == {0, 1}
    assert source.skill.keypad == "numpad" and source.skill.bank_share == 0.4


def test_bank_prompts_start_without_a_number_and_read_simply() -> None:
    for item in PACK.bank["equal_or_not"].items:
        first = item.prompt[0]
        assert first.kind == "text", item.id
        spoken = "".join(p.value if p.kind == "text" else " # " for p in item.prompt)
        for sentence in re.split(r"(?<=[.?!:]) ", spoken):
            assert len(sentence.split()) <= 12, (item.id, sentence)


# --- tier-aware template choice ---------------------------------------------------------------


def _template(template_id: str, tiers: tuple[int, ...] | None) -> WordTemplate:
    return WordTemplate(
        id=template_id,
        text_template="Sam has {a} cats.",
        grade_band="1",
        tiers=tiers,
    )


def test_pick_template_serves_only_the_tier_a_template_names() -> None:
    word = WordProblems(skill="s", templates=(_template("one", (1,)), _template("any", None)))
    assert {pick_template(word, seed, 0).id for seed in range(50)} == {"any"}
    assert {pick_template(word, seed, 1).id for seed in range(50)} == {"one", "any"}
    # No tier given: only the templates that serve every tier.
    assert {pick_template(word, seed).id for seed in range(50)} == {"any"}


def test_pick_template_falls_back_to_every_template_when_none_serves_the_tier() -> None:
    word = WordProblems(skill="s", templates=(_template("a", (1,)), _template("b", (2,))))
    assert {pick_template(word, seed, 0).id for seed in range(50)} == {"a", "b"}
