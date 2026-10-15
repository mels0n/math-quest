"""Placement routes: start a round (or retake it) and answer its questions."""

import uuid

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, ConfigDict

from mathquest.api.deps import (
    AnswerBody,
    AppSettings,
    CurrentPlayer,
    Db,
    limit_answer,
    limit_placement_start,
)
from mathquest.features import placement
from mathquest.features.placement import GradeHint, PlacementDoneOut, PlacementStepOut

router = APIRouter(prefix="/api/placement")


class StartIn(BaseModel):
    """``grade_hint`` only picks the first question; leave it out to skip it."""

    model_config = ConfigDict(extra="forbid")

    grade_hint: GradeHint | None = None


class AnswerIn(AnswerBody):
    placement_id: uuid.UUID
    problem_id: uuid.UUID


@router.post("/start", dependencies=[Depends(limit_placement_start)])
async def start(
    body: StartIn, request: Request, player: CurrentPlayer, db: Db, settings: AppSettings
) -> PlacementStepOut:
    return await placement.start(
        db,
        request.app.state.catalog,
        player.id,
        body.grade_hint,
        expose_answers=settings.dev_expose_answers,
    )


@router.post("/answer", dependencies=[Depends(limit_answer)])
async def answer(
    body: AnswerIn, request: Request, player: CurrentPlayer, db: Db, settings: AppSettings
) -> PlacementStepOut | PlacementDoneOut:
    return await placement.answer(
        db,
        request.app.state.checker_pool,
        request.app.state.catalog,
        player.id,
        body.placement_id,
        body.problem_id,
        body.latex,
        choice=body.choice,
        expose_answers=settings.dev_expose_answers,
    )
