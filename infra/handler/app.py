"""AWS Lambda entry points for BreatheBuddy (SAM).

One module, several handlers — SAM points each function at a different entry.
All heavy lifting lives in the ``breathebuddy`` package (same code as local).
Set ``BB_USE_AWS=true`` so the store mirrors state into S3 / DynamoDB / SNS.
"""
from __future__ import annotations

import json
import logging
import os
import sys
from urllib.parse import parse_qs

# Make the shared package importable when deployed via SAM (CodeUri = repo root).
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(ROOT, "src"))

from breathebuddy import agent as agent_mod            # noqa: E402
from breathebuddy.ingest import ingest_once           # noqa: E402
from breathebuddy.nowcast import build_grid, nowcast_point  # noqa: E402
from breathebuddy.routing import find_routes          # noqa: E402
from breathebuddy.service import (aqi_query, bootstrap, environmental_events,  # noqa: E402
                                  school_today, subscribe)
from breathebuddy.store import STORE                   # noqa: E402
from breathebuddy import alerts as alerting            # noqa: E402

log = logging.getLogger()
log.setLevel(logging.INFO)


def _boot():
    bootstrap()  # seeds mock data + builds grid; use_aws comes from BB_USE_AWS env


# ---------------------------------------------------------------- pipeline
def lambda_ingest(event, context):
    """EventBridge (15 min) -> ingest -> S3 raw + DynamoDB latest."""
    _boot()
    summary = ingest_once(STORE)
    build_grid(STORE)
    return {"ok": True, **summary}


def lambda_nowcast(event, context):
    """Build the 500 m grid nowcast."""
    _boot()
    cells = build_grid(STORE)
    return {"ok": True, "grid_cells": len(cells)}


def lambda_policy(event, context):
    """Run Cedar school rules -> decide + create alerts."""
    _boot()
    created = [a.to_dict() for s in STORE.schools.values()
               if (a := alerting.check_school(s, STORE))]
    return {"ok": True, "school_alerts": created}


def lambda_alert(event, context):
    """Check vulnerable subscribers and publish SNS alerts."""
    _boot()
    fired = [a.to_dict() for a in alerting.check_subscribers(STORE)]
    return {"ok": True, "subscriber_alerts": fired}


# ------------------------------------------------------------------ API GW
def _response(status: int, body) -> dict:
    return {
        "statusCode": status,
        "headers": {
            "Content-Type": "application/json",
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Headers": "Content-Type,Authorization",
            "Access-Control-Allow-Methods": "GET,POST,OPTIONS",
        },
        "body": json.dumps(body),
    }


def lambda_api(event, context):
    """API Gateway proxy handler mirroring the local REST API."""
    _boot()
    method = event.get("httpMethod", "GET")
    path = event.get("path", "/")
    q = {k: v[0] for k, v in (event.get("queryStringParameters") or {}).items()}
    try:
        body = json.loads(event.get("body") or "{}")

        if method == "GET" and path == "/aqi":
            return _response(200, aqi_query(float(q.get("lat", 28.6139)),
                                            float(q.get("lon", 77.2090))))
        if method == "GET" and path == "/route":
            from_ll = tuple(float(x) for x in q["from"].split(","))
            to_ll = tuple(float(x) for x in q["to"].split(","))
            res = find_routes(from_ll, to_ll, STORE)
            mode = q.get("mode")
            return _response(200, res[mode] if mode in ("fastest", "cleanest") else res)
        if method == "GET" and path.startswith("/school/") and path.endswith("/today"):
            sid = path.split("/")[2]
            card = school_today(sid)
            return _response(200 if card else 404, card or {"error": "unknown school"})
        if method == "GET" and path == "/grid":
            return _response(200, [c.to_dict() for c in STORE.get_grid().values()])
        if method == "GET" and path == "/schools":
            return _response(200, [s.to_dict() for s in STORE.schools.values()])
        if method == "GET" and path == "/events":
            return _response(200, environmental_events())
        if method == "POST" and path == "/subscribe":
            return _response(201, subscribe(body))
        if method == "POST" and path == "/agent":
            return _response(200, agent_mod.ask(body.get("question", "")))
        return _response(404, {"error": "not found", "path": path})
    except Exception as exc:  # pragma: no cover
        log.exception("api error")
        return _response(500, {"error": str(exc)})
