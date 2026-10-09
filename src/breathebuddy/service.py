"""High-level orchestration used by the API, the agent and the CLI demo."""
from __future__ import annotations

import uuid

from . import alerts as alerting
from . import config
from .ingest import ingest_once
from .models import now_iso
from .nowcast import build_grid, clean_index, load_events, nowcast_point
from .policy import decide_activities
from .routing import find_routes
from .store import STORE, Store

_BOOTED = False


def aqi_category(aqi: float) -> str:
    if aqi <= 50:
        return "good"
    if aqi <= 100:
        return "satisfactory"
    if aqi <= 200:
        return "moderate"
    if aqi <= 300:
        return "poor"
    if aqi <= 400:
        return "very poor"
    return "severe"


def bootstrap(use_aws: bool | None = None) -> Store:
    """Load mock data, optionally connect AWS, build grid, seed demo users."""
    global _BOOTED
    if _BOOTED:
        return STORE
    STORE.load_mock()
    use_aws = config.USE_AWS if use_aws is None else use_aws
    if use_aws:
        from .awsio import AWSBridge
        STORE.attach_aws(AWSBridge())
    build_grid(STORE)
    # Seed two vulnerable profiles so alerts fire out of the box.
    _seed_subscriber("sub_rider_01", "Rider (bike commuter)", 28.646, 77.31,
                     kind="rider", threshold=150, phone="+91-90000-00001")
    _seed_subscriber("sub_asthma_01", "Asthma patient", 28.628, 77.243,
                     kind="asthma", threshold=120, phone="+91-90000-00002")
    _BOOTED = True
    return STORE


def _seed_subscriber(sid: str, name: str, lat: float, lon: float, kind: str,
                     threshold: int, **extra) -> dict:
    sub = {"subscriber_id": sid, "name": name, "lat": lat, "lon": lon,
           "kind": kind, "threshold_aqi": threshold, "channel": "sms",
           "created_at": now_iso(), **extra}
    STORE.add_subscriber(sub)
    return sub


def run_cycle() -> dict:
    """One full pipeline pass: ingest -> nowcast -> policy -> alert."""
    bootstrap()
    ing = ingest_once(STORE)
    cells = build_grid(STORE)
    school_alerts = [a for s in STORE.schools.values()
                     if (a := alerting.check_school(s, STORE))]
    sub_alerts = alerting.check_subscribers(STORE)
    return {
        "cycle_at": now_iso(),
        "ingest": ing,
        "grid_cells": len(cells),
        "school_alerts": [a.to_dict() for a in school_alerts],
        "subscriber_alerts": [a.to_dict() for a in sub_alerts],
    }


def aqi_query(lat: float, lon: float) -> dict:
    bootstrap()
    nc = nowcast_point(lat, lon, STORE)
    nc["category"] = aqi_category(nc["aqi_now"])
    nc["indoor_aqi_estimate"] = round(nc["aqi_now"] * 0.5, 1)
    nc["events"] = [e["label"] for e in environmental_events()]
    return nc


def environmental_events() -> list[dict]:
    """Active environmental events (stubble burning, etc.) affecting the grid."""
    bootstrap()
    out = []
    for e in load_events():
        out.append({
            "event_id": e["event_id"],
            "type": e["type"],
            "label": e["label"],
            "wind_dir_deg": e.get("wind_dir_deg"),
            "intensity": e.get("intensity", 1.0),
            "source": {"lat": e["source_lat"], "lon": e["source_lon"]},
            "active": True,
        })
    return out


def indoor_advisory(aqi: float) -> list[str]:
    """Plain-language indoor-air guidance for a given outdoor AQI."""
    aqi = int(round(aqi))
    if aqi <= 100:
        return ["Open windows for fresh-air ventilation.",
                "No special indoor measures needed today."]
    if aqi <= 200:
        return ["Keep windows closed during peak traffic hours.",
                "Run an air purifier in classrooms if available.",
                "Avoid incense, candles or agarbatti indoors."]
    if aqi <= 300:
        return ["Keep windows and doors closed.",
                "Run HEPA air purifiers in every classroom.",
                "Wet-mop floors to settle indoor dust.",
                "No incense, candles or frying without exhaust."]
    return ["Seal window gaps; run AC on recirculation mode.",
            "HEPA purifiers running in every room.",
            "Stop outside air intake; N95 indoors if needed.",
            "Consider remote learning until the air clears."]


def route_query(from_ll: tuple[float, float], to_ll: tuple[float, float]) -> dict:
    bootstrap()
    return find_routes(from_ll, to_ll, STORE)


def school_today(school_id: str) -> dict | None:
    bootstrap()
    school = STORE.get_school(school_id)
    if not school:
        return None
    sc = alerting.school_context(school, STORE)
    decision = decide_activities(sc["context"], school.rules_ref)
    status = aqi_category(sc["aqi_now"])
    if "close_school" in decision["allowed"]:
        headline = f"School closed for outdoor & in-person activity — AQI {sc['aqi_now']}."
    elif "hold_outdoor_assembly" in decision["blocked"]:
        headline = f"Outdoor assembly cancelled today — AQI {sc['aqi_now']} ({status})."
    else:
        headline = f"Normal schedule — AQI {sc['aqi_now']} ({status})."
    return {
        "school": school.to_dict(),
        "aqi_now": sc["aqi_now"],
        "aqi_peak": sc["aqi_peak"],
        "forecast": sc["forecast"],
        "clean_index": clean_index(sc["aqi_now"]),
        "status": status,
        "headline": headline,
        "allowed": decision["allowed"],
        "blocked": decision["blocked"],
        "decisions": decision["decisions"],
        "indoor_aqi_estimate": round(sc["aqi_now"] * 0.5, 1),
        "indoor_advisory": indoor_advisory(sc["aqi_now"]),
        "events": [e["label"] for e in environmental_events()],
        "generated_at": now_iso(),
    }


def subscribe(payload: dict) -> dict:
    bootstrap()
    sid = "sub_" + uuid.uuid4().hex[:8]
    sub = {
        "subscriber_id": sid,
        "name": payload.get("name", "Anonymous"),
        "lat": float(payload.get("lat", config.CENTER_LAT)),
        "lon": float(payload.get("lon", config.CENTER_LON)),
        "kind": payload.get("kind", "vulnerable_individual"),
        "threshold_aqi": float(payload.get("threshold_aqi", config.DEFAULT_THRESHOLD_AQI)),
        "phone": payload.get("phone", ""),
        "email": payload.get("email", ""),
        "channel": payload.get("channel", "sms"),
        "created_at": now_iso(),
    }
    STORE.add_subscriber(sub)
    return sub
