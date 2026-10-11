import json
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

import tests  # noqa: F401  (sets sys.path)
from breathebuddy import config, weather
from breathebuddy.ingest import (
    _openaq_pm25,
    effective_source,
    fetch_openaq,
    fetch_readings,
    pm25_to_aqi,
)
from breathebuddy.models import Reading
from breathebuddy.store import Store


class _EmptyCache:
    """Point the live-feed cache at a throwaway empty dir for a test."""

    def __enter__(self):
        self._orig = config.CACHE_DIR
        self._dir = Path(tempfile.mkdtemp())
        config.CACHE_DIR = self._dir
        return self._dir

    def __exit__(self, *exc):
        config.CACHE_DIR = self._orig
        for child in self._dir.glob("*"):
            child.unlink()
        self._dir.rmdir()


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
        original_src, original_key = config.AQ_SOURCE, config.OPENAQ_API_KEY
        try:
            config.AQ_SOURCE = "openaq"
            config.OPENAQ_API_KEY = ""   # force the live call to fail
            with _EmptyCache():          # and no cache to fall back to
                readings = fetch_readings()
        finally:
            config.AQ_SOURCE, config.OPENAQ_API_KEY = original_src, original_key
        self.assertTrue(readings)                        # bundle is non-empty
        self.assertFalse(readings[0].station_id.startswith("openaq-"))

    def test_default_source_is_live(self):
        self.assertEqual(config.AQ_SOURCE, "openaq")

    def test_missing_key_falls_back_to_bundled_by_default(self):
        original = config.OPENAQ_API_KEY
        try:
            config.OPENAQ_API_KEY = ""
            with _EmptyCache():
                readings = fetch_readings()
        finally:
            config.OPENAQ_API_KEY = original
        self.assertTrue(readings)
        self.assertFalse(readings[0].station_id.startswith("openaq-"))

    def test_unknown_source_uses_mock(self):
        original = config.AQ_SOURCE
        try:
            config.AQ_SOURCE = "does-not-exist"
            readings = fetch_readings()
        finally:
            config.AQ_SOURCE = original
        self.assertTrue(readings)


class TestCacheFallback(unittest.TestCase):
    def _write_cache(self, saved_at: float) -> None:
        config.CACHE_DIR.mkdir(parents=True, exist_ok=True)
        (config.CACHE_DIR / "openaq_readings.json").write_text(json.dumps({
            "saved_at": saved_at,
            "readings": [{"station_id": "openaq-99", "lat": 28.61, "lon": 77.19,
                          "aqi": 180.0, "pm25": 90.0}],
        }), "utf-8")

    def test_live_failure_uses_fresh_cache(self):
        original = (config.AQ_SOURCE, config.OPENAQ_API_KEY, config.WEATHER_ENABLED)
        try:
            with _EmptyCache():
                self._write_cache(time.time())
                config.AQ_SOURCE, config.OPENAQ_API_KEY = "openaq", ""
                config.WEATHER_ENABLED = False
                readings = fetch_readings()
                src = effective_source()
        finally:
            (config.AQ_SOURCE, config.OPENAQ_API_KEY,
             config.WEATHER_ENABLED) = original
        self.assertEqual(readings[0].station_id, "openaq-99")
        self.assertEqual(src["source"], "cache")
        self.assertTrue(src["live"])           # cached live data still counts as real
        self.assertFalse(src["fresh"])         # but flagged as not fresh

    def test_live_failure_ignores_stale_cache(self):
        original = (config.AQ_SOURCE, config.OPENAQ_API_KEY, config.WEATHER_ENABLED)
        try:
            with _EmptyCache():
                self._write_cache(time.time() - config.CACHE_MAX_AGE_S - 3600)
                config.AQ_SOURCE, config.OPENAQ_API_KEY = "openaq", ""
                config.WEATHER_ENABLED = False
                readings = fetch_readings()
                src = effective_source()
        finally:
            (config.AQ_SOURCE, config.OPENAQ_API_KEY,
             config.WEATHER_ENABLED) = original
        self.assertFalse(readings[0].station_id.startswith("openaq-"))
        self.assertEqual(src["source"], "mock")


class TestWeatherEnrichment(unittest.TestCase):
    def test_apply_sets_wind_only_when_missing(self):
        snap = {"wind_speed": 3.2, "wind_dir": 210.0}
        live = [Reading(station_id="openaq-1", lat=28.6, lon=77.2, aqi=150.0)]
        mock_readings = [Reading(station_id="ST-X", lat=28.6, lon=77.2, aqi=150.0, wind_speed=1.4)]
        with mock.patch.object(weather, "current", return_value=snap):
            weather.apply(live + mock_readings)
        self.assertEqual(live[0].wind_speed, 3.2)     # enriched
        self.assertEqual(live[0].wind_dir, 210.0)
        self.assertEqual(mock_readings[0].wind_speed, 1.4)     # left untouched

    def test_apply_noop_without_weather(self):
        r = [Reading(station_id="openaq-1", lat=28.6, lon=77.2, aqi=150.0)]
        with mock.patch.object(weather, "current", return_value=None):
            self.assertIsNone(weather.apply(r))
        self.assertEqual(r[0].wind_speed, 0.0)


class TestStoreReplace(unittest.TestCase):
    def test_put_readings_replaces_snapshot(self):
        st = Store()
        st.put_readings([Reading("a", 1, 1, 100), Reading("b", 2, 2, 110)])
        self.assertEqual(len(st.all_readings()), 2)
        st.put_readings([Reading("c", 3, 3, 120)])   # a full snapshot of one
        ids = [r.station_id for r in st.all_readings()]
        self.assertEqual(ids, ["c"])                 # old stations do not linger


if __name__ == "__main__":
    unittest.main()
