"""Adventure play routes."""

import uuid
from typing import Literal

from fastapi import APIRouter, Request
from pydantic import BaseModel, ConfigDict, Field

from mathquest.api.deps import AppSettings, CurrentPlayer, Db
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


@router.post("/sessions")
async def start_session(body: StartIn, player: CurrentPlayer, db: Db) -> SessionOut:
    return await play.start_session(db, player.id, body.mode)


@router.post("/sessions/{session_id}/next")
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


@router.post("/problems/{problem_id}/answer")
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
