import unittest

import tests  # noqa: F401  (sets sys.path)
from breathebuddy.routing import find_routes
from breathebuddy.service import bootstrap
from breathebuddy.store import STORE


class TestRouting(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        bootstrap()

    def test_cleanest_not_worse_than_fastest(self):
        res = find_routes((28.60, 77.10), (28.60, 77.30), STORE)
        self.assertLessEqual(res["cleanest"]["avg_aqi"], res["fastest"]["avg_aqi"])
        self.assertGreaterEqual(res["aqi_saved_on_cleanest"], 0)

    def test_cleanest_is_longer_or_equal(self):
        res = find_routes((28.60, 77.10), (28.60, 77.30), STORE)
        self.assertGreaterEqual(res["cleanest"]["distance_m"], res["fastest"]["distance_m"])

    def test_routes_have_geometry(self):
        res = find_routes((28.60, 77.10), (28.60, 77.30), STORE)
        self.assertGreaterEqual(len(res["fastest"]["geometry"]), 2)
        self.assertEqual(res["winner"], "cleanest")


if __name__ == "__main__":
    unittest.main()
