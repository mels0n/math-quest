"""Adventure play routes."""

import uuid
from typing import Literal

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, ConfigDict, Field, field_validator

from mathquest.api.deps import (
    AppSettings,
    CurrentPlayer,
    Db,
    limit_answer,
    limit_next,
    limit_session,
)
from mathquest.features import play
from mathquest.features.play import AnswerOut, ProblemOut, SessionOut

router = APIRouter(prefix="/api/play")

# Wide enough for any real answer; the service stores 200 characters and the checker
# rejects longer input as unreadable.
MAX_BODY_LATEX = 1000


class StartIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    mode: Literal["adventure"]


class AnswerIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    latex: str = Field(max_length=MAX_BODY_LATEX)

    @field_validator("latex")
    @classmethod
    def _storable(cls, value: str) -> str:
        """Reject NUL and text that UTF-8 cannot encode; Postgres text cannot store either."""
        if "\x00" in value:
            raise ValueError("NUL is not allowed")
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
    session_id: uuid.UUID, request: Request, player: CurrentPlayer, db: Db, settings: AppSettings
) -> ProblemOut:
    return await play.next_problem(
        db,
        request.app.state.skill_graph,
        player.id,
        session_id,
        expose_answers=settings.dev_expose_answers,
    )


@router.post("/problems/{problem_id}/answer", dependencies=[Depends(limit_answer)])
async def answer(
    problem_id: uuid.UUID, body: AnswerIn, request: Request, player: CurrentPlayer, db: Db
) -> AnswerOut:
    return await play.submit_answer(
        db,
        request.app.state.checker_pool,
        request.app.state.skill_graph,
        player.id,
        problem_id,
        body.latex,
    )
