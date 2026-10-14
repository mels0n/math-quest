"""Request-scoped dependencies: database session, client address, CSRF, rate limits."""

import re
import secrets
from collections.abc import AsyncGenerator
from typing import Annotated

from fastapi import Depends, Request, Response
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from mathquest.api import ratelimit
from mathquest.api.clientip import IPNetwork, client_ip
from mathquest.features.accounts import PlayerOut, player_for_token
from mathquest.shared.config import Settings
from mathquest.shared.errors import Forbidden, Unauthorized

DEVICE_COOKIE = "mq_device"
SESSION_COOKIE = "mq_session"
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


async def limit_answer(request: Request, player: CurrentPlayer) -> None:
    """Answer submissions are limited per player."""
    _limiter(request).hit(
        "answer", str(player.id), limit=ratelimit.ANSWER_LIMIT, window_s=ratelimit.ANSWER_WINDOW_S
    )
