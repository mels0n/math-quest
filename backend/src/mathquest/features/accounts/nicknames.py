"""Nickname rules: shape, blocklist and generated suggestions."""

import random
import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import yaml

from mathquest.shared.config import default_content_dir

NICKNAME_RE = re.compile(r"[A-Za-z0-9 _-]{3,16}")
_NON_LETTERS = re.compile(r"[^a-z]")


@dataclass(frozen=True)
class NicknameWords:
    adjectives: tuple[str, ...]
    animals: tuple[str, ...]


def load_blocklist(content_dir: Path) -> frozenset[str]:
    """Lowercase blocked words from `blocklist.txt`; `#` lines are comments."""
    lines = (content_dir / "blocklist.txt").read_text(encoding="utf-8").splitlines()
    return frozenset(
        word for line in lines if (word := line.strip().lower()) and not word.startswith("#")
    )


def load_nickname_words(content_dir: Path) -> NicknameWords:
    data = yaml.safe_load((content_dir / "nicknames.yaml").read_text(encoding="utf-8"))
    return NicknameWords(
        adjectives=tuple(str(w) for w in data["adjectives"]),
        animals=tuple(str(w) for w in data["animals"]),
    )


@lru_cache
def default_blocklist() -> frozenset[str]:
    return load_blocklist(default_content_dir())


@lru_cache
def default_nickname_words() -> NicknameWords:
    return load_nickname_words(default_content_dir())


def nickname_valid(nickname: str) -> bool:
    """3-16 characters of letters, digits, space, underscore or hyphen; no edge spaces."""
    return NICKNAME_RE.fullmatch(nickname) is not None and nickname == nickname.strip()


def nickname_allowed(nickname: str, blocklist: frozenset[str]) -> bool:
    """False when the letters of the nickname contain any blocked word."""
    letters = _NON_LETTERS.sub("", nickname.lower())
    return not any(word in letters for word in blocklist)


def suggest_nickname(rng: random.Random, words: NicknameWords | None = None) -> str:
    """`<Adjective><Animal><2 digits>`."""
    pool = words or default_nickname_words()
    return f"{rng.choice(pool.adjectives)}{rng.choice(pool.animals)}{rng.randrange(100):02d}"
