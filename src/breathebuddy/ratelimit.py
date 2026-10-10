"""A tiny in-memory per-client rate limiter (fixed window).

Used by the write endpoints (``/subscribe``, ``/cycle``) to slow down accidental
loops and abusive clients. Deliberately simple: one counter per client per
window, no external store. Disabled when the configured limit is 0. Each Lambda
container gets its own limiter, which is fine -- API Gateway provides account-level
throttling in production.
"""
from __future__ import annotations

import threading
import time

from . import config


class RateLimiter:
    def __init__(self, limit: int, window_s: int = 60):
        self.limit = int(limit)
        self.window_s = int(window_s)
        self._hits: dict[str, list] = {}   # client -> [window_start, count]
        self._lock = threading.Lock()

    def allow(self, client: str) -> bool:
        """Return True if the client is under the limit, else False."""
        if self.limit <= 0:
            return True
        now = time.time()
        with self._lock:
            start, count = self._hits.get(client, (now, 0))
            if now - start >= self.window_s:
                start, count = now, 0
            count += 1
            self._hits[client] = (start, count)
            # Opportunistic cleanup so the dict cannot grow unbounded.
            if len(self._hits) > 4096:
                self._hits = {k: v for k, v in self._hits.items()
                              if now - v[0] < self.window_s}
            return count <= self.limit

    def retry_after(self) -> int:
        return self.window_s


# One limiter shared by the API process (write endpoints).
WRITE_LIMITER = RateLimiter(config.WRITE_RATE_LIMIT_PER_MIN, 60)
