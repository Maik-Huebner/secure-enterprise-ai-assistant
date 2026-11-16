"""In-memory sliding-window rate limiter.

Sufficient for one API process. Several instances behind a load balancer would share limits in
Redis or enforce them at the gateway; that is documented as a production gap.
"""

from __future__ import annotations

import threading
import time
from collections import deque
from collections.abc import Callable


class SlidingWindowLimiter:
    """Allow at most ``limit`` events per ``window_seconds`` and key."""

    def __init__(
        self,
        limit: int,
        window_seconds: float,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.limit = limit
        self.window = window_seconds
        self._clock = clock
        self._events: dict[str, deque[float]] = {}
        self._lock = threading.Lock()

    def check(self, key: str) -> tuple[bool, int]:
        """Register one event; return (allowed, retry_after_seconds)."""
        now = self._clock()
        with self._lock:
            events = self._events.setdefault(key, deque())
            while events and events[0] <= now - self.window:
                events.popleft()
            if len(events) >= self.limit:
                return False, max(1, int(events[0] + self.window - now) + 1)
            events.append(now)
            return True, 0
