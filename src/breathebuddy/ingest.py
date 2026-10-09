"""Ingest: pull an AQI+weather+traffic feed and push into the store.

Default source is the bundled mock feed (``data/stations.json``). A live source
can be plugged in later through ``FEEDS`` without touching the rest of the app.
Each ingest run adds small, deterministic noise to simulate a fresh 15-min
reading so the dashboard visibly updates.
"""
from __future__ import annotations

import hashlib
import logging
import time

from . import config
from .models import Reading, now_iso
from .store import STORE, Store

log = logging.getLogger("breathebuddy.ingest")


def _jitter(station_id: str, base: float) -> float:
    """Small stable-ish perturbation derived from station + minute bucket."""
    bucket = int(time.time() // 900)  # 15-minute bucket
    h = int(hashlib.sha1(f"{station_id}:{bucket}".encode()).hexdigest(), 16)
    delta = ((h % 2000) / 1000.0 - 1.0) * 12.0  # +/- ~12 AQI points
    return round(max(5.0, base + delta), 1)


def fetch_mock() -> list[Reading]:
    from .store import Store as _S  # noqa: F401
    import json
    raw = json.loads((config.DATA_DIR / "stations.json").read_text("utf-8"))
    out = []
    for r in raw["stations"]:
        r = dict(r)
        r["aqi"] = _jitter(r["station_id"], float(r["aqi"]))
        r["ts"] = now_iso()
        out.append(Reading.from_dict(r))
    return out


def ingest_once(store: Store | None = None) -> dict:
    """One ingest cycle. Returns a small summary (used by Step Functions too)."""
    store = store or STORE
    t0 = time.time()
    readings = fetch_mock()
    if store.aws is None and config.USE_AWS:
        from .awsio import AWSBridge
        store.attach_aws(AWSBridge())
    n = store.put_readings(readings)
    summary = {
        "ingested": n,
        "ts": now_iso(),
        "stations": [r.station_id for r in readings],
        "elapsed_ms": round((time.time() - t0) * 1000, 1),
    }
    log.info("ingest: %s stations in %sms", n, summary["elapsed_ms"])
    return summary


if __name__ == "__main__":  # pragma: no cover
    logging.basicConfig(level=logging.INFO)
    print(ingest_once())
