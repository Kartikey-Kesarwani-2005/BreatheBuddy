"""Alerting: turn policy decisions + threshold crossings into alerts.

Alerts are published through SNS when configured (LocalStack or AWS) and are
always written to a local outbox (``data/alerts_outbox.json``) so the offline
demo still produces a visible, testable alert.
"""
from __future__ import annotations

import logging

from . import config
from .models import Alert, School
from .nowcast import nowcast_point
from .policy import decide_activities
from .store import STORE, Store

log = logging.getLogger("breathebuddy.alerts")


def school_context(school: School, store: Store | None = None) -> dict:
    store = store or STORE
    nc = nowcast_point(school.lat, school.lon, store)
    peak = max(nc["aqi_forecast"]) if nc["aqi_forecast"] else nc["aqi_now"]
    return {
        "school": school,
        "aqi_now": nc["aqi_now"],
        "aqi_peak": round(peak, 1),
        "forecast": nc["aqi_forecast"],
        "context": {
            "predicted_aqi": nc["aqi_now"],
            "masks_available": True,
            "time_limit_minutes": 45,
        },
    }


def school_alert(school: School, store: Store | None = None) -> Alert | None:
    """Create an alert if the school's outdoor activities are unsafe today."""
    sc = school_context(school, store)
    decision = decide_activities(sc["context"], school.rules_ref)
    outdoor_blocked = "hold_outdoor_assembly" in decision["blocked"]
    close = "close_school" in decision["allowed"]
    if not (outdoor_blocked or close):
        return None
    aqi = sc["aqi_now"]
    if close:
        kind = "school_close"
        msg = (f"{school.name}: AQI {aqi} is hazardous. Move to remote learning; "
               f"outdoor assembly and sports are cancelled.")
    elif "hold_physical_education" in decision["blocked"]:
        kind = "school_outdoor_cancelled"
        msg = (f"{school.name}: AQI {aqi}. Outdoor assembly and PE cancelled; "
               f"classes indoors. Peak forecast {sc['aqi_peak']}.")
    else:
        kind = "school_assembly_cancelled"
        msg = (f"{school.name}: AQI {aqi}. Outdoor assembly cancelled; "
               f"PE only with masks and a 60-minute limit.")
    return Alert.create(target=f"school:{school.school_id}", kind=kind, aqi=aqi, message=msg)


def check_school(school: School, store: Store | None = None) -> Alert | None:
    store = store or STORE
    alert = school_alert(school, store)
    if alert:
        publish(alert, store)
        log.info("school alert: %s", alert.message)
    return alert


def check_subscribers(store: Store | None = None) -> list[Alert]:
    """Alert vulnerable individuals whose local AQI crosses their threshold."""
    store = store or STORE
    fired = []
    for sub in store.all_subscribers():
        lat, lon = sub.get("lat"), sub.get("lon")
        if lat is None or lon is None:
            continue
        nc = nowcast_point(lat, lon, store)
        thr = float(sub.get("threshold_aqi", config.DEFAULT_THRESHOLD_AQI))
        if nc["aqi_now"] >= thr:
            kind = sub.get("kind", "vulnerable_individual")
            msg = (f"BreatheBuddy: AQI {nc['aqi_now']} near you crosses your alert "
                   f"threshold {int(thr)}. Wear an N95, avoid outdoor exertion. "
                   f"Next 6h: {nc['aqi_forecast']}.")
            alert = Alert.create(target=sub["subscriber_id"], kind=kind,
                                 aqi=nc["aqi_now"], message=msg)
            publish(alert, store)
            fired.append(alert)
    return fired


def publish(alert: Alert, store: Store | None = None) -> dict:
    store = store or STORE
    store.add_alert(alert)
    if store.aws is not None:
        return store.aws.publish_alert(alert)
    return {"delivered": True, "channel": "mock-outbox"}
