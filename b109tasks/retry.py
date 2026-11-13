"""Retry a call with exponential backoff.

``sleep`` and ``clock`` are injectable so callers and tests never have to
wait for real. An optional rate ``limiter`` (anything with ``try_acquire()``
and ``time_until()``, such as :class:`b109tasks.ratelimit.TokenBucket`) paces
the calls.
"""

from __future__ import annotations

import functools
import time
from collections.abc import Callable
from typing import Any, Protocol, TypeVar

__all__ = ["RetryError", "backoff_delays", "retry", "retrying"]

T = TypeVar("T")


class Limiter(Protocol):
    def try_acquire(self, n: float = 1) -> bool: ...

    def time_until(self, n: float = 1) -> float: ...


class RetryError(Exception):
    """Raised when every attempt failed. ``__cause__`` is the last exception."""

    def __init__(self, attempts: int, last: BaseException) -> None:
        super().__init__(f"gave up after {attempts} attempt(s): {last!r}")
        self.attempts = attempts
        self.last = last


def backoff_delays(attempts: int, base_delay: float, factor: float,
                   max_delay: float | None = None) -> list[float]:
    """Delays slept between ``attempts`` tries: one fewer than ``attempts``.

    ``max_delay`` caps each delay; None means no cap.
    """
    if attempts < 1:
        raise ValueError("attempts must be at least 1")
    if base_delay < 0 or factor < 1 or max_delay < 0:
        raise ValueError("delays must be non-negative and factor at least 1")
    delays = []
    delay = base_delay
    for _ in range(attempts - 1):
        delays.append(min(delay, max_delay))
        delay *= factor
    return delays


def retry(
    fn: Callable[[], T],
    *,
    attempts: int = 3,
    base_delay: float = 0.1,
    factor: float = 2.0,
    max_delay: float | None = None,
    retry_on: tuple[type[BaseException], ...] = (Exception,),
    sleep: Callable[[float], Any] = time.sleep,
    on_retry: Callable[[int, BaseException, float], Any] | None = None,
    max_elapsed: float | None = None,
    clock: Callable[[], float] = time.monotonic,
    limiter: Limiter | None = None,
) -> T:
    """Call ``fn`` until it succeeds or ``attempts`` calls have failed.

    Only exceptions matching ``retry_on`` are retried; anything else
    propagates at once. ``on_retry(attempt, exc, delay)`` is called before
    each sleep, where ``attempt`` is the number of the call that just failed.
    When all attempts fail, :class:`RetryError` is raised from the last error.

    ``max_elapsed`` is an overall budget in seconds, measured with ``clock``
    from just before the first call. Before sleeping, retry() gives up (raising
    RetryError without sleeping) if the time used so far plus the next delay
    would exceed the budget; ending exactly on the budget is allowed.

    With a ``limiter``, every call (retries included) first takes one token,
    sleeping for ``limiter.time_until()`` whenever none is available.
    """
    delays = backoff_delays(attempts, base_delay, factor, max_delay)
    started = clock()
    for attempt in range(1, attempts + 1):
        elapsed = clock() - started
        if limiter is not None:
            _take_token(limiter, sleep)
        try:
            return fn()
        except retry_on as exc:
            if attempt == attempts:
                raise RetryError(attempts, exc) from exc
            delay = delays[attempt - 1]
            if max_elapsed is not None and elapsed + delay > max_elapsed:
                raise RetryError(attempt, exc) from exc
            if on_retry is not None:
                on_retry(attempt, exc, delay)
            sleep(delay)
    raise AssertionError("unreachable")


def _take_token(limiter: Limiter, sleep: Callable[[float], Any]) -> None:
    while not limiter.try_acquire():
        sleep(limiter.time_until())


def retrying(**options: Any) -> Callable[[Callable[..., T]], Callable[..., T]]:
    """Decorator form of :func:`retry`; ``options`` are passed through."""

    def decorate(func: Callable[..., T]) -> Callable[..., T]:
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> T:
            return retry(lambda: func(*args, **kwargs), **options)

        return wrapper

    return decorate
