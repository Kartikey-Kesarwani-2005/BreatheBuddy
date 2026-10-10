import unittest
from unittest import mock

import tests  # noqa: F401  (sets sys.path)
from breathebuddy import config
from breathebuddy.nowcast import _clamp_aqi, build_grid, clean_index, nowcast_point
from breathebuddy.service import bootstrap
from breathebuddy.store import STORE, Store


class TestNowcast(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        bootstrap()

    def test_grid_shape(self):
        cells = build_grid(STORE)
        self.assertEqual(len(cells), config.GRID_ROWS * config.GRID_COLS)

    def test_forecast_length(self):
        cells = build_grid(STORE)
        cell = next(iter(cells.values()))
        self.assertEqual(len(cell.aqi_forecast), config.FORECAST_HOURS)

    def test_clean_index_bounds(self):
        self.assertEqual(clean_index(0), 100.0)
        self.assertEqual(clean_index(300), 0.0)
        self.assertTrue(0 <= clean_index(150) <= 100)

    def test_point_nowcast(self):
        nc = nowcast_point(28.6129, 77.2295, STORE)
        self.assertIn("aqi_now", nc)
        self.assertEqual(len(nc["aqi_forecast"]), config.FORECAST_HOURS)
        self.assertGreater(nc["aqi_now"], 0)

    def test_aqi_clamped_0_500(self):
        self.assertEqual(_clamp_aqi(-12), 0.0)
        self.assertEqual(_clamp_aqi(999), 500.0)

    def test_empty_grid_returns_neutral(self):
        # No grid data at all -> a neutral response, no division by zero.
        with mock.patch("breathebuddy.nowcast.build_grid", return_value={}):
            nc = nowcast_point(28.6, 77.2, Store())
        self.assertEqual(nc["aqi_now"], 0.0)
        self.assertEqual(nc["engine"], "empty")
        self.assertEqual(len(nc["aqi_forecast"]), config.FORECAST_HOURS)


if __name__ == "__main__":
    unittest.main()
