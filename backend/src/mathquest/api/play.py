"""Adventure play routes."""

import uuid
from typing import Annotated, Literal, Self

from fastapi import APIRouter, Depends, Header, Request
from pydantic import BaseModel, ConfigDict, Field, StrictInt, field_validator, model_validator

from mathquest.api.deps import (
    AppSettings,
    CurrentPlayer,
    Db,
    limit_answer,
    limit_next,
    limit_session,
)
from mathquest.features import play, teaching
from mathquest.features.play import AnswerOut, NextOut, SessionOut
from mathquest.features.teaching import ExplanationOut, HintOut

router = APIRouter(prefix="/api/play")

# Wide enough for any real answer; the service stores 200 characters and the checker
# rejects longer input as unreadable.
MAX_BODY_LATEX = 1000
# Far above any real number of choices; the service rejects an index past the shown ones.
MAX_CHOICE = 99
LESSON_CLIENT = 2
"""The first client version that shows lessons. `next` offers a lesson only to a client
that sends `X-MathQuest-Client: 2` or later, so a page loaded before lessons existed
keeps getting problems. Remove the header check one release after lessons ship
(ADR-0014)."""


def _client_version(raw: str | None) -> int:
    return int(raw) if raw is not None and raw.isdecimal() and len(raw) <= 4 else 0


class StartIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    mode: Literal["adventure"]


class AnswerIn(BaseModel):
    """Exactly one of ``latex`` (a typed answer) or ``choice`` (a choice index)."""

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
        """Reject NUL and text that UTF-8 cannot encode; Postgres text cannot store either."""
        if value is None:
            return None
        if "\x00" in value:
            raise ValueError("NUL is not allowed")
        if value.startswith(play.CHOICE_PREFIX):
            # Reserved for stored choice attempts; keeps the attempts column unambiguous.
            raise ValueError("not an answer")
        try:
            value.encode("utf-8")
        except UnicodeEncodeError:
            raise ValueError("not valid UTF-8 text") from None
        return value


@router.post("/sessions", dependencies=[Depends(limit_session)])
async def start_session(body: StartIn, player: CurrentPlayer, db: Db) -> SessionOut:
    return await play.start_session(db, player.id, body.mode)


@router.post("/sessions/{session_id}/next", dependencies=[Depends(limit_next)])
async def next_problem(
    session_id: uuid.UUID,
    request: Request,
    player: CurrentPlayer,
    db: Db,
    settings: AppSettings,
    client: Annotated[str | None, Header(alias="X-MathQuest-Client", max_length=8)] = None,
) -> NextOut:
    return await play.next_problem(
        db,
        request.app.state.catalog,
        player.id,
        session_id,
        expose_answers=settings.dev_expose_answers,
        offer_lessons=_client_version(client) >= LESSON_CLIENT,
    )


@router.post("/problems/{problem_id}/answer", dependencies=[Depends(limit_answer)])
async def answer(
    problem_id: uuid.UUID, body: AnswerIn, request: Request, player: CurrentPlayer, db: Db
) -> AnswerOut:
    return await play.submit_answer(
        db,
        request.app.state.checker_pool,
        request.app.state.catalog,
        player.id,
        problem_id,
        body.latex,
        choice=body.choice,
    )


@router.post("/problems/{problem_id}/hint", dependencies=[Depends(limit_answer)])
async def hint(problem_id: uuid.UUID, request: Request, player: CurrentPlayer, db: Db) -> HintOut:
    return await teaching.next_hint(db, request.app.state.catalog, player.id, problem_id)


@router.post("/problems/{problem_id}/explain", dependencies=[Depends(limit_answer)])
async def explain(
    problem_id: uuid.UUID, request: Request, player: CurrentPlayer, db: Db
) -> ExplanationOut:
    return await teaching.next_explanation(db, request.app.state.catalog, player.id, problem_id)
