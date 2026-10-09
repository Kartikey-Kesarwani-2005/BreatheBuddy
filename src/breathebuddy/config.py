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
API_BASE_URL = os.getenv("BB_API_BASE", f"http://{HOST}:{PORT}")

# --- AWS integration flags ----------------------------------------------
# When USE_AWS is on, boto3 is used to talk to LocalStack or real AWS.
USE_AWS = _b("BB_USE_AWS", False)
# Use the LLM-backed Strands agent when true. Left off locally so the demo runs
# offline and instantly; on AWS (with Bedrock/credentials) set BB_USE_STRANDS=true.
USE_STRANDS = _b("BB_USE_STRANDS", False)
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

# --- Alert thresholds (default vulnerable profile) -----------------------
DEFAULT_THRESHOLD_AQI = _i("BB_DEFAULT_THRESHOLD_AQI", 150)
SCHOOL_ALERT_AQI = _i("BB_SCHOOL_ALERT_AQI", 150)
