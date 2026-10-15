"""Play routes: adventure and practice sessions, problems, summaries and the skill list."""

import uuid
from typing import Annotated, Literal, Self

from fastapi import APIRouter, Depends, Header, Request
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from mathquest.api.deps import (
    AnswerBody,
    AppSettings,
    CurrentPlayer,
    Db,
    limit_answer,
    limit_next,
    limit_session,
)
from mathquest.features import play, teaching
from mathquest.features.play import AnswerOut, NextOut, SessionOut, SkillsOut, SummaryOut
from mathquest.features.teaching import ExplanationOut, HintOut

router = APIRouter(prefix="/api/play")
skills_router = APIRouter(prefix="/api/skills")

LESSON_CLIENT = 2
"""The first client version that shows lessons. `next` offers a lesson only to a client
that sends `X-MathQuest-Client: 2` or later, so a page loaded before lessons existed
keeps getting problems. Remove the header check one release after lessons ship
(ADR-0014)."""
SUMMARY_CLIENT = 3
"""The first client version that shows session summaries. `next` ends an adventure
after its twelfth problem only for a client that sends `X-MathQuest-Client: 3` or later;
an older page keeps getting problems (ADR-0016)."""


def _client_version(raw: str | None) -> int:
    return int(raw) if raw is not None and raw.isdecimal() and len(raw) <= 4 else 0


class StartIn(BaseModel):
    """An adventure, or a practice session on ``skill_id`` or on ``weak_spots``."""

    model_config = ConfigDict(extra="forbid")

    mode: Literal["adventure", "practice"]
    skill_id: str | None = Field(default=None, pattern=r"^[a-z][a-z0-9_]*$", max_length=64)
    weak_spots: bool = False

    @model_validator(mode="after")
    def _practice_target(self) -> Self:
        if self.mode == "adventure" and (self.skill_id is not None or self.weak_spots):
            raise ValueError("an adventure takes no skill_id or weak_spots")
        if self.mode == "practice" and (self.skill_id is None) == (not self.weak_spots):
            raise ValueError("practice takes exactly one of skill_id or weak_spots")
        return self


class AnswerIn(AnswerBody):
    @field_validator("latex")
    @classmethod
    def _not_a_stored_choice(cls, value: str | None) -> str | None:
        if value is not None and value.startswith(play.CHOICE_PREFIX):
            # Reserved for stored choice attempts; keeps the attempts column unambiguous.
            raise ValueError("not an answer")
        return value


@router.post("/sessions", dependencies=[Depends(limit_session)])
async def start_session(
    body: StartIn, request: Request, player: CurrentPlayer, db: Db
) -> SessionOut:
    if body.mode == "practice":
        return await play.start_practice(
            db,
            request.app.state.catalog,
            player.id,
            skill_id=body.skill_id,
            weak_spots=body.weak_spots,
        )
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
        offer_summary=_client_version(client) >= SUMMARY_CLIENT,
    )


@router.post("/sessions/{session_id}/end", dependencies=[Depends(limit_next)])
async def end_session(
    session_id: uuid.UUID, request: Request, player: CurrentPlayer, db: Db
) -> SummaryOut:
    return await play.end_session(db, request.app.state.catalog, player.id, session_id)


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


@skills_router.get("", dependencies=[Depends(limit_next)])
async def list_skills(request: Request, player: CurrentPlayer, db: Db) -> SkillsOut:
    return await play.list_skills(db, request.app.state.catalog, player.id)
