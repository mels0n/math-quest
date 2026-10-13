"""Application factory: wiring, lifespan, device-cookie middleware and the SPA mount."""

import logging
from collections.abc import AsyncGenerator, Awaitable, Callable
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import Depends, FastAPI, Request, Response
from sqlalchemy.ext.asyncio import AsyncEngine
from starlette.exceptions import HTTPException
from starlette.staticfiles import StaticFiles
from starlette.types import Scope

from mathquest.api import auth, health
from mathquest.api.clientip import parse_networks
from mathquest.api.deps import (
    DEVICE_COOKIE,
    new_device_key,
    require_csrf,
    set_cookie,
    valid_device_key,
)
from mathquest.api.errors import install_error_handlers
from mathquest.api.ratelimit import Clock, RateLimiter
from mathquest.engine.checker.bounded import CheckerPool
from mathquest.features import accounts
from mathquest.shared import db as database
from mathquest.shared.config import Settings, get_settings
from mathquest.shared.logging import configure_logging

log = logging.getLogger(__name__)


class SpaStaticFiles(StaticFiles):
    """Static files that answer unknown non-API paths with `index.html`."""

    async def get_response(self, path: str, scope: Scope) -> Response:
        try:
            return await super().get_response(path, scope)
        except HTTPException as err:
            route = path.replace("\\", "/")
            if err.status_code != 404 or route == "api" or route.startswith("api/"):
                raise
            return await super().get_response("index.html", scope)


def create_app(
    settings: Settings | None = None,
    *,
    engine: AsyncEngine | None = None,
    clock: Clock | None = None,
    checker_pool: CheckerPool | None = None,
) -> FastAPI:
    """Build the app. `engine`, `clock` and `checker_pool` replace the defaults (tests)."""
    cfg = settings or get_settings()
    trusted = parse_networks(cfg.trusted_proxies)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncGenerator[None]:
        configure_logging()
        owned = engine is None
        if engine is not None:
            db_engine = engine
        else:
            assert cfg.database_url is not None
            db_engine = database.create_engine(cfg.database_url.get_secret_value())
        factory = database.create_session_factory(db_engine)
        pool = checker_pool or CheckerPool()
        try:
            async with factory() as session:
                await accounts.seed_signup_word(session, cfg.initial_signup_word)
            app.state.settings = cfg
            app.state.session_factory = factory
            app.state.trusted_networks = trusted
            app.state.rate_limiter = RateLimiter(clock) if clock else RateLimiter()
            app.state.blocklist = accounts.load_blocklist(cfg.content_dir)
            app.state.nickname_words = accounts.load_nickname_words(cfg.content_dir)
            accounts.load_recovery_words(cfg.content_dir)
            await pool.warm()
            app.state.checker_pool = pool
            yield
        finally:
            pool.close()
            if owned:
                await db_engine.dispose()

    app = FastAPI(
        lifespan=lifespan,
        dependencies=[Depends(require_csrf)],
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
    )
    install_error_handlers(app)

    @app.middleware("http")
    async def device_cookie(  # pyright: ignore[reportUnusedFunction]
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        if not request.url.path.startswith("/api"):
            return await call_next(request)
        sent = request.cookies.get(DEVICE_COOKIE)
        key = sent if sent is not None and valid_device_key(sent) else new_device_key()
        request.state.device_key = key
        response = await call_next(request)
        if key != sent:
            set_cookie(response, cfg, DEVICE_COOKIE, key)
        return response

    app.include_router(health.router)
    app.include_router(auth.router)

    if cfg.static_dir is not None:
        static_dir: Path = cfg.static_dir
        app.mount("/", SpaStaticFiles(directory=static_dir, html=True), name="static")
    return app
