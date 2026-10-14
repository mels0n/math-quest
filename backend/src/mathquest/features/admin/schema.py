"""Value objects returned by the admin service (never database rows)."""

import uuid

from pydantic import BaseModel, ConfigDict


class _Frozen(BaseModel):
    model_config = ConfigDict(frozen=True)


class AdminSessionOut(_Frozen):
    id: uuid.UUID


class AdminLogin(_Frozen):
    session_id: uuid.UUID
    token: str
