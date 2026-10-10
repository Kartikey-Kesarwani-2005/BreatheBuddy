"""Verify Amazon Cognito (or compatible) JWTs for the write endpoints.

Two modes:
  * No user pool / JWKS configured -> dev mode: any non-empty bearer token is
    accepted (keeps the offline demo friction-free).
  * A pool is configured -> the RS256 signature is verified against the pool's
    JWKS. Needs the optional ``PyJWT`` (+ ``cryptography``) extra; if it is not
    installed the check degrades to presence-only and logs a warning.
"""
from __future__ import annotations

import logging

from . import config

log = logging.getLogger("breathebuddy.auth")

# Only asymmetric signatures are accepted; "none" / symmetric tricks never pass.
_ALLOWED_ALGS = ("RS256", "ES256")


def issuer() -> str:
    if config.COGNITO_ISSUER:
        return config.COGNITO_ISSUER
    if config.COGNITO_USER_POOL_ID:
        return (f"https://cognito-idp.{config.AWS_REGION}.amazonaws.com/"
                f"{config.COGNITO_USER_POOL_ID}")
    return ""


def jwks_url() -> str:
    if config.COGNITO_JWKS_URL:
        return config.COGNITO_JWKS_URL
    return issuer() + "/.well-known/jwks.json"


def _claims_local() -> dict:
    return {"sub": "local-dev", "username": "local-dev", "mode": "dev"}


def _signing_key(token: str):
    """Resolve the JWKS signing key for a token (isolated for testability)."""
    import jwt
    return jwt.PyJWKClient(jwks_url()).get_signing_key_from_jwt(token)


def verify_token(token: str) -> dict | None:
    """Return decoded claims when the token is valid, otherwise ``None``."""
    if not token:
        return None
    if not (config.COGNITO_USER_POOL_ID or config.COGNITO_JWKS_URL):
        return _claims_local()          # dev mode: presence is enough
    try:
        import jwt
    except ImportError:
        # A pool IS configured, so write access must hinge on a real signature.
        # Fail closed (reject) instead of silently accepting anything.
        log.error("auth: PyJWT not installed but a user pool is configured; "
                  "rejecting protected writes until it is installed")
        return None
    try:
        header = jwt.get_unverified_header(token)
        if header.get("alg") not in _ALLOWED_ALGS:
            log.warning("auth: token signed with unsupported alg %r", header.get("alg"))
            return None
        signing = _signing_key(token)
        return jwt.decode(
            token, signing.key,
            algorithms=list(_ALLOWED_ALGS),
            audience=config.COGNITO_CLIENT_ID or None,
            issuer=issuer() or None,
            options={"verify_aud": bool(config.COGNITO_CLIENT_ID)},
        )
    except Exception as exc:  # noqa: BLE001 - any failure means unauthorised
        log.warning("auth: token rejected (%s)", exc)
        return None


def bearer(headers: dict) -> str:
    """Extract the raw token from a case-insensitive header mapping."""
    low = {k.lower(): v for k, v in (headers or {}).items()}
    auth = low.get("authorization", "") or ""
    return auth[len("Bearer "):].strip() if auth.startswith("Bearer ") else ""


def authorized(headers: dict) -> bool:
    """True when the request may perform a write."""
    if not config.REQUIRE_AUTH:
        return True
    return verify_token(bearer(headers)) is not None
