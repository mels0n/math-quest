"""Pack schemas and the loader: valid packs load, every invalid one names file and path."""

import copy
import re
from pathlib import Path
from typing import Any

import pytest
import yaml

from mathquest.engine.catalog import build_catalog, load_catalog
from mathquest.engine.content import ContentError, Pack, load_pack, load_slots
from mathquest.engine.generators import all_generators
from mathquest.engine.types import KEYPAD_PROFILES

CONTENT = Path(__file__).resolve().parents[2] / "content"
PACK = CONTENT / "packs" / "k8-core"
SLOTS = load_slots(CONTENT / "slots.yaml")


def _skill(sid: str, *prereqs: str, **extra: Any) -> dict[str, Any]:
    return {
        "id": sid,
        "name": sid.title(),
        "region": "meadow",
        "prerequisites": list(prereqs),
        "fluency": False,
        "anchor": False,
        "generator": "add_within_10",
        "tiers": [{"id": i, "label": f"Tier {i}"} for i in range(3)],
        "grade_band": "K",
        "keypad": "numpad",
        **extra,
    }


def _lesson(skill: str) -> dict[str, Any]:
    return {
        "skill": skill,
        "screens": [
            {"title": "One", "body_md": "Count on."},
            {
                "title": "Two",
                "body_md": r"Jump along: \(3 + 2\).",
                "visual": {"kind": "number_line", "params": {"min": 0, "max": 10}},
            },
        ],
        "worked_example": {
            "prompt": [{"kind": "math", "value": "3 + 2 = ?"}],
            "steps": ["Start at 3.", "Count on 2."],
        },
        "try_it": {"tier": 0},
    }


def _base() -> dict[str, Any]:
    """A small valid pack, as file name -> YAML data."""
    return {
        "pack.yaml": {"id": "test-pack", "title": "Test", "version": "1.0.0"},
        "world.yaml": {
            "regions": [
                {
                    "id": "meadow",
                    "name": "Meadow",
                    "order": 1,
                    "creature_family": "family_a",
                    "boss_skill_set": ["alpha"],
                    "map_hint": "Grass.",
                },
                {
                    "id": "canyon",
                    "name": "Canyon",
                    "order": 2,
                    "creature_family": "family_b",
                    "map_hint": "Rocks.",
                },
            ]
        },
        "skills.yaml": {
            "skills": [
                _skill("alpha", word_problems_fit=True),
                _skill("beta", "alpha", banked=True),
            ]
        },
        "lessons/alpha.yaml": _lesson("alpha"),
        "hints/alpha.yaml": {
            "skill": "alpha",
            "levels": [{"text_template": t} for t in ("Look.", "Count {a}.", "It is {a}.")],
        },
        "explanations/alpha.yaml": {
            "skill": "alpha",
            "approaches": [
                {"style": "visual", "body_md": "Picture it."},
                {"style": "steps", "body_md": "Step by step."},
                {"style": "story", "body_md": "Once upon a time."},
            ],
            "misconceptions": {"subtracted_instead": "Add, do not take away."},
        },
        "word_problems/alpha.yaml": {
            "skill": "alpha",
            "templates": [
                {
                    "id": "apples",
                    "text_template": "{name} has {a} {obj}. How many?",
                    "slots": {"name": "names", "obj": "objects"},
                    "grade_band": 1,
                }
            ],
        },
        "bank/beta.yaml": {
            "skill": "beta",
            "items": [
                {
                    "id": "bigger",
                    "prompt": [{"kind": "text", "value": "Which is bigger?"}],
                    "answer": {"kind": "choice", "value": 1},
                    "choices": [
                        [{"kind": "math", "value": "3"}],
                        [{"kind": "math", "value": "7"}],
                        [{"kind": "math", "value": "5"}],
                    ],
                },
                {
                    "id": "half",
                    "prompt": [{"kind": "text", "value": "Half of 8?"}],
                    "answer": {"kind": "expr", "value": "4"},
                },
            ],
        },
    }


def _write(root: Path, files: dict[str, Any]) -> Path:
    pack = root / "test-pack"
    for rel, data in files.items():
        path = pack / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")
    return pack


def _load(tmp_path: Path, files: dict[str, Any]) -> Pack:
    return load_pack(_write(tmp_path, files))


def test_valid_fixture_loads(tmp_path: Path) -> None:
    pack = _load(tmp_path, _base())
    assert pack.id == "test-pack"
    assert list(pack.skills) == ["alpha", "beta"]
    assert pack.skills["alpha"].word_share == 0.4
    assert pack.skills["beta"].bank_share == 0.25
    assert pack.lessons["alpha"].screens[1].visual is not None
    assert pack.word_problems["alpha"].templates[0].grade_band == "1"
    assert pack.bank["beta"].items[0].answer.value == 1
    catalog = build_catalog(pack, SLOTS)
    assert catalog.graph.topo_order() == ["alpha", "beta"]
    assert catalog.source("beta").generate(5, 1).skill_id == "beta"


def test_real_pack_loads_and_binds() -> None:
    catalog = load_catalog(CONTENT, "k8-core")
    pack = catalog.pack
    assert pack.id == "k8-core"
    assert re.fullmatch(r"\d+\.\d+\.\d+", pack.version)
    assert [r.id for r in sorted(pack.world.regions, key=lambda r: r.order)] == [
        "number_meadows",
        "operation_canyon",
        "fraction_forest",
        "decimal_docks",
        "ratio_ridge",
        "integer_ice_caves",
        "expression_swamp",
        "equation_peaks",
    ]
    bands = {sid: s.grade_band for sid, s in pack.skills.items()}
    assert bands == {
        "count_to_10": "K",
        "add_within_10": "K",
        "sub_within_10": "K",
        "count_to_20": "K",
        "count_to_100": "K",
        "compare_groups": "K",
        "compare_numbers_20": "K",
        "one_more_one_less": "K",
        "skip_count_10": "K",
        "teen_numbers": "K",
        "pairs_to_10": "K",
        "add_within_20": "1",
        "sub_within_20": "1",
        "place_value_tens_ones": "1",
        "place_value_hundreds": "2",
        "compare_numbers_100": "1",
        "add_2digit_no_regroup": "2",
        "add_2digit_regroup": "2",
        "equivalent_fractions": "3",
        "add_fractions_unlike": "5",
    }
    for skill in pack.skills.values():
        assert skill.generator == skill.id
        assert len(skill.tiers) == len(all_generators()[skill.generator].tier_difficulties)


def test_slot_lists_are_big_enough() -> None:
    assert len(SLOTS.names) >= 40
    assert len(SLOTS.objects) >= 40
    assert SLOTS.length_units and SLOTS.time_units and SLOTS.money_units and SLOTS.contexts


def _mutated(path: list[str | int], value: Any) -> dict[str, Any]:
    files = copy.deepcopy(_base())
    node: Any = files
    for step in path[:-1]:
        node = node[step]
    if value is _DELETE:
        del node[path[-1]]
    else:
        node[path[-1]] = value
    return files


_DELETE = object()

INVALID: list[tuple[str, dict[str, Any], str]] = [
    (
        "missing field",
        _mutated(["skills.yaml", "skills", 0, "generator"], _DELETE),
        "skills.yaml: skills[0].generator: Field required",
    ),
    (
        "unknown field",
        _mutated(["lessons/alpha.yaml", "try_it", "seed"], 3),
        "lessons/alpha.yaml: try_it.seed: Extra inputs are not permitted",
    ),
    (
        "bad slot type",
        _mutated(["word_problems/alpha.yaml", "templates", 0, "slots", "obj"], "animals"),
        "word_problems/alpha.yaml: templates[0].slots.obj: Input should be",
    ),
    (
        "unknown visual kind",
        _mutated(["lessons/alpha.yaml", "screens", 1, "visual", "kind"], "pie_chart"),
        "lessons/alpha.yaml: screens[1].visual: Input tag 'pie_chart' found using 'kind'",
    ),
    (
        "unknown visual param",
        _mutated(["lessons/alpha.yaml", "screens", 1, "visual", "params", "colour"], "gold"),
        "lessons/alpha.yaml: screens[1].visual.number_line.params.colour: Extra inputs",
    ),
    (
        "visual param out of range",
        _mutated(["lessons/alpha.yaml", "screens", 1, "visual", "params", "start"], 99),
        "lessons/alpha.yaml: screens[1].visual.number_line.params: Value error, start must be",
    ),
    (
        "unknown keypad",
        _mutated(["skills.yaml", "skills", 1, "keypad"], "numbers"),
        "skills.yaml: skills[1].keypad: Input should be",
    ),
    (
        "bad grade band",
        _mutated(["skills.yaml", "skills", 0, "grade_band"], 9),
        "skills.yaml: skills[0].grade_band: Input should be",
    ),
    (
        "prerequisite to an unknown skill",
        _mutated(["skills.yaml", "skills", 1, "prerequisites"], ["alpha", "ghost"]),
        "skills.yaml: skills[1].prerequisites[1]: unknown skill ghost",
    ),
    (
        "cycle",
        _mutated(["skills.yaml", "skills", 0, "prerequisites"], ["beta"]),
        "skills.yaml: skills: prerequisite cycle: alpha -> beta -> alpha",
    ),
    (
        "unknown region",
        _mutated(["skills.yaml", "skills", 0, "region"], "moon"),
        "skills.yaml: skills[0].region: unknown region moon",
    ),
    (
        "duplicate skill",
        _mutated(["skills.yaml", "skills", 1, "id"], "alpha"),
        "skills.yaml: skills[1].id: duplicate skill id alpha",
    ),
    (
        "tier ids out of order",
        _mutated(["skills.yaml", "skills", 0, "tiers", 0, "id"], 2),
        "skills.yaml: skills[0]: Value error, tier ids must be 0, 1, 2",
    ),
    (
        "wrong hint count",
        _mutated(["hints/alpha.yaml", "levels"], [{"text_template": "Look."}] * 2),
        "hints/alpha.yaml: levels: Tuple should have at least 3 items",
    ),
    (
        "too many lesson screens",
        _mutated(["lessons/alpha.yaml", "screens"], [{"title": "x", "body_md": "y"}] * 5),
        "lessons/alpha.yaml: screens: Tuple should have at most 4 items",
    ),
    (
        "repeated approach style",
        _mutated(["explanations/alpha.yaml", "approaches", 2, "style"], "visual"),
        "explanations/alpha.yaml: (top level): Value error, duplicate approach style: visual",
    ),
    (
        "choice index out of range",
        _mutated(["bank/beta.yaml", "items", 0, "answer", "value"], 3),
        "bank/beta.yaml: items[0]: Value error, choice index 3 is out of range",
    ),
    (
        "visual parameter that is not a template",
        _mutated(["lessons/alpha.yaml", "screens", 1, "visual", "params", "start"], "{oops"),
        "lessons/alpha.yaml: screens[1].visual.number_line.params.start: "
        "Value error, stray '{' in text",
    ),
    (
        "only two choices",
        _mutated(
            ["bank/beta.yaml", "items", 0, "choices"],
            [[{"kind": "math", "value": "3"}], [{"kind": "math", "value": "7"}]],
        ),
        "bank/beta.yaml: items[0]: Value error, a choice answer needs at least 3 choices",
    ),
    (
        "expr answer that does not parse",
        _mutated(["bank/beta.yaml", "items", 1, "answer", "value"], r"\sin x"),
        "bank/beta.yaml: items[1]: Value error, answer does not parse",
    ),
    (
        r"\text in a math part",
        _mutated(
            ["bank/beta.yaml", "items", 0, "prompt"], [{"kind": "math", "value": r"\text{hi}"}]
        ),
        "bank/beta.yaml: items[0].prompt[0]: Value error, words belong in a text part",
    ),
    (
        "boss skill unknown",
        _mutated(["world.yaml", "regions", 0, "boss_skill_set"], ["ghost"]),
        "world.yaml: regions[0].boss_skill_set[0]: unknown skill ghost",
    ),
    (
        "bad version",
        _mutated(["pack.yaml", "version"], "1.0"),
        "pack.yaml: version: String should match pattern",
    ),
    (
        "complete region missing content",
        _mutated(["pack.yaml", "complete_regions"], ["meadow"]),
        "pack.yaml: complete_regions[0]: region meadow is declared complete but beta has no lesson",
    ),
    (
        "unknown complete region",
        _mutated(["pack.yaml", "complete_regions"], ["moon"]),
        "pack.yaml: complete_regions[0]: unknown region moon",
    ),
    (
        "try_it tier past the skill's tiers",
        _mutated(["lessons/alpha.yaml", "try_it", "tier"], 3),
        "lessons/alpha.yaml: try_it.tier: skill alpha has only 3 tiers",
    ),
    (
        "word problems for a skill they do not fit",
        _mutated(["skills.yaml", "skills", 0, "word_problems_fit"], False),
        "word_problems/alpha.yaml: skill: alpha has word_problems_fit: false",
    ),
    (
        "bank item tier beyond the skill's tiers",
        _mutated(["bank/beta.yaml", "items", 0, "tier"], 5),
        "bank/beta.yaml: items[0].tier: skill beta has only 3 tiers",
    ),
    (
        "bank for a skill that is not banked",
        _mutated(["skills.yaml", "skills", 1, "banked"], False),
        "bank/beta.yaml: skill: beta has banked: false",
    ),
    (
        "shares above one",
        _mutated(["skills.yaml", "skills", 1, "word_share"], 0.9),
        "skills.yaml: skills[1]: Value error, word_share + bank_share must not exceed 1",
    ),
]


@pytest.mark.parametrize(("case", "files", "message"), INVALID, ids=[c[0] for c in INVALID])
def test_invalid_pack_names_file_and_path(
    tmp_path: Path, case: str, files: dict[str, Any], message: str
) -> None:
    with pytest.raises(ContentError) as exc:
        _load(tmp_path, files)
    assert message in str(exc.value), case


def test_file_for_unknown_skill(tmp_path: Path) -> None:
    files = _base()
    files["hints/gamma.yaml"] = {**files["hints/alpha.yaml"], "skill": "gamma"}
    with pytest.raises(ContentError, match=r"^hints/gamma\.yaml: skill: unknown skill gamma$"):
        _load(tmp_path, files)


def test_file_name_must_match_skill(tmp_path: Path) -> None:
    files = _base()
    files["hints/beta.yaml"] = files["hints/alpha.yaml"]
    with pytest.raises(
        ContentError, match=r"^hints/beta\.yaml: skill: alpha does not match the file name$"
    ):
        _load(tmp_path, files)


def test_missing_world_file(tmp_path: Path) -> None:
    files = _base()
    del files["world.yaml"]
    with pytest.raises(ContentError, match=r"^world\.yaml: file is missing$"):
        _load(tmp_path, files)


def test_broken_yaml_names_the_file(tmp_path: Path) -> None:
    pack = _write(tmp_path, _base())
    (pack / "lessons" / "alpha.yaml").write_text("skill: [alpha\n", encoding="utf-8")
    with pytest.raises(ContentError, match=r"^lessons/alpha\.yaml: cannot read"):
        load_pack(pack)


def test_pack_id_must_match_directory(tmp_path: Path) -> None:
    files = _mutated(["pack.yaml", "id"], "other-pack")
    with pytest.raises(ContentError, match=r"pack\.yaml: id: other-pack does not match"):
        _load(tmp_path, files)


def test_choice_keypad_needs_a_full_choice_bank(tmp_path: Path) -> None:
    files = _mutated(["skills.yaml", "skills", 1, "keypad"], "choice")
    with pytest.raises(ContentError, match=r"skills\.yaml: skills\[1\]\.keypad: a choice keypad"):
        _load(tmp_path, files)


@pytest.mark.parametrize("profile", list(KEYPAD_PROFILES))
def test_every_keypad_profile_loads(tmp_path: Path, profile: str) -> None:
    files = _base()
    files["skills.yaml"]["skills"][0]["keypad"] = profile
    if profile == "choice":
        files["skills.yaml"]["skills"][0].update(
            banked=True, bank_share=1.0, word_problems_fit=False, word_share=0.0
        )
        del files["word_problems/alpha.yaml"]
        files["bank/alpha.yaml"] = {**files["bank/beta.yaml"], "skill": "alpha"}
        files["bank/alpha.yaml"]["items"] = files["bank/alpha.yaml"]["items"][:1]
    assert _load(tmp_path, files).skills["alpha"].keypad == profile


def test_unknown_generator_fails_binding(tmp_path: Path) -> None:
    files = _mutated(["skills.yaml", "skills", 1, "generator"], "no_such_generator")
    pack = _load(tmp_path, files)
    with pytest.raises(
        ContentError, match=r"^skills\.yaml: skills\[1\]\.generator: unknown generator"
    ):
        build_catalog(pack, SLOTS)


def test_tier_count_must_match_generator(tmp_path: Path) -> None:
    files = _mutated(
        ["skills.yaml", "skills", 0, "tiers"], [{"id": i, "label": "x"} for i in range(4)]
    )
    pack = _load(tmp_path, files)
    with pytest.raises(ContentError, match=r"skills\[0\]\.tiers: 4 tiers declared"):
        build_catalog(pack, SLOTS)


def test_misconception_feedback_must_name_a_generator_key(tmp_path: Path) -> None:
    files = _mutated(
        ["explanations/alpha.yaml", "misconceptions"], {"forgot_carry": "Carry the ten."}
    )
    pack = _load(tmp_path, files)
    with pytest.raises(
        ContentError, match=r"^explanations/alpha\.yaml: misconceptions\.forgot_carry: generator"
    ):
        build_catalog(pack, SLOTS)


def test_slots_need_forty_names(tmp_path: Path) -> None:
    data = yaml.safe_load((CONTENT / "slots.yaml").read_text(encoding="utf-8"))
    data["names"] = data["names"][:39]
    path = tmp_path / "slots.yaml"
    path.write_text(yaml.safe_dump(data), encoding="utf-8")
    with pytest.raises(ContentError, match=r"^slots\.yaml: names: Tuple should have at least 40"):
        load_slots(path)


def test_repeated_name_rejected(tmp_path: Path) -> None:
    data = yaml.safe_load((CONTENT / "slots.yaml").read_text(encoding="utf-8"))
    data["names"].append(data["names"][0])
    path = tmp_path / "slots.yaml"
    path.write_text(yaml.safe_dump(data), encoding="utf-8")
    with pytest.raises(ContentError, match="duplicate name"):
        load_slots(path)


def test_bank_answer_must_be_in_the_skill_form(tmp_path: Path) -> None:
    files = _mutated(["bank/beta.yaml", "items", 1, "answer", "value"], r"\frac{8}{2}")
    pack = _load(tmp_path, files)
    with pytest.raises(
        ContentError, match=r"^bank/beta\.yaml: items\[1\]\.answer\.value: not in the skill's"
    ):
        build_catalog(pack, SLOTS)
