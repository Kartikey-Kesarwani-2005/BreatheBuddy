import unittest

import tests  # noqa: F401  (sets sys.path)
from breathebuddy.policy import decide_activities, evaluate


class TestCedarPolicy(unittest.TestCase):
    def test_high_aqi_blocks_assembly(self):
        res = evaluate("hold_outdoor_assembly", {"predicted_aqi": 250,
                                                 "masks_available": True,
                                                 "time_limit_minutes": 45})
        self.assertFalse(res["allowed"])

    def test_low_aqi_allows_assembly(self):
        res = evaluate("hold_outdoor_assembly", {"predicted_aqi": 80,
                                                 "masks_available": True,
                                                 "time_limit_minutes": 45})
        self.assertTrue(res["allowed"])

    def test_pe_needs_masks_in_moderate_air(self):
        no_mask = evaluate("hold_physical_education", {"predicted_aqi": 180,
                                                       "masks_available": False,
                                                       "time_limit_minutes": 45})
        with_mask = evaluate("hold_physical_education", {"predicted_aqi": 180,
                                                         "masks_available": True,
                                                         "time_limit_minutes": 45})
        self.assertFalse(no_mask["allowed"])
        self.assertTrue(with_mask["allowed"])

    def test_hazardous_closes_school(self):
        res = decide_activities({"predicted_aqi": 340, "masks_available": True,
                                 "time_limit_minutes": 45})
        self.assertIn("close_school", res["allowed"])
        self.assertIn("hold_classes", res["blocked"])
        self.assertIn("indoor_activities", res["allowed"])

    def test_float_context_matches_integer_semantics(self):
        # Regression: real Cedar (cedarpy) default-denies on float context
        # (Long vs Decimal). AQI is integer-valued, so results must match ints.
        low = decide_activities({"predicted_aqi": 100.5, "masks_available": True,
                                 "time_limit_minutes": 45})
        high = decide_activities({"predicted_aqi": 153.6, "masks_available": True,
                                  "time_limit_minutes": 45})
        self.assertIn("hold_outdoor_assembly", low["allowed"])
        self.assertIn("hold_classes", low["allowed"])
        self.assertIn("hold_outdoor_assembly", high["blocked"])
        self.assertIn("hold_classes", high["allowed"])
        self.assertIn("indoor_activities", high["allowed"])

    def test_default_deny_unknown_activity(self):
        res = evaluate("teleport", {"predicted_aqi": 10, "masks_available": True,
                                    "time_limit_minutes": 45})
        self.assertFalse(res["allowed"])
        self.assertIn(res["engine"], ("cedar", "builtin-cedar"))


if __name__ == "__main__":
    unittest.main()
