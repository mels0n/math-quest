"""Admin login, logout and session check. LAN-only: off-LAN clients see 404 on every route."""

from fastapi import APIRouter, Depends, Request, Response
from pydantic import BaseModel, ConfigDict, Field

from mathquest.api.deps import (
    ADMIN_COOKIE,
    ADMIN_COOKIE_PATH,
    AppSettings,
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
    body: AdminLoginIn, request: Request, response: Response, db: Db, settings: AppSettings
) -> Done:
    stored_hash: str | None = request.app.state.admin_password_hash
    if stored_hash is None:
        raise Unauthorized()
    result = await admin.login(db, stored_hash=stored_hash, password=body.password)
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
