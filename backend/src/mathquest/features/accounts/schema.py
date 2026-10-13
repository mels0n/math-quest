"""Value objects returned by the accounts service (never database rows)."""

import uuid

from pydantic import BaseModel, ConfigDict


class _Frozen(BaseModel):
    model_config = ConfigDict(frozen=True)


class PlayerOut(_Frozen):
    id: uuid.UUID
    nickname: str


class SignupResult(_Frozen):
    player_id: uuid.UUID
    device_token: str
    recovery_word: str


class LoginResult(_Frozen):
    player_id: uuid.UUID
    device_token: str
