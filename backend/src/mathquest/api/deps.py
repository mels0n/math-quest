"""Request-scoped dependencies: database session, client address, CSRF, rate limits."""

import re
import secrets
from collections.abc import AsyncGenerator
from typing import Annotated, Self

from fastapi import Depends, Request, Response
from pydantic import BaseModel, ConfigDict, Field, StrictInt, field_validator, model_validator
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from mathquest.api import ratelimit
from mathquest.api.clientip import IPNetwork, client_ip
from mathquest.features import admin
from mathquest.features.accounts import PlayerOut, player_for_token
from mathquest.shared.config import Settings
from mathquest.shared.errors import Forbidden, Unauthorized

DEVICE_COOKIE = "mq_device"
SESSION_COOKIE = "mq_session"
ADMIN_COOKIE = "mq_admin"
ADMIN_COOKIE_PATH = "/api/admin"
COOKIE_MAX_AGE_S = 400 * 24 * 3600
CSRF_HEADER = "X-Requested-With"
CSRF_VALUE = "mathquest"
SAFE_METHODS = frozenset({"GET", "HEAD", "OPTIONS"})

_DEVICE_KEY = re.compile(r"[A-Za-z0-9_-]{16,64}")


def valid_device_key(value: str | None) -> bool:
    return value is not None and _DEVICE_KEY.fullmatch(value) is not None


def new_device_key() -> str:
    return secrets.token_urlsafe(24)


def set_cookie(response: Response, settings: Settings, name: str, value: str) -> None:
    response.set_cookie(
        name,
        value,
        max_age=COOKIE_MAX_AGE_S,
        path="/",
        httponly=True,
        secure=settings.cookie_secure,
        samesite="lax",
    )


async def get_db(request: Request) -> AsyncGenerator[AsyncSession]:
    """One session per request. Services commit; anything left open is rolled back."""
    factory: async_sessionmaker[AsyncSession] = request.app.state.session_factory
    session = factory()
    try:
        yield session
    finally:
        try:
            await session.rollback()
        finally:
            await session.close()


def get_settings(request: Request) -> Settings:
    settings: Settings = request.app.state.settings
    return settings


def resolve_client_ip(request: Request) -> str:
    trusted: tuple[IPNetwork, ...] = request.app.state.trusted_networks
    peer = request.client.host if request.client is not None else None
    return client_ip(peer, request.headers.getlist("x-forwarded-for"), trusted)


async def get_client_ip(request: Request) -> str:
    """The address lockouts key on: the rate-limit bucket, so an IPv6 /64 counts as one."""
    return ratelimit.rate_bucket(resolve_client_ip(request))


async def get_device_key(request: Request) -> str:
    key: str = request.state.device_key
    return key


async def require_csrf(request: Request) -> None:
    if request.method not in SAFE_METHODS and request.headers.get(CSRF_HEADER) != CSRF_VALUE:
        raise Forbidden("csrf")


def _limiter(request: Request) -> ratelimit.RateLimiter:
    limiter: ratelimit.RateLimiter = request.app.state.rate_limiter
    return limiter


async def limit_signup(request: Request) -> None:
    key = ratelimit.rate_bucket(resolve_client_ip(request))
    _limiter(request).hit(
        "signup", key, limit=ratelimit.SIGNUP_LIMIT, window_s=ratelimit.SIGNUP_WINDOW_S
    )


async def limit_auth(request: Request) -> None:
    """Login and recovery attempts share one counter."""
    key = ratelimit.rate_bucket(resolve_client_ip(request))
    _limiter(request).hit("auth", key, limit=ratelimit.AUTH_LIMIT, window_s=ratelimit.AUTH_WINDOW_S)


Db = Annotated[AsyncSession, Depends(get_db)]
AppSettings = Annotated[Settings, Depends(get_settings)]
ClientIp = Annotated[str, Depends(get_client_ip)]
DeviceKey = Annotated[str, Depends(get_device_key)]


async def current_player(request: Request, db: Db) -> PlayerOut:
    token = request.cookies.get(SESSION_COOKIE)
    if not token:
        raise Unauthorized()
    player = await player_for_token(db, token)
    if player is None:
        raise Unauthorized()
    await db.commit()
    return player


CurrentPlayer = Annotated[PlayerOut, Depends(current_player)]


async def limit_admin_login(request: Request) -> None:
    """Admin login attempts are capped per client bucket and across all clients."""
    key = ratelimit.rate_bucket(resolve_client_ip(request))
    limiter = _limiter(request)
    limiter.hit(
        "admin-login",
        key,
        limit=ratelimit.ADMIN_LOGIN_LIMIT,
        window_s=ratelimit.ADMIN_LOGIN_WINDOW_S,
    )
    limiter.hit(
        "admin-login-all",
        "all",
        limit=ratelimit.ADMIN_LOGIN_GLOBAL_LIMIT,
        window_s=ratelimit.ADMIN_LOGIN_WINDOW_S,
    )


async def require_admin(request: Request, db: Db) -> admin.AdminSessionOut:
    """A live admin session (401 otherwise). The LAN gate already ran as middleware."""
    token = request.cookies.get(ADMIN_COOKIE)
    if not token:
        raise Unauthorized()
    session = await admin.session_for_token(db, token)
    if session is None:
        raise Unauthorized()
    return session


CurrentAdmin = Annotated[admin.AdminSessionOut, Depends(require_admin)]


async def limit_answer(request: Request, player: CurrentPlayer) -> None:
    """Answer submissions are limited per player."""
    _limiter(request).hit(
        "answer", str(player.id), limit=ratelimit.ANSWER_LIMIT, window_s=ratelimit.ANSWER_WINDOW_S
    )


async def limit_session(request: Request, player: CurrentPlayer) -> None:
    """Session creation is limited per player."""
    _limiter(request).hit(
        "session", str(player.id), limit=ratelimit.PLAY_LIMIT, window_s=ratelimit.PLAY_WINDOW_S
    )


async def limit_placement_start(request: Request, player: CurrentPlayer) -> None:
    """Placement rounds started (first rounds and retakes) are limited per player."""
    _limiter(request).hit(
        "placement-start",
        str(player.id),
        limit=ratelimit.PLACEMENT_START_LIMIT,
        window_s=ratelimit.PLACEMENT_START_WINDOW_S,
    )


async def limit_next(request: Request, player: CurrentPlayer) -> None:
    """Problem requests are limited per player."""
    _limiter(request).hit(
        "next", str(player.id), limit=ratelimit.PLAY_LIMIT, window_s=ratelimit.PLAY_WINDOW_S
    )


MAX_BODY_LATEX = 1000
"""Wide enough for any real answer; services store 200 characters and the checker
rejects longer input as unreadable."""
MAX_CHOICE = 99
"""Far above any real number of choices; services reject an index past the shown ones."""


class AnswerBody(BaseModel):
    """An answer: exactly one of ``latex`` (typed) or ``choice`` (a choice index). Text
    with NUL or that UTF-8 cannot encode is rejected, since Postgres text cannot store
    either."""

    model_config = ConfigDict(extra="forbid")

    latex: str | None = Field(default=None, max_length=MAX_BODY_LATEX)
    choice: StrictInt | None = Field(default=None, ge=0, le=MAX_CHOICE)

    @model_validator(mode="after")
    def _exactly_one(self) -> Self:
        if (self.latex is None) == (self.choice is None):
            raise ValueError("send exactly one of latex or choice")
        return self

    @field_validator("latex")
    @classmethod
    def _storable(cls, value: str | None) -> str | None:
        if value is None:
            return None
        if "\x00" in value:
            raise ValueError("NUL is not allowed")
        try:
            value.encode("utf-8")
        except UnicodeEncodeError:
            raise ValueError("not valid UTF-8 text") from None
        return value
