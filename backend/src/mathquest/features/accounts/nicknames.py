"""Nickname rules: shape, blocklist and generated suggestions."""

import random
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import yaml

from mathquest.entities.credentials import (
    NICKNAME_RE,
    default_blocklist,
    load_blocklist,
    nickname_allowed,
    nickname_valid,
)
from mathquest.shared.config import default_content_dir

__all__ = [
    "NICKNAME_RE",
    "NicknameWords",
    "default_blocklist",
    "default_nickname_words",
    "load_blocklist",
    "load_nickname_words",
    "nickname_allowed",
    "nickname_valid",
    "suggest_nickname",
]


@dataclass(frozen=True)
class NicknameWords:
    adjectives: tuple[str, ...]
    animals: tuple[str, ...]


def load_nickname_words(content_dir: Path) -> NicknameWords:
    data = yaml.safe_load((content_dir / "nicknames.yaml").read_text(encoding="utf-8"))
    return NicknameWords(
        adjectives=tuple(str(w) for w in data["adjectives"]),
        animals=tuple(str(w) for w in data["animals"]),
    )


@lru_cache
def default_nickname_words() -> NicknameWords:
    return load_nickname_words(default_content_dir())


def suggest_nickname(rng: random.Random, words: NicknameWords | None = None) -> str:
    """`<Adjective><Animal><2 digits>`."""
    pool = words or default_nickname_words()
    return f"{rng.choice(pool.adjectives)}{rng.choice(pool.animals)}{rng.randrange(100):02d}"
