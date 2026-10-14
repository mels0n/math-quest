"""The single place domain errors become HTTP responses."""

import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException

from mathquest.shared.errors import (
    Conflict,
    Forbidden,
    Invalid,
    Locked,
    NotFound,
    RateLimited,
    Unauthorized,
)

log = logging.getLogger(__name__)


def _body(code: str, status: int, retry_after_s: int | None = None) -> JSONResponse:
    headers = {"Retry-After": str(retry_after_s)} if retry_after_s is not None else None
    return JSONResponse({"error": code}, status_code=status, headers=headers)


def not_found_response() -> JSONResponse:
    """The one 404 body, used for unknown paths and for hidden admin routes alike."""
    return _body("not_found", 404)


async def _invalid(_: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, Invalid)
    return _body(exc.code, 422)


async def _conflict(_: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, Conflict)
    return _body(exc.code, 409)


async def _forbidden(_: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, Forbidden)
    return _body(exc.code, 403)


async def _unauthorized(_: Request, __: Exception) -> JSONResponse:
    return _body("unauthorized", 401)


async def _not_found(_: Request, __: Exception) -> JSONResponse:
    return not_found_response()


async def _locked(_: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, Locked)
    return _body("locked", 429, exc.retry_after_s)


async def _rate_limited(_: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, RateLimited)
    return _body("rate_limited", 429, exc.retry_after_s)


async def _http(_: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, HTTPException)
    code = {404: "not_found", 405: "method_not_allowed"}.get(exc.status_code, "http_error")
    return JSONResponse({"error": code}, status_code=exc.status_code, headers=exc.headers)


async def _bad_request(_: Request, __: Exception) -> JSONResponse:
    return _body("invalid_request", 422)


async def _internal(request: Request, exc: Exception) -> JSONResponse:
    log.error("unhandled error on %s %s", request.method, request.url.path, exc_info=exc)
    return _body("internal", 500)


def install_error_handlers(app: FastAPI) -> None:
    app.add_exception_handler(Invalid, _invalid)
    app.add_exception_handler(Conflict, _conflict)
    app.add_exception_handler(Forbidden, _forbidden)
    app.add_exception_handler(Unauthorized, _unauthorized)
    app.add_exception_handler(NotFound, _not_found)
    app.add_exception_handler(Locked, _locked)
    app.add_exception_handler(RateLimited, _rate_limited)
    app.add_exception_handler(HTTPException, _http)
    app.add_exception_handler(RequestValidationError, _bad_request)
    app.add_exception_handler(Exception, _internal)
