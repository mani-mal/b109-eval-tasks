import unittest

from b109tasks.ratelimit import TokenBucket


class FakeClock:
    def __init__(self, now=100.0):
        self.now = now

    def __call__(self):
        return self.now

    def advance(self, seconds):
        self.now += seconds


class TokenBucketTest(unittest.TestCase):
    def setUp(self):
        self.clock = FakeClock()

    def test_starts_full_and_drains(self):
        bucket = TokenBucket(3, 1, clock=self.clock)
        self.assertEqual([bucket.try_acquire() for _ in range(4)], [True, True, True, False])

    def test_refills_over_time(self):
        bucket = TokenBucket(2, 0.5, clock=self.clock)
        self.assertTrue(bucket.try_acquire(2))
        self.clock.advance(2)
        self.assertAlmostEqual(bucket.available(), 1.0)
        self.assertTrue(bucket.try_acquire())
        self.assertFalse(bucket.try_acquire())

    def test_never_exceeds_capacity(self):
        bucket = TokenBucket(5, 10, clock=self.clock, initial=0)
        self.clock.advance(60)
        self.assertEqual(bucket.available(), 5.0)

    def test_clock_going_backwards(self):
        bucket = TokenBucket(2, 1, clock=self.clock, initial=1)
        self.clock.advance(-10)
        self.assertEqual(bucket.available(), 1.0)

    def test_time_until(self):
        bucket = TokenBucket(4, 2, clock=self.clock, initial=1)
        self.assertEqual(bucket.time_until(1), 0.0)
        self.assertAlmostEqual(bucket.time_until(4), 1.5)

    def test_bad_requests(self):
        bucket = TokenBucket(2, 1, clock=self.clock)
        for n in (0, -1, 3):
            with self.subTest(n=n), self.assertRaises(ValueError):
                bucket.try_acquire(n)
        with self.assertRaises(ValueError):
            TokenBucket(0, 1)
        with self.assertRaises(ValueError):
            TokenBucket(1, 1, initial=2)

    def test_reset(self):
        bucket = TokenBucket(2, 1, clock=self.clock)
        bucket.try_acquire(2)
        bucket.reset()
        self.assertEqual(bucket.available(), 2.0)


class AcquireTest(unittest.TestCase):
    def test_waits_for_token(self):
        clock = FakeClock()
        bucket = TokenBucket(1, 1, clock=clock)
        self.assertTrue(bucket.acquire())
        self.assertTrue(bucket.acquire(sleep=clock.advance, timeout=1.0))
        self.assertEqual(clock.now, 101.0)


if __name__ == "__main__":
    unittest.main()
