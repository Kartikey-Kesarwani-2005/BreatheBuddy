import unittest

import tests  # noqa: F401  (sets sys.path)
from breathebuddy import alerts as alerting
from breathebuddy.service import bootstrap, subscribe
from breathebuddy.store import STORE


class TestAlerts(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        bootstrap()

    def setUp(self):
        # cooldown state is process-wide; reset so each test is independent
        STORE.reset_alert_state()

    def test_subscriber_threshold_fires_alert(self):
        before = len(STORE.alerts)
        # high-AQI hotspot, very low threshold => must fire
        subscribe({"name": "Tester", "lat": 28.646, "lon": 77.31,
                   "threshold_aqi": 10, "kind": "asthma"})
        fired = alerting.check_subscribers(STORE)
        self.assertGreaterEqual(len(fired), 1)
        self.assertGreater(len(STORE.alerts), before)

    def test_repeat_alerts_are_suppressed(self):
        school = next(iter(STORE.schools.values()))
        first = alerting.check_school(school, STORE)
        second = alerting.check_school(school, STORE)
        self.assertIsNotNone(first)
        self.assertIsNone(second, "duplicate alert should be suppressed by cooldown")

    def test_publish_delivers_via_mock_outbox(self):
        from breathebuddy.models import Alert
        a = Alert.create(target="t", kind="k", aqi=200, message="m")
        info = alerting.publish(a, STORE)
        self.assertTrue(info.get("delivered"))
        self.assertEqual(info.get("channel"), "mock-outbox")

    def test_school_alert_created_on_bad_day(self):
        school = next(iter(STORE.schools.values()))
        a = alerting.check_school(school, STORE)
        self.assertIsNotNone(a)


if __name__ == "__main__":
    unittest.main()
