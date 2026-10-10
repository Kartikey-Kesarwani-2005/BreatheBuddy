"""Pre-download a keyless dark basemap for the Delhi grid area.

The dashboard map has to work with **no internet** (that's the point of the
local demo), but Leaflet only draws the engine; the imagery comes from a tile
server. This script caches the tiles covering the demo area so the map renders
offline; any tile outside the cache still falls back to the live server.

Provider: **Esri "World Dark Gray Base"** -- no API key required, dark theme.
(We used CARTO dark before; it now returns an "API key required" placeholder
image, which is why the cached tiles must be validated as real images.)

    python scripts/fetch_tiles.py

Tiles are written to ``frontend/vendor/tiles/{z}/{x}/{y}.jpg``. Safe to re-run
(existing valid tiles are skipped).
"""
from __future__ import annotations

import math
import os
import sys
import time
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "frontend", "vendor", "tiles")

# Demo area around the 500 m Delhi grid, with margin so panning works a bit.
LAT_MIN, LAT_MAX = 28.30, 28.92
LON_MIN, LON_MAX = 76.80, 77.60
ZOOMS = (10, 11, 12, 13)
# Esri tile URL uses {z}/{y}/{x} order.
TILE_URL = ("https://server.arcgisonline.com/ArcGIS/rest/services/"
            "Canvas/World_Dark_Gray_Base/MapServer/tile/{z}/{y}/{x}")
EXT = ".jpg"
# A real tile is a JPEG; anything smaller is an error/placeholder image.
MIN_TILE_BYTES = 500


def tile_xy(lat: float, lon: float, z: int) -> tuple[int, int]:
    n = 2 ** z
    x = int((lon + 180.0) / 360.0 * n)
    lat_r = math.radians(lat)
    y = int((1.0 - math.log(math.tan(lat_r) + 1.0 / math.cos(lat_r)) / math.pi) / 2.0 * n)
    return x, y


def plan() -> list[tuple[int, int, int]]:
    todo = []
    for z in ZOOMS:
        pts = [tile_xy(la, lo, z)
               for la in (LAT_MIN, LAT_MAX) for lo in (LON_MIN, LON_MAX)]
        xs, ys = [p[0] for p in pts], [p[1] for p in pts]
        for x in range(min(xs), max(xs) + 1):
            for y in range(min(ys), max(ys) + 1):
                todo.append((z, x, y))
    return todo


def fetch(z: int, x: int, y: int) -> bytes:
    url = TILE_URL.format(z=z, x=x, y=y)
    req = urllib.request.Request(url, headers={"User-Agent": "BreatheBuddy/0.1"})
    data = urllib.request.urlopen(req, timeout=20).read()
    if len(data) < MIN_TILE_BYTES or not data.startswith(b"\xff\xd8"):
        raise RuntimeError(f"{z}/{x}/{y}: not a valid tile ({len(data)} bytes)")
    return data


def main() -> int:
    todo = plan()
    print(f"tiles to cache: {len(todo)} across zoom {ZOOMS} -> {OUT}")
    done = skipped = failed = 0
    t0 = time.time()
    for i, (z, x, y) in enumerate(todo, 1):
        path = os.path.join(OUT, str(z), str(x), f"{y}{EXT}")
        if os.path.exists(path) and os.path.getsize(path) >= MIN_TILE_BYTES:
            skipped += 1
            continue
        os.makedirs(os.path.dirname(path), exist_ok=True)
        try:
            data = fetch(z, x, y)
            with open(path, "wb") as fh:
                fh.write(data)
            done += 1
        except Exception as exc:
            failed += 1
            print(f"  FAIL {z}/{x}/{y}: {exc}")
        if i % 50 == 0:
            print(f"  {i}/{len(todo)}  new={done} cached={skipped} fail={failed}")
    print(f"done in {time.time() - t0:.1f}s  new={done} cached={skipped} failed={failed}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
