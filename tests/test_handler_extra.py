import json
import unittest

import tests  # noqa: F401  (sets sys.path)


class TestLambdaApi(unittest.TestCase):
    """Parity checks for the deployed API Gateway handler."""

    @classmethod
    def setUpClass(cls):
        from infra.handler import app as lambda_app
        cls.app = lambda_app
        lambda_app._boot()

    def _call(self, method, path, query=None, body=None, raw_body=None):
        ev = {
            "httpMethod": method,
            "path": path,
            "queryStringParameters": query,
            "requestContext": {"identity": {"sourceIp": "203.0.113.9"}},
            "body": raw_body if raw_body is not None
            else (json.dumps(body) if body is not None else None),
        }
        res = self.app.lambda_api(ev, None)
        return res["statusCode"], json.loads(res["body"])

    def test_health_reports_data_source(self):
        sc, b = self._call("GET", "/health")
        self.assertEqual(sc, 200)
        self.assertIn("data_source", b)

    def test_api_prefix_aliases(self):
        for path in ("/api/health", "/api/alerts", "/api/stations", "/api/events"):
            sc, _ = self._call("GET", path)
            self.assertEqual(sc, 200, path)

    def test_api_root_alias_is_not_a_500(self):
        sc, _ = self._call("GET", "/api")
        self.assertEqual(sc, 404)   # normalised to "/", which has no route

    def test_unknown_api_route_404(self):
        sc, _ = self._call("GET", "/api/nope")
        self.assertEqual(sc, 404)

    def test_oversized_body_rejected(self):
        sc, _ = self._call("POST", "/agent", raw_body="x" * (self.app.MAX_BODY + 1))
        self.assertEqual(sc, 413)


if __name__ == "__main__":
    unittest.main()
