import time
import unittest
from unittest import mock

import tests  # noqa: F401  (sets sys.path)
from breathebuddy import auth, config


class TestAuthDevMode(unittest.TestCase):
    def test_empty_token_rejected(self):
        self.assertIsNone(auth.verify_token(""))

    def test_presence_accepted_without_pool(self):
        self.assertEqual(auth.verify_token("anything")["mode"], "dev")

    def test_bearer_extraction(self):
        self.assertEqual(auth.bearer({"Authorization": "Bearer tok123"}), "tok123")
        self.assertEqual(auth.bearer({"authorization": "Bearer abc"}), "abc")
        self.assertEqual(auth.bearer({"Authorization": "Basic x"}), "")
        self.assertEqual(auth.bearer({}), "")

    def test_authorized_respects_flag(self):
        original = config.REQUIRE_AUTH
        try:
            config.REQUIRE_AUTH = False
            self.assertTrue(auth.authorized({}))
            config.REQUIRE_AUTH = True
            self.assertFalse(auth.authorized({}))
            self.assertTrue(auth.authorized({"Authorization": "Bearer x"}))
        finally:
            config.REQUIRE_AUTH = original


class TestAuthJwt(unittest.TestCase):
    """RS256 signature checks against a locally generated key pair."""

    @classmethod
    def setUpClass(cls):
        try:
            import jwt
            from cryptography.hazmat.primitives.asymmetric import rsa
        except ImportError:  # pragma: no cover - optional extra
            raise unittest.SkipTest("PyJWT + cryptography not installed") from None
        cls.jwt = jwt
        cls.private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)

    def setUp(self):
        self._saved = (config.COGNITO_USER_POOL_ID, config.COGNITO_CLIENT_ID,
                       config.COGNITO_ISSUER, config.COGNITO_JWKS_URL)
        config.COGNITO_USER_POOL_ID = "us-east-1_TESTPOOL"
        config.COGNITO_CLIENT_ID = "client-123"
        config.COGNITO_ISSUER = "https://issuer.test"
        config.COGNITO_JWKS_URL = "https://issuer.test/.well-known/jwks.json"

    def tearDown(self):
        (config.COGNITO_USER_POOL_ID, config.COGNITO_CLIENT_ID,
         config.COGNITO_ISSUER, config.COGNITO_JWKS_URL) = self._saved

    def _token(self, **claims):
        base = {"sub": "user-1", "aud": "client-123", "iss": "https://issuer.test",
                "exp": int(time.time()) + 3600}
        base.update(claims)
        return self.jwt.encode(base, self.private_key, algorithm="RS256",
                               headers={"kid": "key-1"})

    def _patch_signing(self):
        signing = mock.Mock()
        signing.key = self.private_key.public_key()
        return mock.patch.object(auth, "_signing_key", return_value=signing)

    def test_valid_token_decoded(self):
        with self._patch_signing():
            claims = auth.verify_token(self._token())
        self.assertEqual(claims["sub"], "user-1")

    def test_expired_token_rejected(self):
        with self._patch_signing():
            self.assertIsNone(auth.verify_token(self._token(exp=int(time.time()) - 10)))

    def test_wrong_audience_rejected(self):
        with self._patch_signing():
            self.assertIsNone(auth.verify_token(self._token(aud="someone-else")))

    def test_wrong_issuer_rejected(self):
        with self._patch_signing():
            self.assertIsNone(auth.verify_token(self._token(iss="https://evil.test")))

    def test_bad_signature_rejected(self):
        from cryptography.hazmat.primitives.asymmetric import rsa
        other = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        forged = self.jwt.encode({"sub": "x", "aud": "client-123",
                                  "iss": "https://issuer.test",
                                  "exp": int(time.time()) + 3600},
                                 other, algorithm="RS256", headers={"kid": "key-1"})
        with self._patch_signing():
            self.assertIsNone(auth.verify_token(forged))

    def test_alg_none_rejected(self):
        # "alg: none" (unsigned) tokens must never pass, even with valid claims.
        unsigned = self.jwt.encode({"sub": "x", "aud": "client-123",
                                    "iss": "https://issuer.test",
                                    "exp": int(time.time()) + 3600},
                                   key=None, algorithm="none")
        with self._patch_signing():
            self.assertIsNone(auth.verify_token(unsigned))

    def test_symmetric_alg_rejected(self):
        # HS256 uses a shared secret; only asymmetric algs are allowed.
        secret = self.jwt.encode({"sub": "x", "aud": "client-123",
                                  "iss": "https://issuer.test",
                                  "exp": int(time.time()) + 3600},
                                 key="shared-secret", algorithm="HS256")
        with self._patch_signing():
            self.assertIsNone(auth.verify_token(secret))


if __name__ == "__main__":
    unittest.main()
