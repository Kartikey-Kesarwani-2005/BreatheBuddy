"""AWS Lambda entry points for BreatheBuddy (SAM).

One module, several handlers; SAM points each function at a different entry.
All heavy lifting lives in the ``breathebuddy`` package (same code as local).
Set ``BB_USE_AWS=true`` so the store mirrors state into S3 / DynamoDB / SNS.
"""
from __future__ import annotations

import json
import logging
import os
import sys

# Make the shared package importable when deployed via SAM (CodeUri = repo root).
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(ROOT, "src"))

from breathebuddy import agent as agent_mod  # noqa: E402
from breathebuddy import alerts as alerting  # noqa: E402
from breathebuddy import auth, config, openapi  # noqa: E402
from breathebuddy.geo import valid_latlon  # noqa: E402
from breathebuddy.ingest import ingest_once  # noqa: E402
from breathebuddy.nowcast import build_grid  # noqa: E402
from breathebuddy.ratelimit import WRITE_LIMITER  # noqa: E402
from breathebuddy.routing import find_routes  # noqa: E402
from breathebuddy.service import (  # noqa: E402
    aqi_query,
    bootstrap,
    environmental_events,
    run_cycle,
    school_today,
    subscribe,
)
from breathebuddy.store import STORE  # noqa: E402

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


def lambda_buffer(event, context):
    """SQS consumer: archive buffered alert deliveries to S3 + emit metrics."""
    _boot()
    messages = []
    for record in event.get("Records", []):
        body = record.get("body", "{}")
        try:
            messages.append(json.loads(body))
        except (TypeError, ValueError):
            messages.append({"raw": body})
    if STORE.aws is not None:
        STORE.aws.archive_buffer(messages)
        STORE.aws.put_metric("BufferDrained", len(messages))
    return {"ok": True, "drained": len(messages)}


# ------------------------------------------------------------------ API GW
def _response(status: int, body, extra_headers=None) -> dict:
    return {
        "statusCode": status,
        "headers": {
            "Content-Type": "application/json",
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Headers": "Content-Type,Authorization",
            "Access-Control-Allow-Methods": "GET,POST,OPTIONS",
            **(extra_headers or {}),
        },
        "body": json.dumps(body),
    }


def _authorized(event) -> bool:
    """Cognito gate for write endpoints (API Gateway also enforces the JWT)."""
    return auth.authorized(event.get("headers") or {})


def lambda_api(event, context):
    """API Gateway proxy handler mirroring the local REST API."""
    _boot()
    method = event.get("httpMethod", "GET")
    path = event.get("path", "/")
    q = {k: (v[0] if isinstance(v, list) else v)
         for k, v in (event.get("queryStringParameters") or {}).items()}
    try:
        if method == "OPTIONS":
            return _response(200, {"ok": True})
        if method == "POST" and path in ("/subscribe", "/agent", "/cycle"):
            ip = ((event.get("requestContext") or {}).get("identity") or {}).get("sourceIp", "?")
            if not WRITE_LIMITER.allow(ip):
                return _response(429, {"error": "rate limit exceeded"},
                                 {"Retry-After": str(WRITE_LIMITER.window_s)})
            if not _authorized(event):
                return _response(401, {"error": "unauthorized"})
        body = json.loads(event.get("body") or "{}")
        if not isinstance(body, dict):
            return _response(400, {"error": "body must be a JSON object"})

        if method == "GET" and path == "/health":
            return _response(200, {"ok": True, "city": config.CITY_NAME})
        if method == "GET" and path == "/openapi.json":
            return _response(200, openapi.SPEC)
        if method == "GET" and path == "/docs":
            return {"statusCode": 200,
                    "headers": {"Content-Type": "text/html",
                                "Access-Control-Allow-Origin": "*"},
                    "body": openapi.render_docs_html()}
        if method == "GET" and path == "/aqi":
            lat = float(q.get("lat", 28.6139))
            lon = float(q.get("lon", 77.2090))
            if not valid_latlon(lat, lon):
                return _response(400, {"error": "coordinates out of range"})
            return _response(200, aqi_query(lat, lon))
        if method == "GET" and path == "/route":
            from_ll = tuple(float(x) for x in q["from"].split(","))
            to_ll = tuple(float(x) for x in q["to"].split(","))
            if not (valid_latlon(*from_ll) and valid_latlon(*to_ll)):
                return _response(400, {"error": "coordinates out of range"})
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
        if method == "GET" and path == "/stations":
            return _response(200, [r.to_dict() for r in STORE.all_readings()])
        if method == "GET" and path == "/alerts":
            return _response(200, [a.to_dict() for a in STORE.recent_alerts()])
        if method == "GET" and path == "/buffer":
            return _response(200, {"buffered": STORE.buffer[-50:]})
        if method == "GET" and path == "/events":
            return _response(200, environmental_events())
        if method == "POST" and path == "/subscribe":
            return _response(201, subscribe(body))
        if method == "POST" and path == "/agent":
            question = str(body.get("question", "") or "").strip()
            if not question:
                return _response(400, {"error": "question is required"})
            engine = str(body.get("engine", "")).lower()
            prefer = True if engine == "strands" else (False if engine == "simple" else None)
            return _response(200, agent_mod.ask(question, prefer_strands=prefer))
        if method == "POST" and path == "/cycle":
            return _response(200, run_cycle())
        return _response(404, {"error": "not found", "path": path})
    except (ValueError, KeyError, TypeError):
        return _response(400, {"error": "bad request"})
    except Exception:  # pragma: no cover
        log.exception("api error")
        return _response(500, {"error": "internal error"})
