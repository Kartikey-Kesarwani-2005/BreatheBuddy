"""Live weather enrichment via Open-Meteo (free, keyless, no API key).

The nowcast's dispersion term needs a wind speed, and the OpenAQ feed carries
only pollutant concentrations -- no meteorology. So each cycle we pull a single
city-wide weather snapshot and attach it to the readings that came without their
own wind. Wind direction also steers the stubble-burning plume.

Weather is best-effort: any failure is logged and the app keeps whatever wind it
already had, so a flaky weather API never breaks a cycle or the demo.
"""
from __future__ import annotations

import json
import logging
import time
import urllib.parse
import urllib.request

from . import config
from .models import Reading, now_iso

log = logging.getLogger("breathebuddy.weather")

# Small in-process cache so a burst of cycles does not hammer the weather API.
_CACHE: dict = {"at": 0.0, "data": None}


def current(force: bool = False) -> dict | None:
    """Return a city-wide weather snapshot, or None when unavailable.

    Shape: {wind_speed (m/s), wind_dir (deg), temperature (C), humidity (%),
            source, ts}. Falls back to the last good snapshot on a transient
    error rather than returning nothing.
    """
    if not config.WEATHER_ENABLED:
        return None
    now = time.time()
    if not force and _CACHE["data"] is not None and now - _CACHE["at"] < config.WEATHER_TTL_S:
        return _CACHE["data"]
    params = {
        "latitude": config.WEATHER_LAT,
        "longitude": config.WEATHER_LON,
        "current": "temperature_2m,relative_humidity_2m,wind_speed_10m,wind_direction_10m",
        "wind_speed_unit": "ms",
        "timezone": "UTC",
    }
    url = f"{config.WEATHER_BASE}?{urllib.parse.urlencode(params)}"
    try:
        req = urllib.request.Request(url, headers={"Accept": "application/json"})
        with urllib.request.urlopen(req, timeout=config.WEATHER_TIMEOUT_S) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        cur = data.get("current") or {}
        # Require wind fields to be present; silently falling back to 0.0 would
        # lower all AQI via _dispersion_factor (max 1.15 when wind_speed=0).
        if "wind_speed_10m" not in cur or "wind_direction_10m" not in cur:
            log.warning("weather: missing wind fields in Open-Meteo response")
            return _CACHE["data"]
        out = {
            "wind_speed": round(float(cur["wind_speed_10m"]), 2),
            "wind_dir": round(float(cur["wind_direction_10m"]), 1),
            "temperature": round(float(cur.get("temperature_2m") or 0.0), 1),
            "humidity": round(float(cur.get("relative_humidity_2m") or 0.0), 1),
            "source": "open-meteo",
            "ts": now_iso(),
        }
    except Exception as exc:  # noqa: BLE001 - enrichment must never break the cycle
        log.warning("weather: Open-Meteo unavailable (%s)", exc)
        return _CACHE["data"]  # last good snapshot, or None
    _CACHE["at"], _CACHE["data"] = now, out
    return out


def apply(readings: list[Reading]) -> dict | None:
    """Attach the current weather to readings that arrived without wind.

    Mock readings ship their own wind from stations.json, so only the live
    OpenAQ readings (wind_speed == 0) get enriched.
    """
    snap = current()
    if not snap:
        return None
    for r in readings:
        if not r.wind_speed:
            r.wind_speed = snap["wind_speed"]
            r.wind_dir = snap["wind_dir"]
    return snap
