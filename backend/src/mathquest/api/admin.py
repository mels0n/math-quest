"""Admin login, logout and session check. LAN-only: off-LAN clients see 404 on every route."""

import uuid
from datetime import UTC, datetime
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Path, Query, Request, Response
from pydantic import BaseModel, ConfigDict, Field, TypeAdapter

from mathquest.api.deps import (
    ADMIN_COOKIE,
    ADMIN_COOKIE_PATH,
    AppSettings,
    ClientIp,
    CurrentAdmin,
    Db,
    limit_admin_login,
)
from mathquest.engine.catalog import Catalog
from mathquest.features import admin, teaching
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


MAX_SEED = 2**53 - 1  # the largest seed a browser can hold exactly
MAX_TIER = 20


def _catalog(request: Request) -> Catalog:
    catalog: Catalog = request.app.state.catalog
    return catalog


@router.get("/content")
async def content(_: CurrentAdmin, request: Request) -> admin.ContentOverview:
    return admin.overview(_catalog(request))


@router.get("/content/skills/{skill_id}")
async def content_skill(
    skill_id: Annotated[str, Path(pattern=r"^[a-z][a-z0-9_]*$", max_length=64)],
    _: CurrentAdmin,
    request: Request,
    seed: Annotated[int | None, Query(ge=0, le=MAX_SEED)] = None,
    tier: Annotated[int, Query(ge=0, le=MAX_TIER)] = 0,
) -> admin.SkillPreview:
    return admin.skill_preview(_catalog(request), skill_id, seed=seed, tier=tier)


@router.get("/stuck-log", response_model=list[teaching.StuckProblemOut])
async def stuck_log(
    _: CurrentAdmin,
    db: Db,
    since: Annotated[datetime | None, Query()] = None,
    fmt: Annotated[Literal["json", "csv"], Query(alias="format")] = "json",
) -> Response:
    """Stuck problems (at or after ``since``) as the JSON list ``content-report --stuck``
    reads, or as CSV with ``format=csv``. No player identity is included. A ``since``
    without a time zone is read as UTC."""
    if since is not None and since.tzinfo is None:
        since = since.replace(tzinfo=UTC)
    entries = await teaching.stuck_log(db, since)
    if fmt == "csv":
        return Response(
            teaching.stuck_csv(entries),
            media_type="text/csv; charset=utf-8",
            headers={"Content-Disposition": 'attachment; filename="stuck-log.csv"'},
        )
    body = TypeAdapter(list[teaching.StuckProblemOut]).dump_json(entries)
    return Response(
        body,
        media_type="application/json",
        headers={"Content-Disposition": 'attachment; filename="stuck-log.json"'},
    )
