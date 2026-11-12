from __future__ import annotations

import time
from collections import deque


class RateLimiter:
    """Best-effort in-memory limiter. Resets when the server restarts."""

    def __init__(self, window: int, limit: int) -> None:
        self.window = max(window, 1)
        self.limit = max(limit, 1)
        self._hits: dict[str, deque[float]] = {}

    def allow(self, key: str) -> tuple[bool, int]:
        """Return (allowed, seconds_until_next_slot)."""
        now = time.time()
        bucket = self._hits.setdefault(key, deque())
        while bucket and now - bucket[0] > self.window:
            bucket.popleft()
        if len(bucket) >= self.limit:
            wait = int(self.window - (now - bucket[0])) + 1
            return False, max(wait, 1)
        bucket.append(now)
        return True, 0

    def prune(self) -> None:
        now = time.time()
        dead = [k for k, b in self._hits.items() if not b or now - b[-1] > self.window]
        for key in dead:
            self._hits.pop(key, None)
