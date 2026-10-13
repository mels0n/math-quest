# pyright: reportPrivateUsage=false
"""Run the answer checker in worker processes under a hard time bound.

SymPy work cannot be interrupted in-process, so a check that overruns is
abandoned by terminating its worker process and replacing the pool.
"""

import asyncio
from collections.abc import Callable
from concurrent.futures import ProcessPoolExecutor
from concurrent.futures.process import BrokenProcessPool

from mathquest.engine.checker.check import CheckResult, Verdict, check
from mathquest.engine.types import Problem

CHECK_TIMEOUT_SECONDS = 2.0
MAX_WORKERS = 2

Worker = Callable[[Problem, str], CheckResult]


def _run_check(problem: Problem, latex: str) -> CheckResult:
    return check(problem, latex)


def _kill(pool: ProcessPoolExecutor) -> None:
    """Terminate every worker of ``pool`` and release it."""
    processes = list(pool._processes.values())
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

    def _current(self) -> ProcessPoolExecutor:
        if self._pool is None:
            self._pool = ProcessPoolExecutor(max_workers=MAX_WORKERS)
        return self._pool

    async def _replace(self, stale: ProcessPoolExecutor) -> None:
        """Swap in a fresh pool unless another caller already did, and kill ``stale``."""
        async with self._lock:
            if self._pool is stale:
                self._pool = None
        await asyncio.to_thread(_kill, stale)

    async def check(self, problem: Problem, latex: str) -> CheckResult:
        for attempt in range(2):
            pool = self._current()
            try:
                future = asyncio.get_running_loop().run_in_executor(
                    pool, self._worker, problem, latex
                )
                return await asyncio.wait_for(future, self._timeout)
            except TimeoutError:
                await self._replace(pool)
                return CheckResult(Verdict.UNREADABLE, None)
            except (BrokenProcessPool, RuntimeError):
                await self._replace(pool)
                if attempt == 1:
                    break
        return CheckResult(Verdict.UNREADABLE, None)

    def close(self) -> None:
        pool, self._pool = self._pool, None
        if pool is not None:
            _kill(pool)
