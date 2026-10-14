"""Admin password check and server-side admin sessions.

The password is hashed once at boot with the same argon2 parameters as player credentials;
only the hash is kept. Sessions are random 32-byte tokens stored as SHA-256 with an expiry.
"""

import asyncio
import logging
import re
import secrets
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError
from sqlalchemy.exc import DBAPIError, IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from mathquest.entities import admin, credentials, lockouts, players
from mathquest.entities.models import Player
from mathquest.features.admin.schema import AdminLogin, AdminSessionOut, PinReset, PlayerAdminOut
from mathquest.shared.errors import Conflict, Invalid, NotFound, Unauthorized

SESSION_TTL = timedelta(hours=8)
MAX_PAGE = 100
DELETE_ATTEMPTS = 2
DEADLOCK_DETECTED = "40P01"
_SIGNUP_WORD_RE = re.compile(r"[A-Za-z]{3,32}")

log = logging.getLogger(__name__)

_hasher = PasswordHasher(memory_cost=19456, time_cost=2, parallelism=1)


def utcnow() -> datetime:
    return datetime.now(UTC)


async def hash_password(password: str) -> str:
    return await asyncio.to_thread(_hasher.hash, password)


async def _verify(stored_hash: str, password: str) -> bool:
    def check() -> bool:
        try:
            return _hasher.verify(stored_hash, password)
        except (VerificationError, InvalidHashError):
            return False

    return await asyncio.to_thread(check)


async def login(db: AsyncSession, *, stored_hash: str, password: str) -> AdminLogin:
    """Verify the password and open a session; raises Unauthorized on any mismatch.

    A mismatch is audited (no password, no session) and logged before the error is raised.
    """
    if not await _verify(stored_hash, password):
        await admin.audit(db, action="login_failed", admin_session_id=None)
        await db.commit()
        log.warning("admin login failed")
        raise Unauthorized()
    now = utcnow()
    await admin.delete_expired(db, now)
    token = secrets.token_urlsafe(32)
    row = await admin.add_session(db, token=token, created_at=now, expires_at=now + SESSION_TTL)
    await admin.audit(db, action="login", admin_session_id=row.id)
    await db.commit()
    return AdminLogin(session_id=row.id, token=token)


async def session_for_token(db: AsyncSession, token: str) -> AdminSessionOut | None:
    """The unexpired session for a cookie token, or None."""
    row = await admin.live_session(db, token, utcnow())
    return None if row is None else AdminSessionOut(id=row.id)


async def logout(db: AsyncSession, token: str) -> None:
    """Delete the session the token names, if any, and record it."""
    row = await admin.session_by_token(db, token)
    if row is None:
        return
    await admin.audit(db, action="logout", admin_session_id=row.id)
    await admin.delete_session(db, row.id)
    await db.commit()


async def _player(db: AsyncSession, player_id: uuid.UUID) -> Player:
    player = await players.get_by_id(db, player_id)
    if player is None:
        raise NotFound()
    return player


async def _audit(
    db: AsyncSession,
    action: str,
    session_id: uuid.UUID,
    player: Player | None = None,
    detail: str | None = None,
) -> None:
    """One audit row per action; target_nickname is the nickname before the action."""
    await admin.audit(
        db,
        action=action,
        admin_session_id=session_id,
        player_id=None if player is None else player.id,
        target_nickname=None if player is None else player.nickname,
        detail=detail,
    )


async def list_players(
    db: AsyncSession, *, query: str | None = None, offset: int = 0, limit: int = 50
) -> list[PlayerAdminOut]:
    rows = await players.list_page(
        db, query=query, offset=max(0, offset), limit=max(1, min(limit, MAX_PAGE))
    )
    return [
        PlayerAdminOut(
            id=p.id,
            nickname=p.nickname,
            hidden=p.hidden,
            created_at=p.created_at,
            last_seen=seen,
        )
        for p, seen in rows
    ]


async def set_hidden(
    db: AsyncSession, session_id: uuid.UUID, player_id: uuid.UUID, hidden: bool
) -> None:
    player = await _player(db, player_id)
    await players.set_hidden(db, player, hidden)
    await _audit(db, "hide" if hidden else "unhide", session_id, player)
    await db.commit()


async def rename(
    db: AsyncSession,
    session_id: uuid.UUID,
    player_id: uuid.UUID,
    nickname: str,
    *,
    blocklist: frozenset[str] | None = None,
) -> None:
    """Apply the signup nickname rules; Conflict if another player holds the name."""
    player = await _player(db, player_id)
    await credentials.check_nickname_available(db, nickname, blocklist=blocklist, owner=player.id)
    old_nickname = player.nickname
    try:
        async with db.begin_nested():
            await players.rename(db, player, nickname)
    except IntegrityError:
        raise Conflict("nickname_taken") from None
    await admin.audit(
        db,
        action="rename",
        admin_session_id=session_id,
        player_id=player.id,
        target_nickname=old_nickname,
        detail=nickname,
    )
    await db.commit()


async def reset_pin(
    db: AsyncSession,
    session_id: uuid.UUID,
    player_id: uuid.UUID,
    pin: str,
    *,
    content_dir: Path | None = None,
) -> PinReset:
    """Set a new PIN, rotate the recovery word, sign the player out everywhere and lift locks.

    Holds the player's row lock like a login attempt does, so the stored recovery hash it
    compares against cannot change underneath it.
    """
    player = await _player(db, player_id)
    if not await lockouts.lock_player(db, player.id):
        raise NotFound()
    await db.refresh(player)
    word = await credentials.replace_credentials(
        db, player, pin=pin, picture=None, content_dir=content_dir
    )
    await lockouts.clear_all(db, player.id)
    player.recovery_locked_until = None
    await _audit(db, "reset_pin", session_id, player)
    await db.commit()
    return PinReset(recovery_word=word)


async def delete_player(db: AsyncSession, session_id: uuid.UUID, player_id: uuid.UUID) -> None:
    """Delete the player and all their rows.

    The delete cascades into rows an in-flight answer or problem request may be holding
    while it waits on the player row, so the database can pick the delete as a deadlock
    victim (SQLSTATE 40P01). The work runs in a savepoint and is retried once; a second
    deadlock is reported as Conflict("busy").
    """
    player = await _player(db, player_id)
    nickname = player.nickname
    for attempt in range(DELETE_ATTEMPTS):
        try:
            async with db.begin_nested():
                await admin.audit(
                    db,
                    action="delete",
                    admin_session_id=session_id,
                    player_id=player_id,
                    target_nickname=nickname,
                )
                await players.delete_player(db, player_id)
            break
        except DBAPIError as exc:
            if getattr(exc.orig, "sqlstate", None) != DEADLOCK_DETECTED:
                raise
            if attempt == DELETE_ATTEMPTS - 1:
                raise Conflict("busy") from None
    await db.commit()


async def signup_word_is_set(db: AsyncSession) -> bool:
    return await credentials.signup_word_is_set(db)


async def set_signup_word(db: AsyncSession, session_id: uuid.UUID, word: str) -> None:
    if _SIGNUP_WORD_RE.fullmatch(word) is None:
        raise Invalid("signup_word")
    await credentials.set_signup_word(db, word)
    await _audit(db, "signup_word", session_id)
    await db.commit()
