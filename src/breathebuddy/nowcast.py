"""Hyperlocal AQI nowcast on a ~500 m grid for the next N hours.

Model (small and explainable on purpose -- no external ML needed):
  aqi_now(cell)   = inverse-distance-weighted blend of nearby stations,
                    adjusted by local traffic and wind dispersion.
  forecast[h]     = aqi_now * diurnal(hour+h) * dispersion drift.
  clean_index     = 0..100 score (higher = cleaner): 100 - aqi/3.

The same interface is used locally and by the SageMaker/Lambda nowcast Lambda,
so the model can later be swapped for a trained endpoint without API changes.
"""
from __future__ import annotations

import json
import math
from datetime import datetime, timezone

from . import config
from .geo import bearing_deg, haversine_m, offset_latlon
from .models import GridCell, Reading
from .store import STORE, Store


def _traffic_factor(traffic: float) -> float:
    return 1.0 + 0.15 * max(0.0, min(1.0, traffic))


def _dispersion_factor(wind_speed: float) -> float:
    # More wind -> more dispersion -> lower concentration.
    return max(0.80, min(1.15, 1.15 - 0.12 * max(0.0, wind_speed)))


def _diurnal(hour: int) -> float:
    # Peaks late evening (inversion), dips mid-afternoon.
    return 1.0 + 0.18 * math.cos(2 * math.pi * (hour - 20) / 24.0)


def _idw_aqi(lat: float, lon: float, readings: list[Reading],
             radius_m: float = 12000.0, power: float = 3.0) -> float:
    """Inverse-distance blend of station AQI (power=3 => localised hotspots)."""
    num = den = 0.0
    nearest = None
    nearest_d = float("inf")
    for r in readings:
        d = haversine_m(lat, lon, r.lat, r.lon)
        if d < nearest_d:
            nearest, nearest_d = r, d
        if d <= radius_m:
            eff = r.aqi * _traffic_factor(r.traffic) * _dispersion_factor(r.wind_speed)
            w = 1.0 / (d ** power + 500.0)
            num += w * eff
            den += w
    if den:
        return num / den
    return nearest.aqi if nearest else 100.0


def clean_index(aqi: float) -> float:
    return round(max(0.0, min(100.0, 100.0 - aqi / 3.0)), 1)


# --- stubble-burning plume -------------------------------------------------
def load_events(active_only: bool = True) -> list[dict]:
    """Read environmental events (stubble burning etc.) from data/events.json."""
    if not config.USE_STUBBLE or not config.EVENTS_FILE.exists():
        return []
    data = json.loads(config.EVENTS_FILE.read_text("utf-8"))
    events = data.get("events", [])
    return [e for e in events if e.get("active", True)] if active_only else events


def _plume_aqi(lat: float, lon: float, events: list[dict]) -> float:
    """Wind-driven smoke contribution at a point (0 upwind, max downwind)."""
    total = 0.0
    for e in events:
        if e.get("type") != "stubble_burning":
            continue
        slat, slon = e["source_lat"], e["source_lon"]
        d = haversine_m(slat, slon, lat, lon)
        radius = e.get("radius_km", 200) * 1000.0
        if d > radius:
            continue
        # Meteorological 'from' direction -> smoke travels toward +180.
        plume_bearing = (e.get("wind_dir_deg", 270) + 180.0) % 360.0
        delta = math.radians(bearing_deg(slat, slon, lat, lon) - plume_bearing)
        align = max(0.0, math.cos(delta))       # 0 upwind, 1 straight downwind
        decay = math.exp(-d / (radius * 0.55))  # fades with distance
        total += e.get("intensity", 1.0) * e.get("base_aqi", 90.0) * align * decay
    return total


def build_grid(store: Store | None = None, rows: int | None = None,
               cols: int | None = None) -> dict[str, GridCell]:
    store = store or STORE
    rows = rows or config.GRID_ROWS
    cols = cols or config.GRID_COLS
    res = config.GRID_RES_M
    readings = store.all_readings()
    events = load_events()
    hour = datetime.now(timezone.utc).hour
    cells: dict[str, GridCell] = {}
    for r in range(rows):
        for c in range(cols):
            # cell centres centred on the city centre
            dn = (r - (rows - 1) / 2.0) * res
            de = (c - (cols - 1) / 2.0) * res
            lat, lon = offset_latlon(config.CENTER_LAT, config.CENTER_LON, dn, de)
            plume = round(_plume_aqi(lat, lon, events), 1)
            aqi_now = round(_idw_aqi(lat, lon, readings) + plume, 1)
            forecast = [round(aqi_now * _diurnal((hour + h) % 24), 1)
                        for h in range(1, config.FORECAST_HOURS + 1)]
            cid = f"g_{r}_{c}"
            cells[cid] = GridCell(cell_id=cid, lat=lat, lon=lon, aqi_now=aqi_now,
                                  aqi_forecast=forecast, clean_index=clean_index(aqi_now),
                                  plume=plume, row=r, col=c)
    store.set_grid(cells)
    return cells


def nowcast_point(lat: float, lon: float, store: Store | None = None) -> dict:
    """Forecast for an arbitrary point: blend the 4 nearest grid cells."""
    store = store or STORE
    cells = store.get_grid() or build_grid(store)
    ranked = sorted(cells.values(), key=lambda c: haversine_m(lat, lon, c.lat, c.lon))
    near = ranked[:4]
    weights = [1.0 / (haversine_m(lat, lon, c.lat, c.lon) ** 2 + 1.0) for c in near]
    wsum = sum(weights)
    aqi_now = round(sum(w * c.aqi_now for w, c in zip(weights, near)) / wsum, 1)
    forecast = []
    for h in range(config.FORECAST_HOURS):
        pairs = [(w, c.aqi_forecast[h]) for c, w in zip(near, weights)
                 if h < len(c.aqi_forecast)]
        if pairs:
            wh = sum(w for w, _ in pairs)
            forecast.append(round(sum(w * v for w, v in pairs) / wh, 1))
        else:
            forecast.append(aqi_now)
    result = {
        "lat": round(lat, 6),
        "lon": round(lon, 6),
        "aqi_now": aqi_now,
        "aqi_forecast": forecast,
        "clean_index": clean_index(aqi_now),
        "nearest_cell": near[0].cell_id,
        "engine": "local",
    }
    # Optional: delegate to a deployed SageMaker nowcast endpoint when configured.
    if config.SAGEMAKER_ENDPOINT:
        from .awsio import invoke_sagemaker
        remote = invoke_sagemaker({"lat": lat, "lon": lon})
        if remote and "aqi_now" in remote:
            result["aqi_now"] = round(float(remote["aqi_now"]), 1)
            result["aqi_forecast"] = [round(float(x), 1)
                                      for x in remote.get("aqi_forecast", forecast)]
            result["clean_index"] = clean_index(result["aqi_now"])
            result["engine"] = "sagemaker"
    return result


if __name__ == "__main__":  # pragma: no cover
    STORE.load_mock()
    grid = build_grid(STORE)
    print(f"built {len(grid)} cells; sample:",
          next(iter(grid.values())).to_dict())
