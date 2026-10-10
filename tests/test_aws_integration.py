import unittest

import tests  # noqa: F401  (sets sys.path)
from breathebuddy import config
from breathebuddy.awsio import AWSBridge, invoke_sagemaker
from breathebuddy.nowcast import nowcast_point
from breathebuddy.service import bootstrap
from breathebuddy.store import STORE


class TestAwsIntegration(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        bootstrap()

    def test_awsbridge_disabled_degrades_gracefully(self):
        bridge = AWSBridge(connect=False)
        self.assertFalse(bridge.enabled)
        # every AWS call is a safe no-op offline
        self.assertFalse(bridge.send_to_queue({"type": "alert"})["queued"])
        self.assertFalse(bridge.publish_alert(None)["delivered"])
        bridge.put_metric("Test", 1)          # must not raise
        bridge.archive_buffer([{"ts": "x"}])  # must not raise

    def test_store_buffer_roundtrip(self):
        STORE.drain_buffer()  # clear
        STORE.buffer_message({"type": "alert", "id": "a1"})
        drained = STORE.drain_buffer()
        self.assertEqual(len(drained), 1)
        self.assertEqual(drained[0]["id"], "a1")
        self.assertEqual(STORE.drain_buffer(), [])

    def test_nowcast_reports_engine(self):
        nc = nowcast_point(28.6129, 77.2295, STORE)
        self.assertEqual(nc["engine"], "local")

    def test_sagemaker_disabled_without_endpoint(self):
        self.assertEqual(config.SAGEMAKER_ENDPOINT, "")
        self.assertIsNone(invoke_sagemaker({"lat": 28.6, "lon": 77.2}))


if __name__ == "__main__":
    unittest.main()
