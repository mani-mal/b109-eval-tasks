import unittest

from b109tasks.scheduler import (
    BudgetExceeded, CycleError, JobFailed, RunReport, Scheduler, UnknownJobError,
)


class OrderTest(unittest.TestCase):
    def test_dependencies_first(self):
        s = Scheduler()
        s.add("deploy", ["build", "test"])
        s.add("test", ["build"])
        s.add("build")
        self.assertEqual(s.order(), ["build", "test", "deploy"])

    def test_ties_keep_insertion_order(self):
        s = Scheduler()
        for name in ["lint", "fmt", "build"]:
            s.add(name)
        s.add("package", ["build", "lint"])
        self.assertEqual(s.order(), ["lint", "fmt", "build", "package"])

    def test_unknown_dependency(self):
        s = Scheduler()
        s.add("a", ["ghost"])
        with self.assertRaises(UnknownJobError):
            s.order()

    def test_duplicate_job(self):
        s = Scheduler()
        s.add("a")
        with self.assertRaises(ValueError):
            s.add("a")

    def test_simple_cycle(self):
        s = Scheduler()
        s.add("a", ["b"])
        s.add("b", ["a"])
        with self.assertRaises(CycleError) as ctx:
            s.order()
        self.assertEqual(ctx.exception.cycle, ["a", "b", "a"])
        self.assertIn("a -> b -> a", str(ctx.exception))

    def test_self_cycle(self):
        s = Scheduler()
        s.add("a", ["a"])
        with self.assertRaises(CycleError) as ctx:
            s.order()
        self.assertEqual(ctx.exception.cycle, ["a", "a"])

    def test_dependents_of(self):
        s = Scheduler()
        s.add("base")
        s.add("mid", ["base"])
        s.add("other")
        s.add("top", ["mid"])
        self.assertEqual(s.dependents_of("base"), ["mid", "top"])
        self.assertEqual(s.dependents_of("other"), [])


class RunTest(unittest.TestCase):
    def test_runs_in_order(self):
        calls = []
        s = Scheduler()
        s.add("b", ["a"], func=lambda: calls.append("b") or 2)
        s.add("a", func=lambda: calls.append("a") or 1)
        s.add("c")
        self.assertEqual(s.run(), {"a": 1, "b": 2, "c": None})
        self.assertEqual(calls, ["a", "b"])

    def test_stops_on_failure(self):
        calls = []

        def boom():
            raise RuntimeError("boom")

        s = Scheduler()
        s.add("a", func=boom)
        s.add("b", func=lambda: calls.append("b"))
        with self.assertRaises(JobFailed) as ctx:
            s.run()
        self.assertEqual(ctx.exception.job, "a")
        self.assertEqual(ctx.exception.attempts, 1)
        self.assertEqual(calls, [])


class Flaky:
    def __init__(self, failures, value="ok"):
        self.failures = failures
        self.calls = 0
        self.value = value

    def __call__(self):
        self.calls += 1
        if self.calls <= self.failures:
            raise RuntimeError(f"failure {self.calls}")
        return self.value


class RetryTest(unittest.TestCase):
    def test_attempts_retry_with_backoff(self):
        slept = []
        s = Scheduler(sleep=slept.append, base_delay=1)
        job = Flaky(2)
        s.add("a", func=job, attempts=3)
        self.assertEqual(s.run(), {"a": "ok"})
        self.assertEqual(job.calls, 3)
        self.assertEqual(slept, [1, 2])

    def test_failure_after_all_attempts(self):
        s = Scheduler(sleep=lambda _: None)
        s.add("a", func=Flaky(5), attempts=2)
        with self.assertRaises(JobFailed) as ctx:
            s.run()
        self.assertEqual(ctx.exception.attempts, 2)
        self.assertEqual(str(ctx.exception.error), "failure 2")

    def test_bad_attempts(self):
        with self.assertRaises(ValueError):
            Scheduler().add("a", attempts=0)


class KeepGoingTest(unittest.TestCase):
    def test_report(self):
        s = Scheduler(sleep=lambda _: None)
        s.add("fetch", func=lambda: "data")
        s.add("parse", ["fetch"], func=Flaky(9), attempts=2)
        s.add("index", ["parse"], func=lambda: "never")
        s.add("lint", func=Flaky(1, 0), attempts=2)
        s.add("stats")
        report = s.run(keep_going=True)
        self.assertIsInstance(report, RunReport)
        self.assertEqual(report.status, {"fetch": "ok", "parse": "failed", "index": "skipped",
                                         "lint": "ok", "stats": "ok"})
        self.assertEqual(report.results, {"fetch": "data", "lint": 0, "stats": None})
        self.assertEqual(report.attempts, {"fetch": 1, "parse": 2, "index": 0, "lint": 2, "stats": 0})
        self.assertEqual(str(report.errors["parse"]), "failure 2")
        self.assertFalse(report.ok)


class BudgetTest(unittest.TestCase):
    def setUp(self):
        self.now = 0.0
        self.s = Scheduler(sleep=self.advance, clock=lambda: self.now, base_delay=1)

    def advance(self, seconds):
        self.now += seconds

    def job(self, cost, fail=False):
        def run():
            self.now += cost
            if fail:
                raise RuntimeError("down")
            return cost

        return run

    def test_jobs_skipped_once_budget_used(self):
        self.s.add("a", func=self.job(3))
        self.s.add("b", func=self.job(2))
        self.s.add("c", func=self.job(1))
        report = self.s.run(keep_going=True, budget=5)
        self.assertEqual(report.status, {"a": "ok", "b": "ok", "c": "skipped"})

    def test_retries_stop_within_budget(self):
        self.s.add("a", func=self.job(0, fail=True), attempts=5)
        report = self.s.run(keep_going=True, budget=3)
        self.assertEqual(report.attempts["a"], 3)
        self.assertEqual(self.now, 3)

    def test_default_mode(self):
        self.s.add("a", func=self.job(4))
        self.s.add("b", func=self.job(1))
        with self.assertRaises(BudgetExceeded) as ctx:
            self.s.run(budget=4)
        self.assertEqual(ctx.exception.job, "b")
        with self.assertRaises(ValueError):
            self.s.run(budget=0)


if __name__ == "__main__":
    unittest.main()
