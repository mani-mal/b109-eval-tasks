"""Token-bucket rate limiting with an injectable clock.

A bucket holds up to ``capacity`` tokens and gains ``refill_rate`` tokens per
second, continuously, never exceeding ``capacity``. Taking ``n`` tokens
succeeds only if ``n`` are available.
"""

from __future__ import annotations

import time
from collections.abc import Callable

__all__ = ["TokenBucket"]

Clock = Callable[[], float]


class TokenBucket:
    def __init__(
        self,
        capacity: float,
        refill_rate: float,
        *,
        clock: Clock = time.monotonic,
        initial: float | None = None,
    ) -> None:
        if capacity <= 0:
            raise ValueError("capacity must be positive")
        if refill_rate <= 0:
            raise ValueError("refill_rate must be positive")
        start = capacity if initial is None else initial
        if not 0 <= start <= capacity:
            raise ValueError("initial must be between 0 and capacity")
        self.capacity = float(capacity)
        self.refill_rate = float(refill_rate)
        self._clock = clock
        self._tokens = float(start)
        self._last = clock()

    def _elapsed(self, now: float) -> float:
        # A clock that steps backwards must not drain the bucket.
        return max(0.0, now - self._last)

    def _check_request(self, n: float) -> None:
        if n <= 0:
            raise ValueError("n must be positive")
        if n > self.capacity:
            raise ValueError(f"cannot take {n} tokens from a bucket of {self.capacity}")

    def available(self) -> float:
        """Tokens that could be taken right now."""
        now = self._clock()
        return min(self.capacity, self._tokens + self._elapsed(now) * self.refill_rate)

    def try_acquire(self, n: float = 1) -> bool:
        """Take ``n`` tokens if they are available. Never blocks."""
        self._check_request(n)
        now = self._clock()
        self._tokens = min(self.capacity, self._tokens + self._elapsed(now) * self.refill_rate)
        if self._tokens < n:
            return False
        self._tokens -= n
        self._last = now
        return True

    def time_until(self, n: float = 1) -> float:
        """Seconds until ``n`` tokens will be available (0.0 if they already are)."""
        self._check_request(n)
        deficit = n - self.available()
        return max(0.0, deficit / self.refill_rate)

    def reset(self) -> None:
        """Refill the bucket completely."""
        self._tokens = self.capacity
        self._last = self._clock()
