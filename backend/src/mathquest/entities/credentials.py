"""Credential rules shared by every feature that sets or checks player secrets.

Argon2 hashing, the PIN and picture shapes, recovery words, nickname rules, and the one
routine that replaces a player's credentials. Feature slices import this module instead of
each other.
"""

import asyncio
import re
import secrets
import uuid
from functools import lru_cache
from pathlib import Path

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError
from sqlalchemy.ext.asyncio import AsyncSession

from mathquest.entities import devices, players
from mathquest.entities.models import Player
from mathquest.entities.settings import get_setting, set_setting
from mathquest.shared.config import default_content_dir
from mathquest.shared.errors import Conflict, Invalid

SIGNUP_WORD_KEY = "signup_word_hash"
PICTURE_COUNT = 12
PICTURE_LENGTH = 4

NICKNAME_RE = re.compile(r"[A-Za-z0-9 _-]{3,16}")
_NON_LETTERS = re.compile(r"[^a-z]")
_PIN_RE = re.compile(r"[0-9]{4}")

hasher = PasswordHasher(memory_cost=19456, time_cost=2, parallelism=1)
DUMMY_HASH = hasher.hash("dummy-secret")


async def hash_secret(secret: str) -> str:
    return await asyncio.to_thread(hasher.hash, secret)


async def verify_secret(stored: str | None, secret: str) -> bool:
    """Check a secret; a missing hash is verified against a dummy so timing matches."""

    def check() -> bool:
        try:
            if stored is None:
                hasher.verify(DUMMY_HASH, secret)
                return False
            return hasher.verify(stored, secret)
        except (VerificationError, InvalidHashError):
            return False

    return await asyncio.to_thread(check)


def picture_secret(picture: list[int]) -> str:
    return "-".join(str(i) for i in picture)


def _check_pin(pin: str) -> None:
    if _PIN_RE.fullmatch(pin) is None:
        raise Invalid("pin")


def _check_picture(picture: list[int]) -> None:
    ok = len(picture) == PICTURE_LENGTH and all(
        type(i) is int and 0 <= i < PICTURE_COUNT for i in picture
    )
    if not ok:
        raise Invalid("picture")


def require_one_credential(pin: str | None, picture: list[int] | None) -> None:
    if (pin is None) == (picture is None):
        raise Invalid("credential")
    if pin is not None:
        _check_pin(pin)
    if picture is not None:
        _check_picture(picture)


@lru_cache
def _recovery_words(content_dir: Path) -> tuple[str, ...]:
    lines = (content_dir / "recovery_words.txt").read_text(encoding="utf-8").splitlines()
    return tuple(word for line in lines if (word := line.strip().lower()))


def load_recovery_words(content_dir: Path) -> tuple[str, ...]:
    return _recovery_words(content_dir)


def load_blocklist(content_dir: Path) -> frozenset[str]:
    """Lowercase blocked words from `blocklist.txt`; `#` lines are comments."""
    lines = (content_dir / "blocklist.txt").read_text(encoding="utf-8").splitlines()
    return frozenset(
        word for line in lines if (word := line.strip().lower()) and not word.startswith("#")
    )


@lru_cache
def default_blocklist() -> frozenset[str]:
    return load_blocklist(default_content_dir())


def nickname_valid(nickname: str) -> bool:
    """3-16 characters of letters, digits, space, underscore or hyphen; no edge spaces."""
    return NICKNAME_RE.fullmatch(nickname) is not None and nickname == nickname.strip()


def nickname_allowed(nickname: str, blocklist: frozenset[str]) -> bool:
    """False when the letters of the nickname contain any blocked word."""
    letters = _NON_LETTERS.sub("", nickname.lower())
    return not any(word in letters for word in blocklist)


async def check_nickname_available(
    db: AsyncSession,
    nickname: str,
    *,
    blocklist: frozenset[str] | None = None,
    owner: uuid.UUID | None = None,
) -> None:
    """Raise unless `nickname` is well formed, allowed and free (or already `owner`'s)."""
    if not nickname_valid(nickname):
        raise Invalid("nickname")
    words = blocklist if blocklist is not None else default_blocklist()
    if not nickname_allowed(nickname, words):
        raise Invalid("nickname_blocked")
    existing = await players.get_by_nickname(db, nickname)
    if existing is not None and existing.id != owner:
        raise Conflict("nickname_taken")


async def set_signup_word(db: AsyncSession, word: str) -> None:
    """Replace the stored signup word hash; takes effect on the next signup."""
    await set_setting(db, SIGNUP_WORD_KEY, await hash_secret(word))


async def signup_word_is_set(db: AsyncSession) -> bool:
    return await get_setting(db, SIGNUP_WORD_KEY) is not None


async def replace_credentials(
    db: AsyncSession,
    player: Player,
    *,
    pin: str | None,
    picture: list[int] | None,
    old_word: str | None = None,
    content_dir: Path | None = None,
) -> str:
    """Set new credentials, rotate the recovery word and revoke every device.

    Returns the new recovery word, which is never the old one: excluded by value when the
    caller knows it, otherwise checked against the stored hash. Does not commit.
    """
    require_one_credential(pin, picture)
    words = load_recovery_words(content_dir or default_content_dir())
    if old_word is not None:
        new_word = secrets.choice([w for w in words if w != old_word])
    else:
        new_word = secrets.choice(words)
        while await verify_secret(player.recovery_hash, new_word):
            new_word = secrets.choice(words)
    player.pin_hash = await hash_secret(pin) if pin is not None else None
    player.picture_hash = (
        await hash_secret(picture_secret(picture)) if picture is not None else None
    )
    player.recovery_hash = await hash_secret(new_word)
    await devices.revoke_all(db, player.id)
    return new_word
