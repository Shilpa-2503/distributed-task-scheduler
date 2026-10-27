import unittest

from app.backoff import backoff_seconds


class BackoffTests(unittest.TestCase):
    def test_grows_exponentially_without_jitter(self):
        self.assertEqual(backoff_seconds(1, base=2, cap=1000, jitter=False), 2)
        self.assertEqual(backoff_seconds(2, base=2, cap=1000, jitter=False), 4)
        self.assertEqual(backoff_seconds(5, base=2, cap=1000, jitter=False), 32)

    def test_is_capped(self):
        self.assertEqual(backoff_seconds(20, base=2, cap=300, jitter=False), 300)

    def test_jitter_stays_between_half_and_full_delay(self):
        for _ in range(200):
            d = backoff_seconds(4, base=2, cap=1000, jitter=True)
            self.assertGreaterEqual(d, 8)
            self.assertLessEqual(d, 16)


if __name__ == "__main__":
    unittest.main()
