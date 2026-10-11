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

    def test_alerts_list_is_bounded(self):
        # The in-memory alert list must not grow without limit in a long-running
        # process (DynamoDB holds the durable history on AWS).
        from breathebuddy.models import Alert
        saved = list(STORE.alerts)
        original = STORE._append_outbox
        STORE._append_outbox = lambda alert: None
        try:
            for i in range(600):
                STORE.add_alert(
                    Alert.create(target=f"t{i}", kind="k", aqi=200, message="m"))
            self.assertLessEqual(len(STORE.alerts), 500)
        finally:
            STORE._append_outbox = original
            with STORE._lock:
                STORE.alerts = saved


if __name__ == "__main__":
    unittest.main()
