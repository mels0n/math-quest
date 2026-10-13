"""Signup, login, recovery and device tokens.

Failed logins and recovery guesses share one counter per (player, device key, ip).
Five failures within 60 seconds lock that triple for 30 minutes; other devices, other
addresses and other players are unaffected.
"""

import asyncio
import math
import re
import secrets
import uuid
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime, timedelta
from functools import lru_cache
from pathlib import Path
from typing import NoReturn

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from mathquest.entities import devices, lockouts, players
from mathquest.entities.models import Player
from mathquest.entities.settings import get_setting, set_setting
from mathquest.features.accounts import nicknames
from mathquest.features.accounts.schema import (
    LoginResult,
    PlayerOut,
    RecoverResult,
    SignupResult,
)
from mathquest.shared.config import default_content_dir
from mathquest.shared.errors import Conflict, Invalid, Locked, Unauthorized

SIGNUP_WORD_KEY = "signup_word_hash"
FAILURE_LIMIT = 5
FAILURE_WINDOW = timedelta(seconds=60)
LOCK_DURATION = timedelta(minutes=30)
# Rotating device keys from one address is capped separately: failures for a
# (player, ip) across every device key lock that pair under the sentinel key.
IP_FAILURE_LIMIT = 15
IP_FAILURE_WINDOW = timedelta(minutes=10)
FAILURE_RETENTION = timedelta(hours=1)
PICTURE_COUNT = 12
PICTURE_LENGTH = 4

_PIN_RE = re.compile(r"[0-9]{4}")
_hasher = PasswordHasher(memory_cost=19456, time_cost=2, parallelism=1)
_DUMMY_HASH = _hasher.hash("dummy-secret")

Clock = Callable[[], datetime]


def utcnow() -> datetime:
    return datetime.now(UTC)


async def _hash(secret: str) -> str:
    return await asyncio.to_thread(_hasher.hash, secret)


async def _verify(stored: str | None, secret: str) -> bool:
    def check() -> bool:
        try:
            if stored is None:
                _hasher.verify(_DUMMY_HASH, secret)
                return False
            return _hasher.verify(stored, secret)
        except (VerificationError, InvalidHashError):
            return False

    return await asyncio.to_thread(check)


def _picture_secret(picture: list[int]) -> str:
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


def _require_one_credential(pin: str | None, picture: list[int] | None) -> None:
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


def _normalize_recovery(word: str) -> str:
    return word.strip().lower()


async def seed_signup_word(db: AsyncSession, word: str | None) -> None:
    """Store the signup word's hash when none exists yet; never overwrites."""
    if word is None or await get_setting(db, SIGNUP_WORD_KEY) is not None:
        return
    await set_setting(db, SIGNUP_WORD_KEY, await _hash(word))
    await db.commit()


async def signup(
    db: AsyncSession,
    *,
    signup_word: str,
    nickname: str,
    pin: str | None,
    picture: list[int] | None,
    blocklist: frozenset[str] | None = None,
    content_dir: Path | None = None,
) -> SignupResult:
    if not await _verify(await get_setting(db, SIGNUP_WORD_KEY), signup_word):
        raise Invalid("signup_word")
    _require_one_credential(pin, picture)
    if not nicknames.nickname_valid(nickname):
        raise Invalid("nickname")
    words = blocklist if blocklist is not None else nicknames.default_blocklist()
    if not nicknames.nickname_allowed(nickname, words):
        raise Invalid("nickname_blocked")
    if await players.get_by_nickname(db, nickname) is not None:
        raise Conflict("nickname_taken")

    recovery_word = secrets.choice(load_recovery_words(content_dir or default_content_dir()))
    pin_hash = await _hash(pin) if pin is not None else None
    picture_hash = await _hash(_picture_secret(picture)) if picture is not None else None
    recovery_hash = await _hash(recovery_word)
    try:
        async with db.begin_nested():
            player = await players.add(
                db,
                nickname=nickname,
                pin_hash=pin_hash,
                picture_hash=picture_hash,
                recovery_hash=recovery_hash,
            )
    except IntegrityError:
        raise Conflict("nickname_taken") from None
    token = await _issue_token(db, player.id)
    await db.commit()
    return SignupResult(player_id=player.id, device_token=token, recovery_word=recovery_word)


async def _issue_token(db: AsyncSession, player_id: uuid.UUID) -> str:
    token = secrets.token_urlsafe(32)
    await devices.add(db, player_id=player_id, token=token)
    return token


async def _attempt(
    db: AsyncSession,
    player: Player,
    *,
    device_key: str,
    ip: str,
    now: Clock,
    verify: Callable[[], Awaitable[bool]],
) -> None:
    """Run one credential check under the lockouts.

    Everything happens while holding a row lock on the player, so parallel attempts
    queue up and each sees the failures recorded by the ones before it. Locks are
    per (player, device key, ip), plus one per (player, ip) across all device keys.
    """
    if device_key == lockouts.ANY_DEVICE:
        raise Invalid("device_key")
    await lockouts.lock_player(db, player.id)
    await db.refresh(player)
    moment = now()
    await lockouts.delete_failures_before(db, player.id, moment - FAILURE_RETENTION)
    until = await lockouts.active_lockout_until(db, player.id, device_key, ip, moment)
    if until is not None:
        await db.commit()
        raise Locked(max(1, math.ceil((until - moment).total_seconds())))
    if await verify():
        await lockouts.clear_failures(db, player.id, device_key, ip)
        return
    await lockouts.record_failure(db, player.id, device_key, ip, moment)
    recent = await lockouts.count_failures_since(
        db, player.id, device_key, ip, moment - FAILURE_WINDOW
    )
    if recent >= FAILURE_LIMIT:
        await lockouts.set_lockout(db, player.id, device_key, ip, moment + LOCK_DURATION)
    recent_any = await lockouts.count_failures_since(
        db, player.id, None, ip, moment - IP_FAILURE_WINDOW
    )
    if recent_any >= IP_FAILURE_LIMIT:
        await lockouts.set_lockout(db, player.id, lockouts.ANY_DEVICE, ip, moment + LOCK_DURATION)
    await db.commit()
    raise Unauthorized()


async def _reject_unknown(secret: str) -> NoReturn:
    """Spend a verify's worth of time so unknown nicknames are not distinguishable."""
    await _verify(None, secret)
    raise Unauthorized()


async def login(
    db: AsyncSession,
    *,
    nickname: str,
    pin: str | None = None,
    picture: list[int] | None = None,
    device_key: str,
    ip: str,
    now: Clock = utcnow,
) -> LoginResult:
    _require_one_credential(pin, picture)
    if pin is not None:
        secret = pin
    else:
        assert picture is not None
        secret = _picture_secret(picture)
    player = await players.get_by_nickname(db, nickname)
    if player is None or player.hidden:
        await _reject_unknown(secret)
    await _attempt(
        db,
        player,
        device_key=device_key,
        ip=ip,
        now=now,
        verify=lambda: _verify(player.pin_hash if pin is not None else player.picture_hash, secret),
    )
    token = await _issue_token(db, player.id)
    await db.commit()
    return LoginResult(player_id=player.id, device_token=token)


async def recover(
    db: AsyncSession,
    *,
    nickname: str,
    recovery_word: str,
    new_pin: str | None = None,
    new_picture: list[int] | None = None,
    device_key: str,
    ip: str,
    now: Clock = utcnow,
    content_dir: Path | None = None,
) -> RecoverResult:
    """Replace the player's credentials and recovery word, revoke old devices, sign in."""
    _require_one_credential(new_pin, new_picture)
    secret = _normalize_recovery(recovery_word)
    player = await players.get_by_nickname(db, nickname)
    if player is None or player.hidden:
        await _reject_unknown(secret)
    await _attempt(
        db,
        player,
        device_key=device_key,
        ip=ip,
        now=now,
        verify=lambda: _verify(player.recovery_hash, secret),
    )
    new_word = secrets.choice(load_recovery_words(content_dir or default_content_dir()))
    player.pin_hash = await _hash(new_pin) if new_pin is not None else None
    player.picture_hash = (
        await _hash(_picture_secret(new_picture)) if new_picture is not None else None
    )
    player.recovery_hash = await _hash(new_word)
    await devices.revoke_all(db, player.id)
    token = await _issue_token(db, player.id)
    await db.commit()
    return RecoverResult(player_id=player.id, device_token=token, recovery_word=new_word)


async def player_for_token(db: AsyncSession, token: str, now: Clock = utcnow) -> PlayerOut | None:
    player = await devices.player_for_token(db, token, now())
    if player is None:
        return None
    return PlayerOut(id=player.id, nickname=player.nickname)
