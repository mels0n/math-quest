"""Admin sessions and the admin audit log. Only the SHA-256 of a session token is stored.

`admin_audit.admin_session_id` has no foreign key: the row must outlive the session it names.
"""

import hashlib
import uuid
from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, Index, Text, delete, func, select
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Mapped, mapped_column

from mathquest.shared.db import Base


class AdminSession(Base):
    __tablename__ = "admin_sessions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    token_hash: Mapped[str] = mapped_column(Text, unique=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class AdminAudit(Base):
    __tablename__ = "admin_audit"
    __table_args__ = (Index("ix_admin_audit_at", "at"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    admin_session_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    action: Mapped[str] = mapped_column(Text)
    player_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("players.id", ondelete="SET NULL"), nullable=True
    )
    target_nickname: Mapped[str | None] = mapped_column(Text, nullable=True)
    at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


async def add_session(
    db: AsyncSession, *, token: str, created_at: datetime, expires_at: datetime
) -> AdminSession:
    row = AdminSession(token_hash=hash_token(token), created_at=created_at, expires_at=expires_at)
    db.add(row)
    await db.flush()
    return row


async def live_session(db: AsyncSession, token: str, now: datetime) -> AdminSession | None:
    result = await db.execute(
        select(AdminSession).where(
            AdminSession.token_hash == hash_token(token), AdminSession.expires_at > now
        )
    )
    return result.scalar_one_or_none()


async def session_by_token(db: AsyncSession, token: str) -> AdminSession | None:
    result = await db.execute(
        select(AdminSession).where(AdminSession.token_hash == hash_token(token))
    )
    return result.scalar_one_or_none()


async def delete_session(db: AsyncSession, session_id: uuid.UUID) -> None:
    await db.execute(delete(AdminSession).where(AdminSession.id == session_id))


async def delete_expired(db: AsyncSession, now: datetime) -> None:
    await db.execute(delete(AdminSession).where(AdminSession.expires_at <= now))


async def audit(
    db: AsyncSession,
    *,
    action: str,
    admin_session_id: uuid.UUID | None,
    player_id: uuid.UUID | None = None,
    target_nickname: str | None = None,
) -> None:
    db.add(
        AdminAudit(
            admin_session_id=admin_session_id,
            action=action,
            player_id=player_id,
            target_nickname=target_nickname,
        )
    )
    await db.flush()
