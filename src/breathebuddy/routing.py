"""Clean-air routing: compare the *fastest* route with the *cleanest* one.

Both routes are found with Dijkstra on the 500 m nowcast grid.
  fastest : minimises travel time (assumes free-flowing ~28 km/h).
  cleanest: minimises pollution exposure = distance * (1 + aqi/100).
The cleanest route may be longer but is expected to show a lower average AQI.
"""
from __future__ import annotations

import heapq
from typing import Callable

from . import config
from .geo import haversine_m
from .models import GridCell, RouteResult
from .nowcast import build_grid, clean_index
from .store import STORE, Store

SPEED_KMH = 28.0
DIAG = 1.41421356


def _neighbours(cells: dict[str, GridCell], cid: str) -> list[tuple[str, float]]:
    c = cells[cid]
    out = []
    for dr in (-1, 0, 1):
        for dc in (-1, 0, 1):
            if dr == 0 and dc == 0:
                continue
            nid = f"g_{c.row + dr}_{c.col + dc}"
            n = cells.get(nid)
            if not n:
                continue
            step = config.GRID_RES_M * (DIAG if dr and dc else 1.0)
            out.append((nid, step))
    return out


def _nearest_cell(cells: dict[str, GridCell], lat: float, lon: float) -> GridCell:
    return min(cells.values(), key=lambda c: haversine_m(lat, lon, c.lat, c.lon))


def _dijkstra(cells: dict[str, GridCell], start: str, goal: str,
              weight: Callable[[GridCell, GridCell, float], float]):
    dist: dict[str, float] = {start: 0.0}
    prev: dict[str, str] = {}
    pq = [(0.0, start)]
    while pq:
        d, cid = heapq.heappop(pq)
        if cid == goal:
            break
        if d > dist.get(cid, float("inf")):
            continue
        for nid, step in _neighbours(cells, cid):
            nd = d + weight(cells[cid], cells[nid], step)
            if nd < dist.get(nid, float("inf")):
                dist[nid] = nd
                prev[nid] = cid
                heapq.heappush(pq, (nd, nid))
    if goal not in dist:
        return None
    path = [goal]
    while path[-1] != start:
        path.append(prev[path[-1]])
    path.reverse()
    return path


def _route(cells: dict[str, GridCell], path: list[str], mode: str,
           start_ll: tuple[float, float], end_ll: tuple[float, float]) -> RouteResult:
    geom: list[tuple[float, float]] = [start_ll]
    distance = 0.0
    aqis: list[float] = []
    prev_ll = start_ll
    for cid in path:
        c = cells[cid]
        distance += haversine_m(prev_ll[0], prev_ll[1], c.lat, c.lon)
        geom.append((c.lat, c.lon))
        aqis.append(c.aqi_now)
        prev_ll = (c.lat, c.lon)
    distance += haversine_m(prev_ll[0], prev_ll[1], end_ll[0], end_ll[1])
    geom.append(end_ll)
    avg = round(sum(aqis) / len(aqis), 1) if aqis else 0.0
    return RouteResult(
        mode=mode,
        distance_m=round(distance, 1),
        duration_min=round(distance / 1000.0 / SPEED_KMH * 60.0, 1),
        avg_aqi=avg,
        max_aqi=round(max(aqis), 1) if aqis else 0.0,
        clean_index=clean_index(avg),
        geometry=geom,
        cells=path,
    )


def find_routes(from_ll: tuple[float, float], to_ll: tuple[float, float],
                store: Store | None = None) -> dict:
    """Return both routes and the winner. ``from_ll``/``to_ll`` are (lat, lon)."""
    store = store or STORE
    cells = store.get_grid() or build_grid(store)
    start = _nearest_cell(cells, *from_ll).cell_id
    goal = _nearest_cell(cells, *to_ll).cell_id

    def w_fast(_a: GridCell, _b: GridCell, step: float) -> float:
        return step

    def w_clean(_a: GridCell, b: GridCell, step: float) -> float:
        # Strong penalty on polluted cells => the route bends around hotspots.
        return step * (0.5 + b.aqi_now / 100.0) ** 2

    fast_path = _dijkstra(cells, start, goal, w_fast) or [start, goal]
    clean_path = _dijkstra(cells, start, goal, w_clean) or [start, goal]

    fastest = _route(cells, fast_path, "fastest", from_ll, to_ll)
    cleanest = _route(cells, clean_path, "cleanest", from_ll, to_ll)
    winner = "cleanest" if cleanest.avg_aqi < fastest.avg_aqi else "fastest"
    saved = round(fastest.avg_aqi - cleanest.avg_aqi, 1)
    return {
        "fastest": fastest.to_dict(),
        "cleanest": cleanest.to_dict(),
        "winner": winner,
        "aqi_saved_on_cleanest": saved,
        "note": (f"Cleanest route cuts average exposure by {saved} AQI points."
                 if saved > 0 else "Routes have similar exposure on the current grid."),
    }
