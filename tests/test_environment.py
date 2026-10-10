import unittest

import tests  # noqa: F401  (sets sys.path)
from breathebuddy import config
from breathebuddy.nowcast import build_grid, load_events
from breathebuddy.service import bootstrap, environmental_events, indoor_advisory, school_today
from breathebuddy.store import STORE


class TestEnvironment(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        bootstrap()

    def test_stubble_event_loaded(self):
        events = load_events()
        self.assertTrue(any(e["type"] == "stubble_burning" for e in events))

    def test_plume_raises_downwind_aqi(self):
        original = config.USE_STUBBLE
        try:
            config.USE_STUBBLE = True
            with_plume = build_grid(STORE)
            config.USE_STUBBLE = False
            without = build_grid(STORE)
        finally:
            config.USE_STUBBLE = original
            build_grid(STORE)  # restore the grid with default settings
        # Some cell downwind must be higher with the plume than without.
        diffs = [with_plume[k].aqi_now - without[k].aqi_now for k in with_plume]
        self.assertGreater(max(diffs), 1.0)
        self.assertGreater(max(c.plume for c in with_plume.values()), 0.0)

    def test_indoor_advisory_scales_with_aqi(self):
        self.assertTrue(any("purifier" in t.lower() for t in indoor_advisory(250)))
        self.assertTrue(indoor_advisory(80))
        self.assertTrue(indoor_advisory(340))

    def test_school_today_has_indoor_and_events(self):
        card = school_today("ABC")
        self.assertIn("indoor_advisory", card)
        self.assertGreater(card["indoor_aqi_estimate"], 0)
        self.assertTrue(card["indoor_advisory"])

    def test_environmental_events_summary(self):
        evs = environmental_events()
        self.assertTrue(evs)
        self.assertIn("source", evs[0])


if __name__ == "__main__":
    unittest.main()
