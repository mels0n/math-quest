"""Admin password check and server-side admin sessions.

The password is hashed once at boot with the same argon2 parameters as player credentials;
only the hash is kept. Sessions are random 32-byte tokens stored as SHA-256 with an expiry.
"""

import asyncio
import secrets
from datetime import UTC, datetime, timedelta

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError
from sqlalchemy.ext.asyncio import AsyncSession

from mathquest.entities import admin
from mathquest.features.admin.schema import AdminLogin, AdminSessionOut
from mathquest.shared.errors import Unauthorized

SESSION_TTL = timedelta(hours=8)

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
    """Verify the password and open a session; raises Unauthorized on any mismatch."""
    if not await _verify(stored_hash, password):
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
