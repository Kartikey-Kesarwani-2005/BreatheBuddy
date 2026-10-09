"""Local HTTP API + static frontend, using only the Python standard library.

Run ``python run.py`` and open http://localhost:8000.

Implements the spec endpoints:
    GET  /aqi?lat=&lon=
    GET  /route?from=lat,lon&to=lat,lon&mode=fastest|cleanest
    GET  /school/{id}/today
    POST /subscribe
plus helpers for the dashboard (/grid, /schools, /alerts) and (/agent, /cycle).
"""
from __future__ import annotations

import json
import logging
import re
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

from . import config
from . import agent as agent_mod
from .service import (aqi_query, bootstrap, environmental_events, route_query,
                      run_cycle, school_today, subscribe)
from .store import STORE

log = logging.getLogger("breathebuddy.api")

CONTENT_TYPES = {".html": "text/html", ".js": "application/javascript",
                 ".css": "text/css", ".json": "application/json",
                 ".svg": "image/svg+xml", ".ico": "image/x-icon"}


def _coord(value: str) -> tuple[float, float]:
    lat, lon = value.split(",")
    return float(lat), float(lon)


class Handler(BaseHTTPRequestHandler):
    server_version = "BreatheBuddy/0.1"

    # -- utilities --------------------------------------------------------
    def _send(self, obj, status: int = 200):
        body = json.dumps(obj).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self._cors()
        self.end_headers()
        self.wfile.write(body)

    def _text(self, text: str, content_type: str, status: int = 200):
        body = text.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self._cors()
        self.end_headers()
        self.wfile.write(body)

    def _cors(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")

    def _json_body(self) -> dict:
        length = int(self.headers.get("Content-Length", 0) or 0)
        if not length:
            return {}
        try:
            return json.loads(self.rfile.read(length).decode("utf-8"))
        except json.JSONDecodeError:
            return {}

    def _static(self, path: str):
        rel = "index.html" if path in ("/", "") else path.lstrip("/")
        target = (config.FRONTEND_DIR / rel).resolve()
        if config.FRONTEND_DIR.resolve() not in target.parents and target != config.FRONTEND_DIR.resolve():
            return self._send({"error": "forbidden"}, 403)
        if not target.exists() or target.is_dir():
            return self._send({"error": "not found", "path": path}, 404)
        ctype = CONTENT_TYPES.get(target.suffix, "application/octet-stream")
        self._text(target.read_text("utf-8", errors="replace"), ctype)

    # -- verbs ------------------------------------------------------------
    def do_OPTIONS(self):  # noqa: N802
        self.send_response(204)
        self._cors()
        self.end_headers()

    def do_GET(self):  # noqa: N802
        try:
            self._route_get()
        except Exception as exc:  # pragma: no cover
            log.exception("GET failed")
            self._send({"error": str(exc)}, 500)

    def do_POST(self):  # noqa: N802
        try:
            self._route_post()
        except Exception as exc:  # pragma: no cover
            log.exception("POST failed")
            self._send({"error": str(exc)}, 500)

    # -- routing ----------------------------------------------------------
    def _route_get(self):
        u = urlparse(self.path)
        path, q = u.path, parse_qs(u.query)

        if path == "/health":
            return self._send({"ok": True, "city": config.CITY_NAME})

        if path in ("/aqi", "/api/aqi"):
            try:
                lat = float(q.get("lat", [config.CENTER_LAT])[0])
                lon = float(q.get("lon", [config.CENTER_LON])[0])
            except (ValueError, TypeError):
                return self._send({"error": "lat and lon must be numbers"}, 400)
            return self._send(aqi_query(lat, lon))

        if path in ("/route", "/api/route"):
            try:
                frm = q.get("from", [None])[0]
                to = q.get("to", [None])[0]
                if frm and to:
                    from_ll, to_ll = _coord(frm), _coord(to)
                else:
                    from_ll = (float(q["from_lat"][0]), float(q["from_lon"][0]))
                    to_ll = (float(q["to_lat"][0]), float(q["to_lon"][0]))
            except (ValueError, TypeError, KeyError, IndexError):
                return self._send(
                    {"error": "provide from=lat,lon&to=lat,lon"}, 400)
            res = route_query(from_ll, to_ll)
            mode = q.get("mode", [None])[0]
            if mode in ("fastest", "cleanest"):
                return self._send(res[mode])
            return self._send(res)

        m = re.match(r"^/(?:api/)?school/([^/]+)/today$", path)
        if m:
            card = school_today(m.group(1))
            return self._send(card or {"error": "unknown school"}, 200 if card else 404)

        if path in ("/grid", "/api/grid"):
            bootstrap()
            return self._send([c.to_dict() for c in STORE.get_grid().values()])

        if path in ("/schools", "/api/schools"):
            bootstrap()
            return self._send([s.to_dict() for s in STORE.schools.values()])

        if path in ("/stations", "/api/stations"):
            bootstrap()
            return self._send([r.to_dict() for r in STORE.all_readings()])

        if path in ("/alerts", "/api/alerts"):
            bootstrap()
            return self._send([a.to_dict() for a in STORE.recent_alerts()])

        if path in ("/events", "/api/events"):
            return self._send(environmental_events())

        return self._static(path)

    def _route_post(self):
        path = urlparse(self.path).path
        body = self._json_body()

        if path in ("/subscribe", "/api/subscribe"):
            return self._send(subscribe(body), 201)

        if path in ("/agent", "/api/agent"):
            question = body.get("question", "")
            return self._send(agent_mod.ask(question))

        if path in ("/cycle", "/api/cycle"):
            return self._send(run_cycle())

        return self._send({"error": "not found", "path": path}, 404)


def serve(host: str | None = None, port: int | None = None):
    bootstrap()
    host = host or config.HOST
    port = port or config.PORT
    try:
        httpd = ThreadingHTTPServer((host, port), Handler)
    except OSError as exc:
        print(f"\nCould not start on {host}:{port} -> {exc}")
        print(f"Port {port} may already be in use by another server.")
        print(f"Try a different port, e.g.:  python run.py --port {port + 1}\n")
        raise SystemExit(1)
    log.info("BreatheBuddy API on http://%s:%s", host, port)
    print(f"BreatheBuddy running -> http://{host}:{port}")
    httpd.serve_forever()


if __name__ == "__main__":  # pragma: no cover
    logging.basicConfig(level=logging.INFO)
    serve()
