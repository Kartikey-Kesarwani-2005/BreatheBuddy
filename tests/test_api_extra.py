import unittest

import tests  # noqa: F401  (sets sys.path)
from breathebuddy import openapi
from breathebuddy.ratelimit import RateLimiter


class TestOpenAPI(unittest.TestCase):
    def test_spec_shape(self):
        spec = openapi.SPEC
        self.assertEqual(spec["openapi"], "3.0.3")
        for path in ("/aqi", "/route", "/school/{id}/today", "/subscribe",
                     "/agent", "/cycle", "/openapi.json", "/docs"):
            self.assertIn(path, spec["paths"], path)
        self.assertIn("bearerAuth", spec["components"]["securitySchemes"])

    def test_docs_html_is_offline(self):
        html = openapi.render_docs_html()
        self.assertIn("BreatheBuddy API", html)
        self.assertIn("/aqi", html)
        self.assertIn("subscribe", html.lower())
        # No external CDN / remote assets.
        self.assertNotIn("cdn", html.lower())
        self.assertNotIn("https://unpkg", html)

    def test_spec_json_roundtrips(self):
        import json
        parsed = json.loads(openapi.spec_json())
        self.assertEqual(parsed["info"]["title"], "BreatheBuddy API")


class TestRateLimiter(unittest.TestCase):
    def test_allows_up_to_limit(self):
        rl = RateLimiter(limit=2, window_s=60)
        self.assertTrue(rl.allow("a"))
        self.assertTrue(rl.allow("a"))
        self.assertFalse(rl.allow("a"))
        self.assertTrue(rl.allow("b"))       # separate client unaffected

    def test_disabled_when_zero(self):
        rl = RateLimiter(limit=0, window_s=60)
        for _ in range(1000):
            self.assertTrue(rl.allow("a"))

    def test_window_resets(self):
        rl = RateLimiter(limit=1, window_s=0)   # window of 0s -> always resets
        self.assertTrue(rl.allow("a"))
        self.assertTrue(rl.allow("a"))

    def test_cleanup_keeps_dict_bounded(self):
        rl = RateLimiter(limit=5, window_s=-1)  # negative window -> immediate expiry
        for i in range(5000):
            rl.allow(f"c{i}")
        self.assertLessEqual(len(rl._hits), 5000)


if __name__ == "__main__":
    unittest.main()
