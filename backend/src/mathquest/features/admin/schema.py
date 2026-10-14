"""Value objects returned by the admin service (never database rows)."""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class _Frozen(BaseModel):
    model_config = ConfigDict(frozen=True)


class AdminSessionOut(_Frozen):
    id: uuid.UUID


class AdminLogin(_Frozen):
    session_id: uuid.UUID
    token: str


class PlayerAdminOut(_Frozen):
    id: uuid.UUID
    nickname: str
    hidden: bool
    created_at: datetime
    last_seen: datetime | None


class PinReset(_Frozen):
    recovery_word: str
