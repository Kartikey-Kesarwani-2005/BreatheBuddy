"""Pull a live AQI feed and hand it to the store.

Two feeds are wired up:

  openaq -- the live OpenAQ v3 API (free key; set BB_OPENAQ_API_KEY).
  mock   -- data/stations.json with a small deterministic jitter, used only as
            an offline/error fallback so the app can never be taken down by a
            flaky network.

Choose with BB_AQ_SOURCE (default: openaq). Every cycle records which feed
actually produced the readings, so the dashboard can show LIVE vs PREVIEW.
"""
from __future__ import annotations

import hashlib
import json
import logging
import time
import urllib.request

from . import config
from .models import Reading, now_iso
from .store import STORE, Store

log = logging.getLogger("breathebuddy.ingest")


def _jitter(station_id: str, base: float) -> float:
    """Nudge a mock reading a little per 15-minute bucket so the numbers change
    between cycles without turning random (and therefore untestable)."""
    bucket = int(time.time() // 900)  # 15-minute bucket
    h = int(hashlib.sha1(f"{station_id}:{bucket}".encode()).hexdigest(), 16)
    delta = ((h % 2000) / 1000.0 - 1.0) * 12.0  # +/- ~12 AQI points
    return round(max(5.0, base + delta), 1)


def fetch_mock() -> list[Reading]:
    raw = json.loads((config.DATA_DIR / "stations.json").read_text("utf-8"))
    out = []
    for r in raw["stations"]:
        r = dict(r)
        r["aqi"] = _jitter(r["station_id"], float(r["aqi"]))
        r["ts"] = now_iso()
        out.append(Reading.from_dict(r))
    return out


# --- Live source: OpenAQ v3 -------------------------------------------------
# CPCB (India) PM2.5 breakpoints (µg/m³ -> AQI). Sub-index interpolation.
_PM25_BREAKPOINTS = [
    (0, 30, 0, 50), (30, 60, 51, 100), (60, 90, 101, 200),
    (90, 120, 201, 300), (120, 250, 301, 400), (250, 500, 401, 500),
]


def pm25_to_aqi(pm25: float) -> float:
    """Convert a PM2.5 concentration (µg/m³) to a CPCB-style AQI value."""
    c = max(0.0, float(pm25))
    for c_lo, c_hi, i_lo, i_hi in _PM25_BREAKPOINTS:
        if c <= c_hi:
            return round(i_lo + (i_hi - i_lo) * (c - c_lo) / (c_hi - c_lo), 1)
    return 500.0


def _openaq_pm25(location: dict) -> float | None:
    for sensor in location.get("sensors", []):
        param = sensor.get("parameter")
        name = param.get("name") if isinstance(param, dict) else param
        if name == "pm25":
            value = (sensor.get("latest") or {}).get("value")
            if value is not None:
                return float(value)
    return None


def fetch_openaq() -> list[Reading]:
    """Live readings from OpenAQ v3 (raises on misconfig/network errors)."""
    if not config.OPENAQ_API_KEY:
        raise RuntimeError("BB_OPENAQ_API_KEY not set")
    url = (f"{config.OPENAQ_BASE}/locations?coordinates={config.CENTER_LAT},"
           f"{config.CENTER_LON}&radius={config.OPENAQ_RADIUS_M}&limit=100")
    req = urllib.request.Request(url, headers={
        "X-API-Key": config.OPENAQ_API_KEY, "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=20) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    out = []
    for loc in data.get("results", []):
        coord = loc.get("coordinates") or {}
        lat, lon = coord.get("latitude"), coord.get("longitude")
        pm25 = _openaq_pm25(loc)
        if lat is None or lon is None or pm25 is None:
            continue
        out.append(Reading(station_id=f"openaq-{loc.get('id')}",
                           lat=float(lat), lon=float(lon),
                           aqi=pm25_to_aqi(pm25), pm25=round(pm25, 1),
                           ts=now_iso()))
    if not out:
        raise RuntimeError("OpenAQ returned no PM2.5 readings")
    return out


FEEDS = {"mock": fetch_mock, "openaq": fetch_openaq}

# Which feed actually produced the current readings (live vs bundled fallback),
# so the dashboard / health-check can report the truth instead of the config.
LAST_SOURCE = "mock"
LAST_NOTE = "no feed fetched yet"


def effective_source() -> dict:
    """The feed behind the current readings (for /health + the dashboard badge)."""
    configured = (config.AQ_SOURCE or "mock").lower()
    return {
        "configured": configured,
        "source": LAST_SOURCE,
        "live": LAST_SOURCE != "mock",
        "note": LAST_NOTE,
        "key_set": bool(config.OPENAQ_API_KEY),
    }


def fetch_readings() -> list[Reading]:
    """Read from the configured source, falling back to bundled data on error."""
    global LAST_SOURCE, LAST_NOTE
    source = (config.AQ_SOURCE or "mock").lower()
    feed = FEEDS.get(source, fetch_mock)
    if feed is fetch_mock:
        LAST_SOURCE, LAST_NOTE = "mock", "bundled feed (offline preview)"
        return feed()
    try:
        readings = feed()
        LAST_SOURCE = source
        LAST_NOTE = f"live OpenAQ feed, {len(readings)} stations"
        log.info("ingest: live feed '%s' -> %s readings", source, len(readings))
        return readings
    except Exception as exc:  # noqa: BLE001 - never let a feed error kill the cycle
        LAST_SOURCE, LAST_NOTE = "mock", f"{source} unavailable ({exc}); using bundled feed"
        log.warning("ingest: live feed '%s' failed (%s); using bundled feed", source, exc)
        return fetch_mock()


def ingest_once(store: Store | None = None) -> dict:
    """One ingest cycle. Returns a small summary (used by Step Functions too)."""
    store = store or STORE
    t0 = time.time()
    readings = fetch_readings()
    if store.aws is None and config.USE_AWS:
        from .awsio import AWSBridge
        store.attach_aws(AWSBridge())
    n = store.put_readings(readings)
    summary = {
        "ingested": n,
        "source": LAST_SOURCE,
        "live": LAST_SOURCE != "mock",
        "ts": now_iso(),
        "stations": [r.station_id for r in readings],
        "elapsed_ms": round((time.time() - t0) * 1000, 1),
    }
    log.info("ingest: %s stations in %sms", n, summary["elapsed_ms"])
    return summary


if __name__ == "__main__":  # pragma: no cover
    logging.basicConfig(level=logging.INFO)
    print(ingest_once())

