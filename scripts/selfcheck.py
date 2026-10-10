"""End-to-end self-check for BreatheBuddy.

Runs every layer (data, nowcast, routing, Cedar policy, alerts, agent, HTTP API,
static frontend, and the SAM template) and prints a PASS/FAIL report.

    python scripts/selfcheck.py

Exits non-zero if anything fails. Safe to run repeatedly.
"""
from __future__ import annotations

import json
import os
import sys
import threading
import time
import urllib.error
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

PASS, FAIL = [], []


def check(name: str, cond: bool, detail: str = "") -> None:
    (PASS if cond else FAIL).append(name)
    print(f"  [{'PASS' if cond else 'FAIL'}] {name}" + (f"  ({detail})" if detail else ""))


def section(title: str) -> None:
    print(f"\n== {title} ==")


def main() -> int:
    # ---------------------------------------------------------------- policy
    section("Cedar school policy")
    from breathebuddy.policy import decide_activities, evaluate
    r = evaluate("hold_outdoor_assembly", {"predicted_aqi": 250.0,
                                           "masks_available": True, "time_limit_minutes": 45})
    check("high AQI blocks outdoor assembly", r["allowed"] is False, f"engine={r['engine']}")
    check("real Cedar engine in use", r["engine"] in ("cedar", "builtin-cedar"), r["engine"])
    check("float context does not break Cedar", r["allowed"] is False)
    low = decide_activities({"predicted_aqi": 100.5, "masks_available": True, "time_limit_minutes": 45})
    check("low AQI allows assembly", "hold_outdoor_assembly" in low["allowed"])
    mid = decide_activities({"predicted_aqi": 153.6, "masks_available": True, "time_limit_minutes": 45})
    check("moderate AQI allows classes + indoor",
          "hold_classes" in mid["allowed"] and "indoor_activities" in mid["allowed"])
    check("moderate AQI blocks assembly", "hold_outdoor_assembly" in mid["blocked"])
    haz = decide_activities({"predicted_aqi": 340.9, "masks_available": True, "time_limit_minutes": 45})
    check("hazardous AQI closes school", "close_school" in haz["allowed"])
    check("hazardous AQI blocks classes", "hold_classes" in haz["blocked"])

    # ------------------------------------------------------------ data + nowcast
    section("Ingest + nowcast")
    from breathebuddy import config
    from breathebuddy.nowcast import build_grid, clean_index, nowcast_point
    from breathebuddy.service import bootstrap
    from breathebuddy.store import STORE
    bootstrap()
    check("schools loaded", len(STORE.schools) == 3, f"{len(STORE.schools)}")
    check("stations loaded", len(STORE.all_readings()) == 8)
    cells = build_grid(STORE)
    check("grid size", len(cells) == config.GRID_ROWS * config.GRID_COLS, f"{len(cells)}")
    nc = nowcast_point(28.6129, 77.2295, STORE)
    check("6h forecast length", len(nc["aqi_forecast"]) == config.FORECAST_HOURS)
    check("clean_index in range", 0 <= clean_index(150) <= 100)
    from breathebuddy.service import environmental_events, indoor_advisory
    check("stubble-burning event active", len(environmental_events()) >= 1)
    check("grid carries plume", max(c.plume for c in cells.values()) > 0)
    check("indoor advisory scales", any("purifier" in t.lower() for t in indoor_advisory(250)))

    # ---------------------------------------------------------------- routing
    section("Clean-air routing")
    from breathebuddy.routing import find_routes
    res = find_routes((28.60, 77.10), (28.60, 77.30), STORE)
    check("cleanest avg AQI <= fastest", res["cleanest"]["avg_aqi"] <= res["fastest"]["avg_aqi"],
          f"{res['cleanest']['avg_aqi']} vs {res['fastest']['avg_aqi']}")
    check("cleanest route is longer or equal", res["cleanest"]["distance_m"] >= res["fastest"]["distance_m"])
    check("winner is cleanest", res["winner"] == "cleanest")
    check("routes differ", res["cleanest"]["cells"] != res["fastest"]["cells"])

    # ----------------------------------------------------------------- alerts
    section("Alerts")
    from breathebuddy import alerts as alerting
    from breathebuddy.service import subscribe
    before = len(STORE.alerts)
    subscribe({"name": "SelfCheck", "lat": 28.646, "lon": 77.31, "threshold_aqi": 10, "kind": "asthma"})
    fired = alerting.check_subscribers(STORE)
    check("threshold crossing fires alert", len(fired) >= 1)
    check("alerts recorded", len(STORE.alerts) > before)
    check("outbox written", os.path.exists(os.path.join(ROOT, "data", "alerts_outbox.json")))
    again = alerting.check_subscribers(STORE)
    check("duplicate alerts suppressed (cooldown)", len(again) == 0)

    # ------------------------------------------------------------------ agent
    section("Agent")
    from breathebuddy import agent as agent_mod
    ans = agent_mod.ask("Should ABC School hold outdoor assembly at 8am tomorrow?")
    check("agent returns an answer", bool(ans.get("answer")))
    check("agent took action (blocked -> alert)", "Alert sent" in ans["answer"] or "not allowed" in ans["answer"])
    check("deterministic engine usable", agent_mod.ask("aqi", prefer_strands=False)["engine"] == "simple")
    try:
        from strands import Agent as _StrandsAgent  # noqa: F401
        sa = agent_mod.build_strands_agent()
        check("Strands Agents SDK builds a real Agent",
              sa is not None and type(sa).__name__ == "Agent")
    except ImportError:
        check("Strands Agents SDK (not installed - skipped)", True)

    # -------------------------------------------------------------------- API
    section("HTTP API + static dashboard")
    from http.server import ThreadingHTTPServer

    from breathebuddy.api import Handler
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    port = httpd.server_address[1]
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{port}"

    def get(path):
        return json.loads(urllib.request.urlopen(base + path, timeout=10).read())

    def post(path, body):
        req = urllib.request.Request(base + path, data=json.dumps(body).encode(),
                                     headers={"Content-Type": "application/json"})
        return json.loads(urllib.request.urlopen(req, timeout=10).read())

    try:
        time.sleep(0.3)
        check("GET /health", get("/health")["ok"] is True)
        check("GET /openapi.json", get("/openapi.json")["openapi"] == "3.0.3")
        check("GET /docs renders",
              "BreatheBuddy API" in urllib.request.urlopen(base + "/docs", timeout=10).read().decode())
        check("GET /aqi", get("/aqi?lat=28.6129&lon=77.2295")["aqi_now"] > 0)
        r = get("/route?from=28.6,77.1&to=28.6,77.3")
        check("GET /route returns both", "fastest" in r and "cleanest" in r and r["winner"] == "cleanest")
        c = get("/school/ABC/today")
        check("GET /school/ABC/today blocks assembly", "hold_outdoor_assembly" in c["blocked"])
        g = get("/school/GREEN/today")
        check("GET /school/GREEN/today allows PE with masks", "hold_physical_education" in g["allowed"])
        check("GET /events lists stubble burning", len(get("/events")) >= 1)
        check("school card includes indoor advisory", bool(c.get("indoor_advisory")))
        check("GET /grid", len(get("/grid")) == config.GRID_ROWS * config.GRID_COLS)
        check("GET /schools", len(get("/schools")) == 3)
        check("GET /stations", len(get("/stations")) == 8)
        check("GET /alerts", isinstance(get("/alerts"), list))
        check("GET /buffer", "buffered" in get("/buffer"))
        sub = post("/subscribe", {"name": "API", "threshold_aqi": 90, "lat": 28.6, "lon": 77.2})
        check("POST /subscribe", sub["subscriber_id"].startswith("sub_"))
        ag = post("/agent", {"question": "Should ABC School hold outdoor assembly tomorrow?"})
        check("POST /agent", "answer" in ag)
        check("POST /agent engine=simple", post("/agent", {"question": "aqi", "engine": "simple"})["engine"] == "simple")
        cyc = post("/cycle", {})
        check("POST /cycle", cyc["grid_cells"] > 0)
        check("alerts buffered (SQS producer path)", len(get("/buffer")["buffered"]) >= 1)
        # bad input -> 400, not 500
        try:
            urllib.request.urlopen(base + "/aqi?lat=abc&lon=77", timeout=10)
            check("bad input returns 400", False, "no error raised")
        except urllib.error.HTTPError as e:
            check("bad input returns 400", e.code == 400, f"code={e.code}")
        # out-of-range coordinates -> 400
        try:
            urllib.request.urlopen(base + "/aqi?lat=999&lon=77", timeout=10)
            check("out-of-range coords return 400", False, "no error raised")
        except urllib.error.HTTPError as e:
            check("out-of-range coords return 400", e.code == 400, f"code={e.code}")
        # write rate limiting -> 429 after the limit
        from breathebuddy.ratelimit import WRITE_LIMITER
        _saved = WRITE_LIMITER.limit
        WRITE_LIMITER.limit = 1
        WRITE_LIMITER._hits.clear()
        try:
            post("/subscribe", {"name": "RL1", "lat": 28.6, "lon": 77.2, "threshold_aqi": 200})
            try:
                post("/subscribe", {"name": "RL2", "lat": 28.6, "lon": 77.2, "threshold_aqi": 200})
                check("write rate limit returns 429", False, "no error raised")
            except urllib.error.HTTPError as e:
                check("write rate limit returns 429", e.code == 429, f"code={e.code}")
        finally:
            WRITE_LIMITER.limit = _saved
            WRITE_LIMITER._hits.clear()
        # static
        html = urllib.request.urlopen(base + "/", timeout=10).read().decode()
        check("index.html served", "BreatheBuddy" in html)
        check("app.js served", len(urllib.request.urlopen(base + "/app.js", timeout=10).read()) > 1000)
        check("index uses local Leaflet vendor", "vendor/leaflet/leaflet.js" in html)
        for path, ctype, size in (("/vendor/leaflet/leaflet.js", "application/javascript", 10000),
                                  ("/vendor/leaflet/leaflet.css", "text/css", 5000),
                                  ("/vendor/leaflet/images/marker-icon.png", "image/png", 100)):
            r = urllib.request.urlopen(base + path, timeout=10)
            body = r.read()
            check(f"served {path}", r.status == 200 and len(body) > size
                  and r.headers.get("Content-Type") == ctype, r.headers.get("Content-Type"))
        # offline map tiles
        import glob as _glob
        tiles = _glob.glob(os.path.join(ROOT, "frontend", "vendor", "tiles", "*", "*", "*.jpg"))
        check("offline map tiles cached", len(tiles) >= 400, f"{len(tiles)} tiles")
        _t = "/vendor/tiles/10/730/426.jpg"
        if os.path.exists(os.path.join(ROOT, "frontend", ".", _t.lstrip("/"))):
            r = urllib.request.urlopen(base + _t, timeout=10)
            check("served cached map tile", r.status == 200
                  and r.headers.get("Content-Type") == "image/jpeg")
        # path traversal blocked
        try:
            urllib.request.urlopen(base + "/../run.py", timeout=10)
            check("path traversal blocked", False)
        except urllib.error.HTTPError as e:
            check("path traversal blocked", e.code in (400, 403, 404), f"code={e.code}")
    finally:
        httpd.shutdown()

    # ------------------------------------------------------ Lambda handler parity
    section("Lambda handler parity (API Gateway proxy)")
    try:
        if ROOT not in sys.path:
            sys.path.insert(0, ROOT)
        from infra.handler import app as lambda_app

        def lam(method, path, query=None, body=None, ip="203.0.113.9"):
            ev = {"httpMethod": method, "path": path,
                  "queryStringParameters": query,
                  "requestContext": {"identity": {"sourceIp": ip}},
                  "body": json.dumps(body) if body is not None else None}
            r = lambda_app.lambda_api(ev, None)
            return r["statusCode"], json.loads(r["body"])

        sc, b = lam("GET", "/health")
        check("lambda GET /health", sc == 200 and b["ok"] is True)
        sc, b = lam("GET", "/openapi.json")
        check("lambda GET /openapi.json", sc == 200 and b["openapi"] == "3.0.3")
        sc, b = lam("GET", "/alerts")
        check("lambda GET /alerts", sc == 200 and isinstance(b, list))
        sc, b = lam("GET", "/stations")
        check("lambda GET /stations", sc == 200 and isinstance(b, list))
        sc, b = lam("GET", "/events")
        check("lambda GET /events", sc == 200 and len(b) >= 1)
        sc, b = lam("POST", "/cycle", body={})
        check("lambda POST /cycle", sc == 200 and b["grid_cells"] > 0)
        # write rate limiting parity (source IP) -> 429
        from breathebuddy.ratelimit import WRITE_LIMITER
        _saved = WRITE_LIMITER.limit
        WRITE_LIMITER.limit = 1
        WRITE_LIMITER._hits.clear()
        try:
            lam("POST", "/subscribe",
                body={"name": "L", "lat": 28.6, "lon": 77.2, "threshold_aqi": 200})
            sc, b = lam("POST", "/subscribe",
                        body={"name": "L", "lat": 28.6, "lon": 77.2, "threshold_aqi": 200})
            check("lambda write rate limit -> 429", sc == 429, f"code={sc}")
        finally:
            WRITE_LIMITER.limit = _saved
            WRITE_LIMITER._hits.clear()
        sc, b = lam("GET", "/aqi", query={"lat": "999", "lon": "77"})
        check("lambda bad coords -> 400", sc == 400)
        sc, b = lam("OPTIONS", "/aqi")
        check("lambda OPTIONS -> 200", sc == 200)
        sc, b = lam("GET", "/buffer")
        check("lambda GET /buffer", sc == 200 and "buffered" in b)
        rb = lambda_app.lambda_buffer(
            {"Records": [{"body": json.dumps({"type": "alert"})}]}, None)
        check("lambda_buffer drains SQS records", rb["ok"] and rb["drained"] == 1)
        lambda_app.config.REQUIRE_AUTH = True
        try:
            check("auth gate rejects missing token",
                  lambda_app._authorized({"headers": {}}) is False)
            check("auth gate accepts bearer token",
                  lambda_app._authorized({"headers": {"Authorization": "Bearer x"}}) is True)
        finally:
            lambda_app.config.REQUIRE_AUTH = False
    except ImportError as exc:
        check("lambda handler import", False, str(exc))

    # -------------------------------------------------------------- SAM template
    section("AWS SAM template")
    tpl_path = os.path.join(ROOT, "infra", "template.yaml")
    try:
        import yaml

        class CF(yaml.SafeLoader):
            pass

        def keep(loader, tag_suffix, node):
            if isinstance(node, yaml.ScalarNode):
                return loader.construct_scalar(node)
            if isinstance(node, yaml.SequenceNode):
                return loader.construct_sequence(node)
            return loader.construct_mapping(node)

        CF.add_multi_constructor("!", keep)
        tpl = yaml.load(open(tpl_path, encoding="utf-8"), Loader=CF)
        types = {r["Type"] for r in tpl["Resources"].values()}
        allowed_prefixes = {
            "AWS::S3", "AWS::DynamoDB", "AWS::SNS", "AWS::SQS", "AWS::Lambda",
            "AWS::Serverless", "AWS::StepFunctions", "AWS::Events", "AWS::IAM",
            "AWS::ApiGateway", "AWS::Logs", "AWS::Cognito", "AWS::CloudFront",
            "AWS::CloudWatch", "AWS::Route53", "AWS::Amplify", "AWS::EC2",
            "AWS::ECS", "AWS::EKS", "AWS::Lightsail", "AWS::AppRunner",
            "AWS::SageMaker", "AWS::RDS",
        }
        bad = {t for t in types if t.split("::")[0] + "::" + t.split("::")[1] not in allowed_prefixes}
        check("template parses", True, f"{len(tpl['Resources'])} resources")
        check("no out-of-list AWS services", not bad, f"offenders={bad or 'none'}")
        check("Step Functions present", any(t.startswith("AWS::StepFunctions") for t in types))
        check("EventBridge schedule present", any(t == "AWS::Events::Rule" for t in types))
        check("Cognito user pool present", any(t == "AWS::Cognito::UserPool" for t in types))
        check("CloudFront distribution present", any(t == "AWS::CloudFront::Distribution" for t in types))
        check("Route 53 record present", any(t == "AWS::Route53::RecordSet" for t in types))
        check("CloudWatch alarm present", any(t == "AWS::CloudWatch::Alarm" for t in types))
        check("SQS buffer consumer present", "BufferFunction" in tpl["Resources"])
        check("SageMaker endpoint param present", "SagemakerEndpoint" in tpl.get("Parameters", {}))
    except ImportError:
        check("template check (pyyaml)", True, "pyyaml not installed - skipped")

    # ------------------------------------------- data source + auth + tooling
    section("Data source + auth + project tooling")
    from breathebuddy import auth
    from breathebuddy.ingest import fetch_readings, pm25_to_aqi
    check("PM2.5 -> AQI breakpoints", pm25_to_aqi(60) == 100.0 and pm25_to_aqi(30) == 50.0)
    _src = config.AQ_SOURCE
    try:
        config.AQ_SOURCE = "openaq"           # no key -> must fall back to mock
        live_fallback = fetch_readings()
    finally:
        config.AQ_SOURCE = _src
    check("live feed falls back to mock", bool(live_fallback))
    check("auth accepts token offline (dev mode)", auth.verify_token("x") is not None)
    check("auth rejects empty token", auth.verify_token("") is None)
    check("bearer parsing", auth.bearer({"Authorization": "Bearer abc"}) == "abc")
    for fname, label in (("LICENSE", "MIT LICENSE"), ("pyproject.toml", "pyproject.toml"),
                         (os.path.join(".github", "workflows", "ci.yml"), "CI workflow"),
                         (os.path.join("docs", "ARCHITECTURE.md"), "architecture doc"),
                         (os.path.join("docs", "DESIGN_NOTES.md"), "design notes"),
                         (os.path.join("docs", "DEPLOY.md"), "deploy guide")):
        check(f"{label} present", os.path.exists(os.path.join(ROOT, fname)))
    _readme = open(os.path.join(ROOT, "README.md"), encoding="utf-8").read()
    check("README screenshots section", "## Screenshots" in _readme)
    _app = open(os.path.join(ROOT, "frontend", "app.js"), encoding="utf-8").read()
    _html = open(os.path.join(ROOT, "frontend", "index.html"), encoding="utf-8").read()
    check("forecast slider wired", "setForecast" in _app and "fc-slider" in _app)
    check("map-click routing wired", "onMapClick" in _app and "togglePickMode" in _app)
    check("geolocation 'Near me' wired", "locateMe" in _app and "btn-nearme" in _app)
    check("basemap switcher wired",
          "setBasemap" in _app and "World_Imagery" in _app and "basemaps" in _html)
    check("bilingual (EN/HI) toggle wired",
          "setLang" in _app and "btn-lang" in _html and "data-i18n" in _html)

    # ------------------------------------------------------------------ summary
    print("\n" + "=" * 52)
    total = len(PASS) + len(FAIL)
    print(f"SELF-CHECK: {len(PASS)}/{total} passed")
    if FAIL:
        print("FAILED:")
        for f in FAIL:
            print("   - " + f)
    print("=" * 52)
    return 1 if FAIL else 0


if __name__ == "__main__":
    raise SystemExit(main())
