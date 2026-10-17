"""Every lesson's try-it can be answered the way the skill is answered."""

import uuid
from pathlib import Path

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from mathquest.engine.catalog import load_catalog
from mathquest.engine.checker.bounded import CheckerPool
from mathquest.engine.checker.check import CheckResult, Verdict, check
from mathquest.engine.types import Problem
from mathquest.entities import players
from mathquest.features import teaching

CATALOG = load_catalog(Path(__file__).resolve().parents[2] / "content", "k8-core")


class _SyncPool(CheckerPool):
    async def check(self, problem: Problem, latex: str) -> CheckResult:
        return check(problem, latex)


@pytest.mark.parametrize("skill", sorted(CATALOG.pack.lessons))
async def test_a_try_it_is_a_problem_the_learner_can_answer(db: AsyncSession, skill: str) -> None:
    row = await players.add(
        db,
        nickname=f"Tryer{uuid.uuid4().hex[:6]}",
        pin_hash=None,
        picture_hash=None,
        recovery_hash="x",
    )
    problem = await teaching.start_try(db, CATALOG, row.id, skill, expose_answers=True)
    # A try-it is a generator problem, typed: a skill that is answered by buttons alone
    # would show buttons it cannot fill (there is no choice in a try-it's response).
    assert problem.keypad != "choice"
    assert problem.dev_answer_latex
    out = await teaching.answer_try(
        db, _SyncPool(), CATALOG, row.id, problem.try_id, problem.dev_answer_latex
    )
    assert out.verdict is Verdict.CORRECT and out.solved
