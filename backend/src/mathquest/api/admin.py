"""Admin login, logout and session check. LAN-only: off-LAN clients see 404 on every route."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request, Response
from pydantic import BaseModel, ConfigDict, Field

from mathquest.api.deps import (
    ADMIN_COOKIE,
    ADMIN_COOKIE_PATH,
    AppSettings,
    ClientIp,
    CurrentAdmin,
    Db,
    limit_admin_login,
)
from mathquest.features import admin
from mathquest.shared.config import Settings
from mathquest.shared.errors import Unauthorized

router = APIRouter(prefix="/api/admin")


class AdminLoginIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    password: str = Field(max_length=256)


class Done(BaseModel):
    ok: bool = True


def _set_session_cookie(response: Response, settings: Settings, token: str) -> None:
    response.set_cookie(
        ADMIN_COOKIE,
        token,
        max_age=int(admin.SESSION_TTL.total_seconds()),
        path=ADMIN_COOKIE_PATH,
        httponly=True,
        secure=settings.cookie_secure,
        samesite="strict",
    )


@router.post("/login", dependencies=[Depends(limit_admin_login)])
async def login(
    body: AdminLoginIn,
    request: Request,
    response: Response,
    db: Db,
    settings: AppSettings,
    client: ClientIp,
) -> Done:
    stored_hash: str | None = request.app.state.admin_password_hash
    if stored_hash is None:
        raise Unauthorized()
    result = await admin.login(db, stored_hash=stored_hash, password=body.password, client=client)
    _set_session_cookie(response, settings, result.token)
    return Done()


@router.post("/logout")
async def logout(request: Request, response: Response, db: Db, settings: AppSettings) -> Done:
    token = request.cookies.get(ADMIN_COOKIE)
    if token:
        await admin.logout(db, token)
    response.delete_cookie(
        ADMIN_COOKIE,
        path=ADMIN_COOKIE_PATH,
        httponly=True,
        secure=settings.cookie_secure,
        samesite="strict",
    )
    return Done()


@router.get("/me")
async def me(_: CurrentAdmin) -> Done:
    return Done()


class RenameIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    nickname: str = Field(max_length=64)


class ResetPinIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    pin: str = Field(pattern=r"^[0-9]{4}$")


class SignupWordIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    word: str = Field(pattern=r"^[A-Za-z]{3,32}$")


class SignupWordState(BaseModel):
    set: bool


@router.get("/players")
async def list_players(
    _: CurrentAdmin,
    db: Db,
    query: Annotated[str | None, Query(max_length=64)] = None,
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=admin.MAX_PAGE)] = 50,
) -> list[admin.PlayerAdminOut]:
    return await admin.list_players(db, query=query, offset=offset, limit=limit)


@router.post("/players/{player_id}/hide")
async def hide(player_id: uuid.UUID, session: CurrentAdmin, db: Db) -> Done:
    await admin.set_hidden(db, session.id, player_id, True)
    return Done()


@router.post("/players/{player_id}/unhide")
async def unhide(player_id: uuid.UUID, session: CurrentAdmin, db: Db) -> Done:
    await admin.set_hidden(db, session.id, player_id, False)
    return Done()


@router.post("/players/{player_id}/rename")
async def rename(
    player_id: uuid.UUID, body: RenameIn, request: Request, session: CurrentAdmin, db: Db
) -> Done:
    await admin.rename(
        db, session.id, player_id, body.nickname, blocklist=request.app.state.blocklist
    )
    return Done()


@router.post("/players/{player_id}/reset-pin")
async def reset_pin(
    player_id: uuid.UUID, body: ResetPinIn, session: CurrentAdmin, db: Db, settings: AppSettings
) -> admin.PinReset:
    return await admin.reset_pin(
        db, session.id, player_id, body.pin, content_dir=settings.content_dir
    )


@router.delete("/players/{player_id}")
async def delete_player(player_id: uuid.UUID, session: CurrentAdmin, db: Db) -> Done:
    await admin.delete_player(db, session.id, player_id)
    return Done()


@router.get("/signup-word")
async def signup_word_state(_: CurrentAdmin, db: Db) -> SignupWordState:
    return SignupWordState(set=await admin.signup_word_is_set(db))


@router.put("/signup-word")
async def set_signup_word(body: SignupWordIn, session: CurrentAdmin, db: Db) -> Done:
    await admin.set_signup_word(db, session.id, body.word)
    return Done()
