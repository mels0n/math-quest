"""Signup, login, recovery, logout and the current player."""

import random

from fastapi import APIRouter, Depends, Request, Response
from pydantic import BaseModel, ConfigDict, Field

from mathquest.api.deps import (
    SESSION_COOKIE,
    AppSettings,
    ClientIp,
    CurrentPlayer,
    Db,
    DeviceKey,
    limit_auth,
    limit_signup,
    set_cookie,
)
from mathquest.features import accounts
from mathquest.features.accounts import PlayerOut
from mathquest.shared.errors import Unauthorized

router = APIRouter(prefix="/api")


class _In(BaseModel):
    model_config = ConfigDict(extra="forbid")


class SignupIn(_In):
    signup_word: str = Field(max_length=128)
    nickname: str = Field(max_length=64)
    pin: str | None = Field(default=None, max_length=16)
    picture: list[int] | None = Field(default=None, max_length=16)


class LoginIn(_In):
    nickname: str = Field(max_length=64)
    pin: str | None = Field(default=None, max_length=16)
    picture: list[int] | None = Field(default=None, max_length=16)


class RecoverIn(_In):
    nickname: str = Field(max_length=64)
    recovery_word: str = Field(max_length=64)
    new_pin: str | None = Field(default=None, max_length=16)
    new_picture: list[int] | None = Field(default=None, max_length=16)


class PlayerEnvelope(BaseModel):
    player: PlayerOut


class SignupOut(BaseModel):
    player: PlayerOut
    recovery_word: str


class NicknameSuggestion(BaseModel):
    nickname: str


class Done(BaseModel):
    ok: bool = True


async def _signed_in(db: Db, token: str) -> PlayerOut:
    player = await accounts.player_for_token(db, token)
    if player is None:
        raise Unauthorized()
    await db.commit()
    return player


@router.get("/auth/nickname-suggestion")
async def nickname_suggestion(request: Request) -> NicknameSuggestion:
    words = request.app.state.nickname_words
    return NicknameSuggestion(nickname=accounts.suggest_nickname(random.Random(), words))


@router.post("/auth/signup", dependencies=[Depends(limit_signup)])
async def signup(
    body: SignupIn, request: Request, response: Response, db: Db, settings: AppSettings
) -> SignupOut:
    result = await accounts.signup(
        db,
        signup_word=body.signup_word,
        nickname=body.nickname,
        pin=body.pin,
        picture=body.picture,
        blocklist=request.app.state.blocklist,
        content_dir=settings.content_dir,
    )
    set_cookie(response, settings, SESSION_COOKIE, result.device_token)
    player = await _signed_in(db, result.device_token)
    return SignupOut(player=player, recovery_word=result.recovery_word)


@router.post("/auth/login", dependencies=[Depends(limit_auth)])
async def login(
    body: LoginIn,
    response: Response,
    db: Db,
    settings: AppSettings,
    ip: ClientIp,
    device_key: DeviceKey,
) -> PlayerEnvelope:
    result = await accounts.login(
        db,
        nickname=body.nickname,
        pin=body.pin,
        picture=body.picture,
        device_key=device_key,
        ip=ip,
    )
    set_cookie(response, settings, SESSION_COOKIE, result.device_token)
    return PlayerEnvelope(player=await _signed_in(db, result.device_token))


@router.post("/auth/recover", dependencies=[Depends(limit_auth)])
async def recover(
    body: RecoverIn,
    response: Response,
    db: Db,
    settings: AppSettings,
    ip: ClientIp,
    device_key: DeviceKey,
) -> SignupOut:
    """Replace credentials; the response carries the rotated recovery word."""
    result = await accounts.recover(
        db,
        nickname=body.nickname,
        recovery_word=body.recovery_word,
        new_pin=body.new_pin,
        new_picture=body.new_picture,
        device_key=device_key,
        ip=ip,
        content_dir=settings.content_dir,
    )
    set_cookie(response, settings, SESSION_COOKIE, result.device_token)
    player = await _signed_in(db, result.device_token)
    return SignupOut(player=player, recovery_word=result.recovery_word)


@router.post("/auth/logout")
async def logout(request: Request, response: Response, db: Db, settings: AppSettings) -> Done:
    token = request.cookies.get(SESSION_COOKIE)
    if token:
        await accounts.logout(db, token)
    response.delete_cookie(
        SESSION_COOKIE,
        path="/",
        httponly=True,
        secure=settings.cookie_secure,
        samesite="lax",
    )
    return Done()


@router.get("/me")
async def me(player: CurrentPlayer) -> PlayerEnvelope:
    return PlayerEnvelope(player=player)
