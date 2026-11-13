import unittest

from b109tasks.ratelimit import TokenBucket
from b109tasks.retry import RetryError, backoff_delays, retry, retrying


class Flaky:
    def __init__(self, failures, exc=ConnectionError):
        self.failures = failures
        self.calls = 0
        self.exc = exc

    def __call__(self):
        self.calls += 1
        if self.calls <= self.failures:
            raise self.exc(f"failure {self.calls}")
        return "ok"


class BackoffTest(unittest.TestCase):
    def test_delays(self):
        self.assertEqual(backoff_delays(4, 0.5, 2, 30), [0.5, 1.0, 2.0])
        self.assertEqual(backoff_delays(5, 1, 3, 5), [1, 3, 5, 5])
        self.assertEqual(backoff_delays(1, 1, 2, 10), [])

    def test_invalid(self):
        with self.assertRaises(ValueError):
            backoff_delays(0, 1, 2, 10)
        with self.assertRaises(ValueError):
            backoff_delays(3, 1, 0.5, 10)


class RetryTest(unittest.TestCase):
    def test_succeeds_after_failures(self):
        slept = []
        fn = Flaky(2)
        self.assertEqual(retry(fn, attempts=3, base_delay=1, sleep=slept.append), "ok")
        self.assertEqual(fn.calls, 3)
        self.assertEqual(slept, [1, 2])

    def test_gives_up(self):
        fn = Flaky(5)
        with self.assertRaises(RetryError) as ctx:
            retry(fn, attempts=3, sleep=lambda s: None)
        self.assertEqual(ctx.exception.attempts, 3)
        self.assertIsInstance(ctx.exception.__cause__, ConnectionError)
        self.assertEqual(fn.calls, 3)

    def test_non_matching_error_propagates(self):
        fn = Flaky(1, exc=KeyError)
        with self.assertRaises(KeyError):
            retry(fn, retry_on=(ConnectionError,), sleep=lambda s: None)
        self.assertEqual(fn.calls, 1)

    def test_on_retry_callback(self):
        seen = []
        retry(Flaky(1), base_delay=0.25, sleep=lambda s: None,
              on_retry=lambda n, exc, delay: seen.append((n, type(exc).__name__, delay)))
        self.assertEqual(seen, [(1, "ConnectionError", 0.25)])

    def test_decorator(self):
        slept = []
        state = Flaky(1)

        @retrying(attempts=2, sleep=slept.append)
        def call(x):
            return state() + x

        self.assertEqual(call("!"), "ok!")
        self.assertEqual(len(slept), 1)


class MaxElapsedTest(unittest.TestCase):
    def test_budget_stops_retrying(self):
        now = [0.0]

        def fn():
            now[0] += 1
            raise ConnectionError("down")

        def sleep(seconds):
            now[0] += seconds

        with self.assertRaises(RetryError) as ctx:
            retry(fn, attempts=10, base_delay=1, max_elapsed=5, sleep=sleep, clock=lambda: now[0])
        self.assertEqual(ctx.exception.attempts, 3)


class LimiterTest(unittest.TestCase):
    def test_every_call_takes_a_token(self):
        now = [0.0]
        slept = []

        def sleep(seconds):
            slept.append(seconds)
            now[0] += seconds

        bucket = TokenBucket(1, 10, clock=lambda: now[0])
        fn = Flaky(2)
        self.assertEqual(retry(fn, attempts=3, base_delay=0, sleep=sleep, limiter=bucket), "ok")
        self.assertEqual(slept, [0, 0.1, 0, 0.1])
        self.assertEqual(bucket.available(), 0)


class SingleAttemptTest(unittest.TestCase):
    def test_delay_settings_ignored(self):
        self.assertEqual(retry(Flaky(0), attempts=1, factor=0.5, base_delay=-1), "ok")


if __name__ == "__main__":
    unittest.main()
