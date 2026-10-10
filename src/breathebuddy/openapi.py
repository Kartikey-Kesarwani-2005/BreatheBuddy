"""OpenAPI 3.0 description of the BreatheBuddy HTTP API + a tiny offline doc page.

The spec is data (no framework), so both the local stdlib server and the Lambda
handler can serve the same ``/openapi.json``. ``render_docs_html`` produces a
dependency-free HTML page (no CDN, works offline) that lists every endpoint.
"""
from __future__ import annotations

import html
import json

SPEC: dict = {
    "openapi": "3.0.3",
    "info": {
        "title": "BreatheBuddy API",
        "version": "0.1.0",
        "description": ("Hyperlocal air-quality nowcast, clean-air routing, Cedar school "
                        "rules and vulnerable alerts. Local stdlib server == API Gateway handler."),
    },
    "servers": [{"url": "/", "description": "Same host"}],
    "tags": [
        {"name": "nowcast", "description": "AQI nowcast + hyperlocal grid"},
        {"name": "routing", "description": "Fastest vs cleanest routes"},
        {"name": "policy", "description": "Cedar school bad-day rules"},
        {"name": "alerts", "description": "Vulnerable subscriber alerts"},
        {"name": "agent", "description": "Strands agent (natural-language Q&A)"},
        {"name": "ops", "description": "Health, cycle, buffer, docs"},
    ],
    "paths": {
        "/health": {
            "get": {"tags": ["ops"], "summary": "Liveness + city",
                    "responses": {"200": {"description": "OK"}}}},
        "/aqi": {
            "get": {"tags": ["nowcast"], "summary": "Nowcast for a point",
                    "parameters": [
                        {"name": "lat", "in": "query", "required": True, "schema": {"type": "number"}},
                        {"name": "lon", "in": "query", "required": True, "schema": {"type": "number"}}],
                    "responses": {"200": {"description": "aqi_now, aqi_forecast[6], clean_index"},
                                  "400": {"description": "Invalid coordinates"}}}},
        "/route": {
            "get": {"tags": ["routing"], "summary": "Fastest vs cleanest route",
                    "parameters": [
                        {"name": "from", "in": "query", "schema": {"type": "string"},
                         "description": "lat,lon", "example": "28.6,77.1"},
                        {"name": "to", "in": "query", "schema": {"type": "string"},
                         "description": "lat,lon", "example": "28.6,77.3"},
                        {"name": "mode", "in": "query", "schema": {"type": "string",
                         "enum": ["fastest", "cleanest"]}}],
                    "responses": {"200": {"description": "Route comparison + winner"},
                                  "400": {"description": "Bad or out-of-range coords"}}}},
        "/school/{id}/today": {
            "get": {"tags": ["policy"], "summary": "School bad-day decision card",
                    "parameters": [{"name": "id", "in": "path", "required": True,
                                    "schema": {"type": "string"}}],
                    "responses": {"200": {"description": "Allowed/blocked activities + indoor advisory"},
                                  "404": {"description": "Unknown school"}}}},
        "/subscribe": {
            "post": {"tags": ["alerts"], "summary": "Register a vulnerable user",
                     "security": [{"bearerAuth": []}],
                     "responses": {"201": {"description": "Subscriber created"},
                                   "401": {"description": "Missing/invalid token"},
                                   "429": {"description": "Rate limited"}}}},
        "/agent": {
            "post": {"tags": ["agent"], "summary": "Ask the agent (Strands or deterministic)",
                     "responses": {"200": {"description": "answer + steps + engine"}}}},
        "/cycle": {
            "post": {"tags": ["ops"], "summary": "Run ingest → nowcast → policy → alert once",
                     "security": [{"bearerAuth": []}],
                     "responses": {"200": {"description": "Cycle summary"},
                                   "401": {"description": "Missing/invalid token"},
                                   "429": {"description": "Rate limited"}}}},
        "/grid": {"get": {"tags": ["nowcast"], "summary": "Hyperlocal grid cells",
                          "responses": {"200": {"description": "Array of cells"}}}},
        "/schools": {"get": {"tags": ["policy"], "summary": "Schools",
                             "responses": {"200": {"description": "Array of schools"}}}},
        "/stations": {"get": {"tags": ["nowcast"], "summary": "Latest station readings",
                              "responses": {"200": {"description": "Array of readings"}}}},
        "/alerts": {"get": {"tags": ["alerts"], "summary": "Recent alerts",
                            "responses": {"200": {"description": "Array of alerts"}}}},
        "/events": {"get": {"tags": ["nowcast"], "summary": "Environmental events (stubble plume)",
                            "responses": {"200": {"description": "Array of events"}}}},
        "/buffer": {"get": {"tags": ["ops"], "summary": "Buffered (SQS) messages",
                            "responses": {"200": {"description": "{buffered: [...]}"}}}},
        "/openapi.json": {"get": {"tags": ["ops"], "summary": "This specification",
                                  "responses": {"200": {"description": "OpenAPI document"}}}},
        "/docs": {"get": {"tags": ["ops"], "summary": "Human-readable API docs",
                          "responses": {"200": {"description": "HTML"}}}},
    },
    "components": {
        "securitySchemes": {
            "bearerAuth": {"type": "http", "scheme": "bearer", "bearerFormat": "JWT"}}},
}


def render_docs_html(spec: dict | None = None) -> str:
    """A self-contained (no CDN) HTML page listing every endpoint."""
    spec = spec or SPEC
    rows = []
    for path, item in spec["paths"].items():
        for method, op in item.items():
            params = op.get("parameters", [])
            query = ", ".join(p["name"] for p in params if p.get("in") == "query")
            tags = ", ".join(op.get("tags", []))
            rows.append(
                f"<tr><td><span class='m {method}'>{method.upper()}</span></td>"
                f"<td><code>{html.escape(path)}</code></td>"
                f"<td>{html.escape(op.get('summary', ''))}</td>"
                f"<td>{html.escape(query)}</td><td>{html.escape(tags)}</td></tr>")
    title = html.escape(spec["info"]["title"])
    version = html.escape(spec["info"]["version"])
    desc = html.escape(spec["info"]["description"])
    return f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8" />
<meta name="viewport" content="width=device-width, initial-scale=1" />
<title>{title} - docs</title>
<style>
 body{{font-family:system-ui,Segoe UI,sans-serif;background:#0b1220;color:#e8edf7;margin:0;padding:28px}}
 h1{{margin:0 0 4px}} .sub{{color:#93a2bf;margin:0 0 18px}}
 table{{border-collapse:collapse;width:100%;font-size:13px}}
 th,td{{text-align:left;padding:8px 10px;border-bottom:1px solid #26324a;vertical-align:top}}
 th{{color:#93a2bf;font-weight:600}} code{{color:#4aa8ff}}
 .m{{font-weight:700;font-size:11px;padding:2px 6px;border-radius:5px}}
 .m.get{{background:rgba(74,168,255,.18);color:#4aa8ff}}
 .m.post{{background:rgba(53,210,158,.18);color:#35d29e}}
 a{{color:#35d29e}}
</style></head><body>
<h1>{title} <span class="sub">v{version}</span></h1>
<p class="sub">{desc}</p>
<p class="sub">Machine-readable spec: <a href="/openapi.json">/openapi.json</a></p>
<table><thead><tr><th>Method</th><th>Path</th><th>Summary</th>
<th>Query</th><th>Tags</th></tr></thead><tbody>
{''.join(rows)}
</tbody></table>
</body></html>"""


def spec_json() -> str:
    return json.dumps(SPEC, indent=2)
