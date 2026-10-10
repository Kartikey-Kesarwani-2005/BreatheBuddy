"""Central configuration for BreatheBuddy.

All values can be overridden with environment variables so the same code runs
locally (mock data) and on AWS (LocalStack / real services) without edits.
"""
from __future__ import annotations

import os
from pathlib import Path

# --- Paths ---------------------------------------------------------------
ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = Path(os.getenv("BB_DATA_DIR", ROOT / "data"))
FRONTEND_DIR = Path(os.getenv("BB_FRONTEND_DIR", ROOT / "frontend"))
POLICY_DIR = Path(__file__).resolve().parent / "policies"
OUTBOX = DATA_DIR / "alerts_outbox.json"
EVENTS_FILE = Path(os.getenv("BB_EVENTS_FILE", DATA_DIR / "events.json"))


def _f(name: str, default: float) -> float:
    return float(os.getenv(name, default))


def _i(name: str, default: int) -> int:
    return int(os.getenv(name, default))


def _b(name: str, default: bool) -> bool:
    return os.getenv(name, str(default)).lower() in ("1", "true", "yes", "on")


# --- Hyperlocal grid (500 m cells around a city centre) ------------------
CITY_NAME = os.getenv("BB_CITY", "Delhi")
CENTER_LAT = _f("BB_CENTER_LAT", 28.6100)
CENTER_LON = _f("BB_CENTER_LON", 77.1900)
GRID_RES_M = _i("BB_GRID_RES_M", 500)          # cell size in metres
GRID_ROWS = _i("BB_GRID_ROWS", 32)             # north-south cells (~16 km)
GRID_COLS = _i("BB_GRID_COLS", 44)             # east-west cells (~22 km)
FORECAST_HOURS = _i("BB_FORECAST_HOURS", 6)

# --- Networking ----------------------------------------------------------
HOST = os.getenv("BB_HOST", "127.0.0.1")
PORT = _i("BB_PORT", 8000)

# --- Air-quality data source ---------------------------------------------
# "openaq" = live OpenAQ v3 API (free key, set BB_OPENAQ_API_KEY). "mock" = the
# bundled deterministic feed, kept only as an offline fallback. Any live-feed
# error falls back to bundled data so a bad network never takes down the app.
AQ_SOURCE = os.getenv("BB_AQ_SOURCE", "openaq")
OPENAQ_API_KEY = os.getenv("BB_OPENAQ_API_KEY", "")
OPENAQ_BASE = os.getenv("BB_OPENAQ_BASE", "https://api.openaq.org/v3")
OPENAQ_RADIUS_M = _i("BB_OPENAQ_RADIUS_M", 25000)

# --- AWS integration flags ----------------------------------------------
# When USE_AWS is on, boto3 is used to talk to LocalStack or real AWS.
USE_AWS = _b("BB_USE_AWS", False)
# Use the LLM-backed Strands agent when true. Left off locally so the demo runs
# offline and instantly; on AWS (with Bedrock/credentials) set BB_USE_STRANDS=true.
USE_STRANDS = _b("BB_USE_STRANDS", False)
# Strands Agents SDK + Amazon Bedrock model config (used when USE_STRANDS is on).
# Model id is optional; when blank the SDK picks a region-appropriate default.
STRANDS_MODEL_ID = os.getenv("BB_STRANDS_MODEL", "")
# Bedrock API key (bearer token) works without AWS SigV4 credentials.
BEDROCK_API_KEY = os.getenv("BB_BEDROCK_API_KEY") or os.getenv("AWS_BEARER_TOKEN_BEDROCK", "")
# Stubble-burning plume (seasonal). Turn off to see the clean baseline.
USE_STUBBLE = _b("BB_STUBBLE_BURNING", True)
AWS_ENDPOINT = os.getenv("AWS_ENDPOINT_URL", "")     # e.g. http://localhost:4566
AWS_REGION = os.getenv("AWS_DEFAULT_REGION", "ap-south-1")
SNS_TOPIC_ARN = os.getenv("BB_SNS_TOPIC_ARN", "")
SQS_QUEUE_URL = os.getenv("BB_SQS_QUEUE_URL", "")
S3_RAW_BUCKET = os.getenv("BB_S3_RAW_BUCKET", "breathebuddy-raw")
DDB_READINGS_TABLE = os.getenv("BB_DDB_READINGS_TABLE", "breathebuddy-readings")
DDB_ALERTS_TABLE = os.getenv("BB_DDB_ALERTS_TABLE", "breathebuddy-alerts")
DDB_SUBSCRIBERS_TABLE = os.getenv("BB_DDB_SUBSCRIBERS_TABLE", "breathebuddy-subscribers")
OPENSEARCH_ENDPOINT = os.getenv("BB_OPENSEARCH_ENDPOINT", "")
OPENSEARCH_INDEX = os.getenv("BB_OPENSEARCH_INDEX", "aqi-grid")
# Optional SageMaker endpoint for the nowcast model (blank = local model).
SAGEMAKER_ENDPOINT = os.getenv("BB_SAGEMAKER_ENDPOINT", "")
# CloudWatch custom-metric namespace.
METRICS_NAMESPACE = os.getenv("BB_METRICS_NAMESPACE", "BreatheBuddy")

# --- Auth (Amazon Cognito) ------------------------------------------------
# When REQUIRE_AUTH is on, write endpoints (/subscribe, /cycle, /agent) demand a
# bearer token. Locally any non-empty token is accepted; when a pool is
# configured the JWT signature (RS256/ES256) is verified against the JWKS.
COGNITO_USER_POOL_ID = os.getenv("BB_COGNITO_USER_POOL_ID", "")
COGNITO_CLIENT_ID = os.getenv("BB_COGNITO_CLIENT_ID", "")
# Override the derived issuer / JWKS URL (useful for tests or non-Cognito IdPs).
COGNITO_ISSUER = os.getenv("BB_COGNITO_ISSUER", "")
COGNITO_JWKS_URL = os.getenv("BB_COGNITO_JWKS_URL", "")
REQUIRE_AUTH = _b("BB_REQUIRE_AUTH", False)

# --- Alert thresholds (default vulnerable profile) -----------------------
DEFAULT_THRESHOLD_AQI = _i("BB_DEFAULT_THRESHOLD_AQI", 150)
# Do not re-send the same (target, kind) alert more often than this.
ALERT_COOLDOWN_MIN = _i("BB_ALERT_COOLDOWN_MIN", 60)

# --- API safety ----------------------------------------------------------
# Max write requests (/subscribe, /cycle) per client per minute. 0 disables.
WRITE_RATE_LIMIT_PER_MIN = _i("BB_WRITE_RATE_LIMIT_PER_MIN", 60)
