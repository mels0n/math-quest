"""Content lint: a clean pack has no findings, and each rule catches its own fixture."""

import dataclasses
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

from mathquest.engine.content import Pack, load_pack
from mathquest.engine.content.lint import Finding, errors, lint
from mathquest.engine.generators import all_generators
from mathquest.engine.types import Generator
from tests.engine.content.packbuilder import CONTENT, SLOTS, WORDS, base, load

REGISTRY = all_generators()


def _lint(pack: Pack, registry: dict[str, Generator] | None = None) -> list[Finding]:
    return lint(pack, REGISTRY if registry is None else registry, slots=SLOTS, words=WORDS)


def _rule(findings: list[Finding], rule: str) -> list[Finding]:
    return [f for f in findings if f.rule == rule]


def _edit(files: dict[str, Any], rel: str, change: Callable[[Any], None]) -> dict[str, Any]:
    change(files[rel])
    return files


def test_clean_pack_has_no_findings(tmp_path: Path) -> None:
    assert _lint(load(tmp_path, base())) == []


def test_real_pack_has_no_errors() -> None:
    findings = _lint(load_pack(CONTENT / "packs" / "k8-core"))
    assert errors(findings) == []


def test_finding_prints_file_path_rule_and_message() -> None:
    finding = Finding("error", "hints/a.yaml", "levels[0]", "dashes", "em dash")
    assert str(finding) == "hints/a.yaml:levels[0]: dashes: em dash"


# --- rule 1: graph ---


def _with_prereqs(pack: Pack, prereqs: tuple[str, ...]) -> Pack:
    alpha = pack.skills["alpha"].model_copy(update={"prerequisites": prereqs})
    return pack.model_copy(update={"skills": {"alpha": alpha}})


def test_graph_cycle_and_unreachable(tmp_path: Path) -> None:
    pack = _with_prereqs(load(tmp_path, base()), ("alpha",))
    messages = [f.message for f in _rule(_lint(pack), "graph")]
    assert any("cycle: alpha -> alpha" in m for m in messages)
    assert any("cannot be reached" in m for m in messages)


def test_graph_unknown_prerequisite(tmp_path: Path) -> None:
    pack = _with_prereqs(load(tmp_path, base()), ("ghost",))
    (finding,) = _rule(_lint(pack), "graph")
    assert (finding.file, finding.path) == ("skills.yaml", "skills[0].prerequisites[0]")


# --- rule 2: generators ---


def test_generator_missing(tmp_path: Path) -> None:
    (finding,) = _rule(_lint(load(tmp_path, base()), {}), "generator")
    assert finding.level == "error"
    assert finding.path == "skills[0].generator"


def test_generator_tier_count(tmp_path: Path) -> None:
    real = REGISTRY["add_within_20"]

    @dataclasses.dataclass
    class TwoTiers:
        generator_id: str = "add_within_20"
        tier_difficulties: tuple[float, ...] = (1.0, 2.0)
        misconception_keys: tuple[str, ...] = real.misconception_keys
        generate: Any = real.generate

    (finding,) = _rule(_lint(load(tmp_path, base()), {"add_within_20": TwoTiers()}), "generator")
    assert finding.path == "skills[0].tiers"


def test_generator_unknown_misconception(tmp_path: Path) -> None:
    files = _edit(
        base(),
        "explanations/alpha.yaml",
        lambda e: e["misconceptions"].update({"forgot_carry": "Carry the one."}),
    )
    (finding,) = _rule(_lint(load(tmp_path, files)), "generator")
    assert (finding.file, finding.path) == (
        "explanations/alpha.yaml",
        "misconceptions.forgot_carry",
    )


# --- rule 3 and coverage ---


def test_missing_teaching_is_a_warning_outside_complete_regions(tmp_path: Path) -> None:
    files = base()
    del files["hints/alpha.yaml"]
    (finding,) = _rule(_lint(load(tmp_path, files)), "teaching")
    assert finding.level == "warning"
    assert "no hints" in finding.message


def test_missing_teaching_is_an_error_in_a_complete_region(tmp_path: Path) -> None:
    files = base()
    del files["hints/alpha.yaml"]
    pack = load(tmp_path, files).model_copy(update={"complete_regions": ("meadow",)})
    (finding,) = _rule(_lint(pack), "teaching")
    assert finding.level == "error"


def test_coverage_gaps_are_errors_only_in_a_complete_region(tmp_path: Path) -> None:
    pack = load(tmp_path, base())
    assert _rule(_lint(pack), "coverage") == []
    found = _rule(_lint(pack.model_copy(update={"complete_regions": ("meadow",)})), "coverage")
    assert {f.level for f in found} == {"error"}
    text = " ".join(f.message for f in found)
    assert "misconceptions 1 of 2" in text
    assert "word templates 3 of 15" in text
    assert "bank items 2 of 30" in text


# --- rule 4: answers ---


def test_expression_answer_must_be_accepted(tmp_path: Path) -> None:
    files = _edit(
        base(),
        "word_problems/alpha.yaml",
        lambda w: w["templates"][2].update({"expression": r"\frac{a}{2}"}),
    )
    (finding,) = _rule(_lint(load(tmp_path, files)), "answers")
    assert finding.level == "error"
    assert finding.path == "templates[2].text_template"
    assert "not accepted as integer" in finding.message


def test_bank_answer_must_be_accepted(tmp_path: Path) -> None:
    files = _edit(
        base(),
        "bank/alpha.yaml",
        lambda b: b["items"][1]["answer"].update({"value": r"\frac{1}{2}"}),
    )
    (finding,) = _rule(_lint(load(tmp_path, files)), "answers")
    assert (finding.file, finding.path) == ("bank/alpha.yaml", "items[1]")


def test_template_leaving_out_a_number_is_a_warning(tmp_path: Path) -> None:
    files = _edit(
        base(),
        "word_problems/alpha.yaml",
        lambda w: w["templates"][1].update({"text_template": "{a} birds sit. Then more land."}),
    )
    (finding,) = _rule(_lint(load(tmp_path, files)), "answers")
    assert finding.level == "warning"
    assert "never shows b" in finding.message


# --- rule 5: computed numbers ---


def test_hint_computing_a_fraction_in_text_fails(tmp_path: Path) -> None:
    files = _edit(
        base(),
        "hints/alpha.yaml",
        lambda h: h["levels"][0].update({"text_template": r"Half of {a} is {{= \frac{a}{2} }}."}),
    )
    (finding,) = _rule(_lint(load(tmp_path, files)), "computed")
    assert (finding.file, finding.path) == ("hints/alpha.yaml", "levels")
    assert "must be inside a math part" in finding.message


def test_lesson_computed_number_must_use_literals(tmp_path: Path) -> None:
    files = _edit(
        base(),
        "lessons/alpha.yaml",
        lambda lesson: lesson["worked_example"]["steps"].append("Now {{= a + 1 }}."),
    )
    (finding,) = _rule(_lint(load(tmp_path, files)), "computed")
    assert finding.file == "lessons/alpha.yaml"
    assert "unknown name" in finding.message


def test_feedback_is_rendered_for_each_misconception(tmp_path: Path) -> None:
    files = _edit(
        base(),
        "explanations/alpha.yaml",
        lambda e: e["misconceptions"].update({"subtracted_instead": "Try {{= a / 0 }}."}),
    )
    (finding,) = _rule(_lint(load(tmp_path, files)), "computed")
    assert finding.path == "misconceptions.subtracted_instead"


# --- rule 6: duplicates ---


def test_near_duplicate_templates_in_one_skill(tmp_path: Path) -> None:
    files = _edit(
        base(),
        "word_problems/alpha.yaml",
        lambda w: w["templates"].append(
            {
                "id": "birds_again",
                "text_template": "{b} birds sit on a fence! {a} birds land. How many birds??",
                "grade_band": 1,
            }
        ),
    )
    (finding,) = _rule(_lint(load(tmp_path, files)), "duplicate")
    assert finding.level == "error"
    assert {finding.path, finding.message.rsplit(" ", 1)[-1]} == {"templates[1]", "templates[3]"}


def test_near_duplicate_explanations_and_bank_items(tmp_path: Path) -> None:
    files = base()
    files["explanations/alpha.yaml"]["approaches"][1]["body_md"] = (
        "Picture a number line. Jump from {b} to the right!"
    )
    files["bank/alpha.yaml"]["items"].append(
        {
            "id": "bigger_again",
            "prompt": [{"kind": "text", "value": "Which number is bigger?"}],
            "answer": {"kind": "choice", "value": 0},
            "choices": [[{"kind": "math", "value": "9"}], [{"kind": "math", "value": "2"}]],
        }
    )
    found = _rule(_lint(load(tmp_path, files)), "duplicate")
    assert sorted(f.file for f in found) == ["bank/alpha.yaml", "explanations/alpha.yaml"]


def test_near_duplicate_across_skills_is_a_warning(tmp_path: Path) -> None:
    files = base()
    beta = {**files["skills.yaml"]["skills"][0], "id": "beta", "prerequisites": ["alpha"]}
    beta.update({"banked": False})
    files["skills.yaml"]["skills"].append(beta)
    files["word_problems/beta.yaml"] = {
        "skill": "beta",
        "templates": [files["word_problems/alpha.yaml"]["templates"][1]],
    }
    found = _rule(_lint(load(tmp_path, files)), "duplicate")
    assert [(f.level, f.file) for f in found] == [("warning", "word_problems/alpha.yaml")]
    assert "word_problems/beta.yaml:templates[0]" in found[0].message


# --- rule 7: reading level ---


def test_long_sentence_is_an_error_for_early_grades(tmp_path: Path) -> None:
    long = "Start at {a} and then count on {b} more jumps to get to the end now."
    files = _edit(base(), "hints/alpha.yaml", lambda h: h["levels"][1].update(text_template=long))
    (finding,) = _rule(_lint(load(tmp_path, files)), "reading")
    assert finding.level == "error"
    assert "16 words" in finding.message


def test_long_sentence_is_fine_from_grade_three(tmp_path: Path) -> None:
    long = "Start at {a} and then count on {b} more jumps to get to the end now."
    files = _edit(base(), "hints/alpha.yaml", lambda h: h["levels"][1].update(text_template=long))
    files["skills.yaml"]["skills"][0]["grade_band"] = "3"
    for template in files["word_problems/alpha.yaml"]["templates"]:
        template["grade_band"] = 3
    assert _rule(_lint(load(tmp_path, files)), "reading") == []


def test_hard_word_is_a_warning_unless_in_the_skill_vocabulary(tmp_path: Path) -> None:
    text = "Use the commutative property on {a} and {b}."
    files = _edit(base(), "hints/alpha.yaml", lambda h: h["levels"][0].update(text_template=text))
    (finding,) = _rule(_lint(load(tmp_path, files)), "reading")
    assert finding.level == "warning"
    assert finding.message.endswith("commutative, property")
    files["skills.yaml"]["skills"][0]["vocabulary"] = ["commutative", "property"]
    assert _rule(_lint(load(tmp_path / "again", files)), "reading") == []


def test_list_markers_and_inflections_are_read_sensibly(tmp_path: Path) -> None:
    body = "1. Count the jumping frogs.\n2. Hopping bunnies counted.\n3. The biggest ones."
    files = _edit(
        base(),
        "explanations/alpha.yaml",
        lambda e: e["approaches"][1].update(body_md=body),
    )
    assert _rule(_lint(load(tmp_path, files)), "reading") == []


# --- rule 8: dashes ---


@pytest.mark.parametrize("dash", ["\u2014", "\u2013", " -- "])
def test_dashes_in_kid_text(tmp_path: Path, dash: str) -> None:
    text = f"Put {{a}} and {{b}} together{dash}add them."
    files = _edit(base(), "hints/alpha.yaml", lambda h: h["levels"][0].update(text_template=text))
    (finding,) = _rule(_lint(load(tmp_path, files)), "dashes")
    assert (finding.level, finding.path) == ("error", "levels[0].text_template")


def test_double_minus_inside_math_is_not_a_dash(tmp_path: Path) -> None:
    text = r"Put {a} and {b} together: \({a} - -{b}\) is not it."
    files = _edit(base(), "hints/alpha.yaml", lambda h: h["levels"][0].update(text_template=text))
    assert _rule(_lint(load(tmp_path, files)), "dashes") == []


# --- rule 9: slots ---


def test_unknown_slot_name(tmp_path: Path) -> None:
    files = _edit(
        base(),
        "word_problems/alpha.yaml",
        lambda w: w["templates"][1].update(text_template="{a} {pet} sit. {b} land. How many?"),
    )
    (finding,) = _rule(_lint(load(tmp_path, files)), "slots")
    assert "pet is neither" in finding.message


def test_unused_slot(tmp_path: Path) -> None:
    files = _edit(
        base(),
        "word_problems/alpha.yaml",
        lambda w: w["templates"][1].update(slots={"name": "names"}),
    )
    (finding,) = _rule(_lint(load(tmp_path, files)), "slots")
    assert finding.path == "templates[1].slots.name"
    assert "never used" in finding.message


def test_slot_hiding_a_generator_value(tmp_path: Path) -> None:
    files = _edit(
        base(),
        "word_problems/alpha.yaml",
        lambda w: w["templates"][1].update(slots={"b": "number"}),
    )
    found = _rule(_lint(load(tmp_path, files)), "slots")
    assert any("hides the generator value" in f.message for f in found)
