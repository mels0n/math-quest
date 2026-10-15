"""Placement routes: start a round (or retake it) and answer its questions."""

import uuid
from typing import Literal, Self

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, ConfigDict, Field, StrictInt, field_validator, model_validator

from mathquest.api.deps import (
    AppSettings,
    CurrentPlayer,
    Db,
    limit_answer,
    limit_placement_start,
)
from mathquest.features import placement
from mathquest.features.placement import PlacementDoneOut, PlacementStepOut

router = APIRouter(prefix="/api/placement")

MAX_BODY_LATEX = 1000
MAX_CHOICE = 99

GradeHint = Literal["K", "1", "2", "3", "4", "5", "6", "7", "8"]


class StartIn(BaseModel):
    """``grade_hint`` only picks the first question; leave it out to skip it."""

    model_config = ConfigDict(extra="forbid")

    grade_hint: GradeHint | None = None


class AnswerIn(BaseModel):
    """Exactly one of ``latex`` (a typed answer) or ``choice`` (a choice index)."""

    model_config = ConfigDict(extra="forbid")

    placement_id: uuid.UUID
    problem_id: uuid.UUID
    latex: str | None = Field(default=None, max_length=MAX_BODY_LATEX)
    choice: StrictInt | None = Field(default=None, ge=0, le=MAX_CHOICE)

    @model_validator(mode="after")
    def _exactly_one(self) -> Self:
        if (self.latex is None) == (self.choice is None):
            raise ValueError("send exactly one of latex or choice")
        return self

    @field_validator("latex")
    @classmethod
    def _plain_text(cls, value: str | None) -> str | None:
        """Reject NUL and text that UTF-8 cannot encode, as the play route does."""
        if value is None:
            return None
        if "\x00" in value:
            raise ValueError("NUL is not allowed")
        try:
            value.encode("utf-8")
        except UnicodeEncodeError:
            raise ValueError("not valid UTF-8 text") from None
        return value


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
