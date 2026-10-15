"""Build small content packs in a temporary directory for lint and coverage tests."""

import copy
from pathlib import Path
from typing import Any

import yaml

from mathquest.engine.content import Pack, load_pack, load_slots
from mathquest.engine.content.lint import load_word_list

CONTENT = Path(__file__).resolve().parents[3] / "content"
SLOTS = load_slots(CONTENT / "slots.yaml")
WORDS = load_word_list(CONTENT / "lint" / "k2_words.txt")


def base() -> dict[str, Any]:
    """A small pack that lints clean, as file name -> YAML data."""
    return copy.deepcopy(_BASE)


def write(root: Path, files: dict[str, Any]) -> Path:
    pack = root / "lint-pack"
    for rel, data in files.items():
        path = pack / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")
    return pack


def load(root: Path, files: dict[str, Any]) -> Pack:
    return load_pack(write(root, files))


_BASE: dict[str, Any] = {
    "pack.yaml": {"id": "lint-pack", "title": "Lint", "version": "1.0.0"},
    "world.yaml": {
        "regions": [
            {
                "id": "meadow",
                "name": "Meadow",
                "order": 1,
                "creature_family": "family_a",
                "map_hint": "Grass.",
            }
        ]
    },
    "skills.yaml": {
        "skills": [
            {
                "id": "alpha",
                "name": "Add Them",
                "region": "meadow",
                "prerequisites": [],
                "fluency": True,
                "anchor": False,
                "generator": "add_within_20",
                "tiers": [{"id": i, "label": f"Tier {i}"} for i in range(3)],
                "grade_band": "1",
                "keypad": "numpad",
                "word_problems_fit": True,
                "banked": True,
            }
        ]
    },
    "lessons/alpha.yaml": {
        "skill": "alpha",
        "screens": [
            {"title": "Put together", "body_md": r"Adding puts two groups together. \(3 + 2\)."},
            {"title": "Count on", "body_md": "Start at 3. Count on 2. You get {{= 3 + 2 }}."},
        ],
        "worked_example": {
            "prompt": [{"kind": "math", "value": "4 + 2 = ?"}],
            "steps": ["Start at 4.", "Count on 2 to get {{= 4 + 2 }}."],
        },
        "try_it": {"tier": 0},
    },
    "hints/alpha.yaml": {
        "skill": "alpha",
        "levels": [
            {"text_template": "Put {a} and {b} together."},
            {"text_template": "Start at {a}. Count on {b}."},
            {"text_template": r"You land on {{= a + b }}. So \({a} + {b} = {{= a + b }}\)."},
        ],
    },
    "explanations/alpha.yaml": {
        "skill": "alpha",
        "approaches": [
            {"style": "visual", "body_md": "Picture a number line. Jump from {a} to the right."},
            {"style": "steps", "body_md": "1. Say the bigger number.\n2. Count on the other one."},
            {"style": "story", "body_md": "{a} ducks swim. {b} more ducks come. How many now?"},
        ],
        "misconceptions": {"subtracted_instead": "It looks like you took away. Put them together."},
    },
    "word_problems/alpha.yaml": {
        "skill": "alpha",
        "templates": [
            {
                "id": "gives_more",
                "text_template": "{name} has {a} {obj}. {friend} gives {b} more. How many now?",
                "slots": {"name": "names", "friend": "names", "obj": "objects"},
                "grade_band": 1,
            },
            {
                "id": "birds",
                "text_template": "{a} birds sit on a fence. {b} birds land. How many birds?",
                "grade_band": 1,
            },
            {
                "id": "pages",
                "text_template": "A book has {a} pages and {b} pictures. How much is {a} and {b}?",
                "answer_from": "expression",
                "expression": "a + b",
                "grade_band": 1,
            },
        ],
    },
    "bank/alpha.yaml": {
        "skill": "alpha",
        "items": [
            {
                "id": "bigger",
                "prompt": [{"kind": "text", "value": "Which number is bigger?"}],
                "answer": {"kind": "choice", "value": 1},
                "choices": [[{"kind": "math", "value": "3"}], [{"kind": "math", "value": "7"}]],
            },
            {
                "id": "double",
                "prompt": [{"kind": "text", "value": "What is double six?"}],
                "answer": {"kind": "expr", "value": "12"},
            },
        ],
    },
}
