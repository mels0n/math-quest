"""In-process sliding-window rate limiter. Correct for a single replica only."""

import ipaddress
import math
import threading
import time
from collections import deque
from collections.abc import Callable

from mathquest.shared.errors import RateLimited

Clock = Callable[[], float]

SIGNUP_LIMIT = 10
SIGNUP_WINDOW_S = 3600
AUTH_LIMIT = 30
AUTH_WINDOW_S = 600
ADMIN_LOGIN_LIMIT = 10
ADMIN_LOGIN_WINDOW_S = 600
ADMIN_LOGIN_GLOBAL_LIMIT = 30
ANSWER_LIMIT = 60
ANSWER_WINDOW_S = 60
PLACEMENT_START_LIMIT = 6
PLACEMENT_START_WINDOW_S = 3600
PLAY_LIMIT = 120
PLAY_WINDOW_S = 60
_SWEEP_INTERVAL_S = 60.0


def rate_bucket(ip: str) -> str:
    """IPv6 addresses share a bucket per /64; IPv4 and anything else are exact."""
    try:
        address = ipaddress.ip_address(ip)
    except ValueError:
        return ip
    if isinstance(address, ipaddress.IPv6Address):
        return str(ipaddress.ip_network(f"{address}/64", strict=False))
    return str(address)


class RateLimiter:
    def __init__(self, clock: Clock = time.monotonic) -> None:
        self._clock = clock
        self._lock = threading.Lock()
        self._hits: dict[tuple[str, str], deque[float]] = {}
        self._windows: dict[tuple[str, str], float] = {}
        self._last_sweep = clock()

    def hit(self, scope: str, key: str, *, limit: int, window_s: float) -> None:
        """Record one attempt; raises RateLimited when `limit` already fall inside the window.

        Slot creation, the check and the append happen in one critical section.
        """
        with self._lock:
            now = self._clock()
            if now - self._last_sweep >= _SWEEP_INTERVAL_S:
                self._sweep(now)
            slot = (scope, key)
            hits = self._hits.setdefault(slot, deque())
            self._windows[slot] = window_s
            while hits and hits[0] <= now - window_s:
                hits.popleft()
            if len(hits) >= limit:
                raise RateLimited(max(1, math.ceil(hits[0] + window_s - now)))
            hits.append(now)

    def _sweep(self, now: float) -> None:
        """Drop slots whose newest hit has left its window. Caller holds the lock."""
        self._last_sweep = now
        for slot, hits in list(self._hits.items()):
            if not hits or hits[-1] <= now - self._windows[slot]:
                del self._hits[slot]
                del self._windows[slot]
