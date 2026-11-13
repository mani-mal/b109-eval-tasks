"""Order and run jobs that depend on each other.

Jobs run in a topological order: every job after all of its dependencies.
When several jobs are ready at once, the one added first goes first, so the
order is deterministic.

A job may be given several ``attempts``; a failing call is then retried with
exponential backoff (see :mod:`b109tasks.retry`), sleeping through the
scheduler's injectable ``sleep``.

``run(budget=...)`` limits a run's total time, measured with the scheduler's
``clock`` from the start of the run. No job starts once the budget is used
up, and a started job is never interrupted, but its retries respect what is
left of the budget exactly as retry()'s ``max_elapsed`` does.
"""

from __future__ import annotations

import time
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from typing import Any

from .retry import RetryError, retry

__all__ = ["BudgetExceeded", "CycleError", "JobFailed", "RunReport", "Scheduler",
           "UnknownJobError"]


class CycleError(ValueError):
    """Dependencies form a cycle. ``cycle`` lists it, first job repeated at the end."""

    def __init__(self, cycle: list[str]) -> None:
        super().__init__("dependency cycle: " + " -> ".join(cycle))
        self.cycle = cycle


class UnknownJobError(KeyError):
    pass


class JobFailed(RuntimeError):
    """A job failed on every attempt. ``error`` is the exception from its last call."""

    def __init__(self, job: str, error: BaseException, attempts: int = 1) -> None:
        super().__init__(f"job {job!r} failed after {attempts} attempt(s): {error!r}")
        self.job = job
        self.error = error
        self.attempts = attempts


class BudgetExceeded(RuntimeError):
    """The run's time budget was used up before ``job`` could start."""

    def __init__(self, job: str, budget: float) -> None:
        super().__init__(f"time budget of {budget}s used up before job {job!r}")
        self.job = job
        self.budget = budget


@dataclass
class RunReport:
    """Outcome of ``Scheduler.run(keep_going=True)``. Dicts are in run order."""

    status: dict[str, str] = field(default_factory=dict)
    results: dict[str, Any] = field(default_factory=dict)
    errors: dict[str, BaseException] = field(default_factory=dict)
    attempts: dict[str, int] = field(default_factory=dict)

    @property
    def ok(self) -> bool:
        return all(s == "ok" for s in self.status.values())


class Scheduler:
    def __init__(
        self,
        *,
        sleep: Callable[[float], Any] = time.sleep,
        clock: Callable[[], float] | None = None,
        base_delay: float = 0.5,
    ) -> None:
        self._deps: dict[str, list[str]] = {}
        self._funcs: dict[str, Callable[[], Any] | None] = {}
        self._attempts: dict[str, int] = {}
        self._sleep = sleep
        self._clock = clock
        self._base_delay = base_delay

    def add(self, name: str, deps: Iterable[str] = (), *,
            func: Callable[[], Any] | None = None, attempts: int = 1) -> None:
        if name in self._deps:
            raise ValueError(f"job {name!r} already added")
        if attempts < 1:
            raise ValueError("attempts must be at least 1")
        self._deps[name] = list(dict.fromkeys(deps))
        self._funcs[name] = func
        self._attempts[name] = attempts

    def __contains__(self, name: object) -> bool:
        return name in self._deps

    def __len__(self) -> int:
        return len(self._deps)

    def order(self) -> list[str]:
        """All jobs in run order. Raises CycleError or UnknownJobError."""
        for name, deps in self._deps.items():
            for dep in deps:
                if dep not in self._deps:
                    raise UnknownJobError(f"{name!r} depends on unknown job {dep!r}")
        position = {name: i for i, name in enumerate(self._deps)}
        waiting = {name: len(deps) for name, deps in self._deps.items()}
        dependents: dict[str, list[str]] = {name: [] for name in self._deps}
        for name, deps in self._deps.items():
            for dep in deps:
                dependents[dep].append(name)

        ready = [name for name, count in waiting.items() if count == 0]
        result: list[str] = []
        while ready:
            ready.sort(key=position.__getitem__)
            name = ready.pop(0)
            result.append(name)
            for child in dependents[name]:
                waiting[child] -= 1
                if waiting[child] == 0:
                    ready.append(child)
        if len(result) < len(self._deps):
            remaining = [n for n in self._deps if waiting[n] > 0]
            raise CycleError(self._find_cycle(set(remaining), remaining[0]))
        return result

    def _find_cycle(self, remaining: set[str], start: str) -> list[str]:
        # Every remaining job still waits on another remaining job, so
        # following those edges must eventually revisit a job.
        path: list[str] = []
        seen: dict[str, int] = {}
        node = start
        while node not in seen:
            seen[node] = len(path)
            path.append(node)
            node = next(d for d in self._deps[node] if d in remaining)
        return path + [node]

    def dependents_of(self, name: str) -> list[str]:
        """Every job that depends on ``name``, directly or not, in run order."""
        if name not in self._deps:
            raise UnknownJobError(name)
        found: set[str] = set()
        frontier = [name]
        while frontier:
            current = frontier.pop()
            for job, deps in self._deps.items():
                if current in deps and job not in found:
                    found.add(job)
                    frontier.append(job)
        return [job for job in self.order() if job in found]

    def _call(self, name: str, max_elapsed: float | None = None) -> tuple[Any, int]:
        """Run one job with its retries. Returns (result, calls made)."""
        func = self._funcs[name]
        if func is None:
            return None, 0
        calls = 0

        def attempt() -> Any:
            nonlocal calls
            calls += 1
            return func()

        try:
            value = retry(attempt, attempts=self._attempts[name], base_delay=self._base_delay,
                          sleep=self._sleep, clock=self._clock, max_elapsed=max_elapsed)
        except RetryError as exc:
            raise JobFailed(name, exc.last, calls) from exc.last
        return value, calls

    def run(self, *, keep_going: bool = False, budget: float | None = None) -> Any:
        """Run every job in order.

        By default, return each job's result and stop at the first job that
        fails on all its attempts, raising :class:`JobFailed`. With
        ``keep_going=True``, run everything that does not depend on a failed
        job and return a :class:`RunReport`; a job whose dependency failed or
        was skipped is skipped without being called.

        With a ``budget`` (seconds), jobs that cannot start in time are skipped
        (keep-going) or :class:`BudgetExceeded` is raised (default mode).
        """
        if budget is not None and budget <= 0:
            raise ValueError("budget must be positive")
        if budget is not None and self._clock is None:
            raise ValueError("a budget needs a clock")
        order = self.order()
        started = self._clock() if self._clock is not None else 0.0

        def left() -> float | None:
            if budget is None or self._clock is None:
                return None
            return budget - (self._clock() - started)

        if not keep_going:
            results: dict[str, Any] = {}
            for name in order:
                remaining = left()
                if remaining is not None and remaining <= 0:
                    raise BudgetExceeded(name, budget)
                results[name], _ = self._call(name, remaining)
            return results
        report = RunReport()
        for name in order:
            if any(report.status[dep] != "ok" for dep in self._deps[name]):
                report.status[name] = "skipped"
                report.attempts[name] = 0
                continue
            remaining = left()
            if remaining is not None and remaining <= 0:
                report.status[name] = "skipped"
                report.attempts[name] = 0
                continue
            try:
                report.results[name], report.attempts[name] = self._call(name, remaining)
            except JobFailed as exc:
                report.status[name] = "failed"
                report.errors[name] = exc.error
                report.attempts[name] = exc.attempts
            else:
                report.status[name] = "ok"
        return report
