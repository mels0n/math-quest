"""Run the answer checker in worker processes under a hard time bound.

SymPy work cannot be interrupted in-process, so a check that overruns is
abandoned by terminating its worker process and replacing the pool. Every pool
is warmed (workers spawned, SymPy imported) before callers use it, so import
cost never counts against the per-answer budget.
"""

import asyncio
import logging
from collections.abc import Callable
from concurrent.futures import ProcessPoolExecutor
from concurrent.futures.process import BrokenProcessPool

from mathquest.engine.checker.check import CheckResult, Verdict, check
from mathquest.engine.types import AnswerForm, Problem

CHECK_TIMEOUT_SECONDS = 2.0
MAX_WORKERS = 2

WARM_TIMEOUT_SECONDS = 60.0
SHUTDOWN_MESSAGE = "after shutdown"

log = logging.getLogger(__name__)

Worker = Callable[[Problem, str], CheckResult]


def _run_check(problem: Problem, latex: str) -> CheckResult:
    return check(problem, latex)


def _init_worker() -> None:
    """Worker initializer. Unpickling it imports this module, which loads SymPy and the checker."""


def _warm_task() -> bool:
    import sympy

    problem = Problem(
        skill_id="warm",
        tier=1,
        seed=0,
        prompt_latex="",
        answer=sympy.Integer(2),
        form=AnswerForm.ANY,
        misconceptions=(),
        difficulty=0.0,
        keypad="numbers",
    )
    return check(problem, "2").verdict is Verdict.CORRECT


def _kill(pool: ProcessPoolExecutor) -> None:
    """Terminate every worker of ``pool`` and release it. Safe to call twice."""
    processes = list((pool._processes or {}).values())  # pyright: ignore[reportPrivateUsage]
    pool.shutdown(wait=False, cancel_futures=True)
    for process in processes:
        process.terminate()
    for process in processes:
        process.join(timeout=2.0)


class CheckerPool:
    def __init__(
        self, *, worker: Worker = _run_check, timeout: float = CHECK_TIMEOUT_SECONDS
    ) -> None:
        self._worker = worker
        self._timeout = timeout
        self._pool: ProcessPoolExecutor | None = None
        self._lock = asyncio.Lock()

    async def _warm(self, pool: ProcessPoolExecutor) -> None:
        loop = asyncio.get_running_loop()
        jobs = [loop.run_in_executor(pool, _warm_task) for _ in range(MAX_WORKERS)]
        try:
            await asyncio.wait_for(asyncio.gather(*jobs), WARM_TIMEOUT_SECONDS)
        except Exception:
            log.exception("checker pool warm-up failed")

    async def _ensure(self) -> ProcessPoolExecutor:
        """The current pool, created and warmed under the lock if absent."""
        async with self._lock:
            if self._pool is None:
                pool = ProcessPoolExecutor(max_workers=MAX_WORKERS, initializer=_init_worker)
                await self._warm(pool)
                self._pool = pool
            return self._pool

    async def warm(self) -> None:
        """Spawn and warm the workers ahead of the first answer."""
        await self._ensure()

    async def _retire(self, stale: ProcessPoolExecutor) -> None:
        """Kill ``stale`` if it is still current. Only the caller that wins the swap kills."""
        async with self._lock:
            if self._pool is not stale:
                return
            self._pool = None
        await asyncio.to_thread(_kill, stale)

    async def check(self, problem: Problem, latex: str) -> CheckResult:
        for _ in range(2):
            pool = await self._ensure()
            try:
                future = asyncio.get_running_loop().run_in_executor(
                    pool, self._worker, problem, latex
                )
                return await asyncio.wait_for(future, self._timeout)
            except TimeoutError:
                await self._retire(pool)
                return CheckResult(Verdict.UNREADABLE, None)
            except BrokenProcessPool:
                await self._retire(pool)
            except RuntimeError as err:
                if SHUTDOWN_MESSAGE not in str(err):
                    log.exception("checker worker raised")
                    return CheckResult(Verdict.UNREADABLE, None)
            except Exception:
                log.exception("checker worker raised")
                return CheckResult(Verdict.UNREADABLE, None)
        return CheckResult(Verdict.UNREADABLE, None)

    def close(self) -> None:
        pool, self._pool = self._pool, None
        if pool is not None:
            _kill(pool)
