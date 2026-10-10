"""Small geo helpers: distance, bearings and lat/lon <-> grid indexing."""
from __future__ import annotations

import math

EARTH_R = 6_371_000.0  # metres


def haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance in metres."""
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi = p2 - p1
    dlam = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlam / 2) ** 2
    return 2 * EARTH_R * math.asin(min(1.0, math.sqrt(a)))


def valid_latlon(lat: float, lon: float) -> bool:
    """True when ``lat``/``lon`` are within valid geographic bounds."""
    return -90.0 <= lat <= 90.0 and -180.0 <= lon <= 180.0


def meters_per_deg_lat() -> float:
    return 111_320.0


def meters_per_deg_lon(lat: float) -> float:
    return 111_320.0 * math.cos(math.radians(lat))


def offset_latlon(lat: float, lon: float, dn_m: float, de_m: float) -> tuple[float, float]:
    """Offset a coordinate by north/east metres."""
    return lat + dn_m / meters_per_deg_lat(), lon + de_m / meters_per_deg_lon(lat)


def bearing_deg(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Initial bearing from point 1 to point 2, degrees clockwise from north."""
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dl = math.radians(lon2 - lon1)
    x = math.sin(dl) * math.cos(p2)
    y = math.cos(p1) * math.sin(p2) - math.sin(p1) * math.cos(p2) * math.cos(dl)
    return (math.degrees(math.atan2(x, y)) + 360.0) % 360.0
