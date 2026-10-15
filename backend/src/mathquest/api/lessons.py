"""Lesson routes: read a skill's lesson, mark it seen, and its practice problem."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Path, Request
from pydantic import BaseModel, ConfigDict, Field, field_validator

from mathquest.api.deps import AppSettings, CurrentPlayer, Db, limit_answer, limit_next
from mathquest.features import teaching
from mathquest.features.teaching import LessonOut, SeenOut, TryAnswerOut, TryProblemOut

router = APIRouter(prefix="/api/lessons")

MAX_BODY_LATEX = 1000

SkillId = Annotated[str, Path(pattern=r"^[a-z][a-z0-9_]*$", max_length=64)]


class TryAnswerIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    latex: str = Field(max_length=MAX_BODY_LATEX)

    @field_validator("latex")
    @classmethod
    def _no_nul(cls, value: str) -> str:
        if "\x00" in value:
            raise ValueError("NUL is not allowed")
        return value


@router.get("/{skill_id}")
async def get_lesson(skill_id: SkillId, request: Request, player: CurrentPlayer) -> LessonOut:
    del player  # signed-in players only
    return teaching.get_lesson(request.app.state.catalog, skill_id)


@router.post("/{skill_id}/seen")
async def mark_seen(skill_id: SkillId, request: Request, player: CurrentPlayer, db: Db) -> SeenOut:
    return await teaching.mark_seen(db, request.app.state.catalog, player.id, skill_id)


@router.post("/{skill_id}/try", dependencies=[Depends(limit_next)])
async def start_try(
    skill_id: SkillId, request: Request, player: CurrentPlayer, db: Db, settings: AppSettings
) -> TryProblemOut:
    return await teaching.start_try(
        db,
        request.app.state.catalog,
        player.id,
        skill_id,
        expose_answers=settings.dev_expose_answers,
    )


@router.post("/tries/{try_id}/answer", dependencies=[Depends(limit_answer)])
async def answer_try(
    try_id: uuid.UUID, body: TryAnswerIn, request: Request, player: CurrentPlayer, db: Db
) -> TryAnswerOut:
    return await teaching.answer_try(
        db,
        request.app.state.checker_pool,
        request.app.state.catalog,
        player.id,
        try_id,
        body.latex,
    )
