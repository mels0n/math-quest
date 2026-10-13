# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false, reportPrivateUsage=false
import asyncio
import time
from collections.abc import AsyncIterator

import pytest_asyncio
import sympy

from mathquest.engine.checker.bounded import CheckerPool
from mathquest.engine.checker.check import CheckResult, Verdict, check
from mathquest.engine.types import AnswerForm, Problem

SLOW = "slow"
MID = "mid"


def slow_or_check(problem: Problem, latex: str) -> CheckResult:
    """Module-level so it pickles under the spawn start method."""
    if latex == SLOW:
        time.sleep(5)
    if latex == MID:
        time.sleep(1)
        latex = "2"
    return check(problem, latex)


def problem_for(answer: sympy.Basic) -> Problem:
    return Problem(
        skill_id="test",
        tier=1,
        seed=0,
        prompt_latex="1+1",
        answer=answer,  # pyright: ignore[reportArgumentType]
        form=AnswerForm.ANY,
        misconceptions=(),
        difficulty=0.5,
        keypad="numbers",
    )


@pytest_asyncio.fixture
async def pool() -> AsyncIterator[CheckerPool]:
    p = CheckerPool(worker=slow_or_check, timeout=2.0)
    yield p
    p.close()


async def test_normal_check_passes_through(pool: CheckerPool) -> None:
    result = await pool.check(problem_for(sympy.Integer(2)), "2")
    assert result.verdict is Verdict.CORRECT


async def test_default_worker_round_trips_a_real_problem() -> None:
    default = CheckerPool(timeout=30.0)
    try:
        result = await default.check(problem_for(sympy.Rational(3, 2)), r"\frac{3}{2}")
    finally:
        default.close()
    assert result.verdict is Verdict.CORRECT


async def test_timeout_returns_unreadable(pool: CheckerPool) -> None:
    await pool.warm()
    start = time.monotonic()
    result = await pool.check(problem_for(sympy.Integer(2)), SLOW)
    assert result == CheckResult(Verdict.UNREADABLE, None)
    assert time.monotonic() - start < 3.0


async def test_timeout_terminates_stuck_worker(pool: CheckerPool) -> None:
    await pool.check(problem_for(sympy.Integer(2)), "2")
    old = pool._pool
    assert old is not None
    processes = list(old._processes.values())
    assert processes
    result = await pool.check(problem_for(sympy.Integer(2)), SLOW)
    assert result.verdict is Verdict.UNREADABLE
    assert pool._pool is not old
    assert all(not p.is_alive() for p in processes)


async def test_pool_recovers_after_timeout(pool: CheckerPool) -> None:
    await pool.check(problem_for(sympy.Integer(2)), SLOW)
    result = await pool.check(problem_for(sympy.Integer(2)), "2")
    assert result.verdict is Verdict.CORRECT


async def test_concurrent_normal_check_survives_replacement(pool: CheckerPool) -> None:
    problem = problem_for(sympy.Integer(2))
    await pool.check(problem, "2")
    slow, normal = await asyncio.gather(pool.check(problem, SLOW), pool.check(problem, "2"))
    assert slow.verdict is Verdict.UNREADABLE
    assert normal.verdict is Verdict.CORRECT


async def test_two_simultaneous_timeouts_do_not_raise(pool: CheckerPool) -> None:
    problem = problem_for(sympy.Integer(2))
    results = await asyncio.gather(pool.check(problem, SLOW), pool.check(problem, SLOW))
    assert [r.verdict for r in results] == [Verdict.UNREADABLE, Verdict.UNREADABLE]


async def test_in_flight_peer_is_retried_after_kill(pool: CheckerPool) -> None:
    problem = problem_for(sympy.Integer(2))
    await pool.warm()
    slow = asyncio.create_task(pool.check(problem, SLOW))
    await asyncio.sleep(1.5)
    peer = await pool.check(problem, MID)
    assert (await slow).verdict is Verdict.UNREADABLE
    assert peer.verdict is Verdict.CORRECT


async def test_two_timeouts_plus_queued_check_do_not_raise(pool: CheckerPool) -> None:
    problem = problem_for(sympy.Integer(2))
    results = await asyncio.gather(
        pool.check(problem, SLOW), pool.check(problem, SLOW), pool.check(problem, "2")
    )
    assert results[0].verdict is Verdict.UNREADABLE
    assert results[1].verdict is Verdict.UNREADABLE
    assert (await pool.check(problem, "2")).verdict is Verdict.CORRECT


async def test_warm_pool_checks_well_under_budget(pool: CheckerPool) -> None:
    await pool.warm()
    start = time.monotonic()
    result = await pool.check(problem_for(sympy.Integer(2)), "2")
    assert result.verdict is Verdict.CORRECT
    assert time.monotonic() - start < 1.0
