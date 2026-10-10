import unittest

import tests  # noqa: F401  (sets sys.path)
from breathebuddy import config
from breathebuddy.ingest import (_openaq_pm25, fetch_openaq, fetch_readings,
                                 pm25_to_aqi)


class TestIngestFeed(unittest.TestCase):
    def test_pm25_to_aqi_breakpoints(self):
        self.assertEqual(pm25_to_aqi(0), 0.0)
        self.assertEqual(pm25_to_aqi(30), 50.0)
        self.assertEqual(pm25_to_aqi(60), 100.0)
        self.assertEqual(pm25_to_aqi(45), 75.5)      # linear sub-index
        self.assertEqual(pm25_to_aqi(90), 200.0)
        self.assertEqual(pm25_to_aqi(500), 500.0)
        self.assertEqual(pm25_to_aqi(9999), 500.0)   # clamps at the ceiling
        self.assertEqual(pm25_to_aqi(-5), 0.0)       # clamps at zero

    def test_openaq_pm25_parsing(self):
        loc = {"sensors": [
            {"parameter": {"name": "pm10"}, "latest": {"value": 120.0}},
            {"parameter": {"name": "pm25"}, "latest": {"value": 85.0}},
        ]}
        self.assertEqual(_openaq_pm25(loc), 85.0)
        self.assertIsNone(_openaq_pm25({"sensors": [
            {"parameter": {"name": "pm10"}, "latest": {"value": 1.0}}]}))

    def test_missing_key_raises(self):
        original = config.OPENAQ_API_KEY
        try:
            config.OPENAQ_API_KEY = ""
            with self.assertRaises(RuntimeError):
                fetch_openaq()
        finally:
            config.OPENAQ_API_KEY = original

    def test_live_feed_falls_back_to_mock(self):
        original = config.AQ_SOURCE
        try:
            config.AQ_SOURCE = "openaq"  # no API key -> live call fails
            readings = fetch_readings()
        finally:
            config.AQ_SOURCE = original
        self.assertTrue(readings)                        # mock feed is non-empty
        self.assertFalse(readings[0].station_id.startswith("openaq-"))

    def test_default_source_is_mock(self):
        readings = fetch_readings()
        self.assertTrue(readings)
        self.assertTrue(all(r.aqi > 0 for r in readings))

    def test_unknown_source_uses_mock(self):
        original = config.AQ_SOURCE
        try:
            config.AQ_SOURCE = "does-not-exist"
            readings = fetch_readings()
        finally:
            config.AQ_SOURCE = original
        self.assertTrue(readings)


if __name__ == "__main__":
    unittest.main()
