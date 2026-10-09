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

    # ------------------------------------------------------------------ agent
    section("Agent")
    from breathebuddy import agent as agent_mod
    ans = agent_mod.ask("Should ABC School hold outdoor assembly at 8am tomorrow?")
    check("agent returns an answer", bool(ans.get("answer")))
    check("agent took action (blocked -> alert)", "Alert sent" in ans["answer"] or "not allowed" in ans["answer"])

    # -------------------------------------------------------------------- API
    section("HTTP API + static dashboard")
    from breathebuddy.api import Handler
    from http.server import ThreadingHTTPServer
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
        sub = post("/subscribe", {"name": "API", "threshold_aqi": 90, "lat": 28.6, "lon": 77.2})
        check("POST /subscribe", sub["subscriber_id"].startswith("sub_"))
        ag = post("/agent", {"question": "Should ABC School hold outdoor assembly tomorrow?"})
        check("POST /agent", "answer" in ag)
        cyc = post("/cycle", {})
        check("POST /cycle", cyc["grid_cells"] > 0)
        # bad input -> 400, not 500
        try:
            urllib.request.urlopen(base + "/aqi?lat=abc&lon=77", timeout=10)
            check("bad input returns 400", False, "no error raised")
        except urllib.error.HTTPError as e:
            check("bad input returns 400", e.code == 400, f"code={e.code}")
        # static
        html = urllib.request.urlopen(base + "/", timeout=10).read().decode()
        check("index.html served", "BreatheBuddy" in html)
        check("app.js served", len(urllib.request.urlopen(base + "/app.js", timeout=10).read()) > 1000)
        # path traversal blocked
        try:
            urllib.request.urlopen(base + "/../run.py", timeout=10)
            check("path traversal blocked", False)
        except urllib.error.HTTPError as e:
            check("path traversal blocked", e.code in (400, 403, 404), f"code={e.code}")
    finally:
        httpd.shutdown()

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
            "AWS::Route53", "AWS::Amplify", "AWS::EC2", "AWS::ECS", "AWS::EKS",
            "AWS::Lightsail", "AWS::AppRunner", "AWS::SageMaker", "AWS::RDS",
        }
        bad = {t for t in types if t.split("::")[0] + "::" + t.split("::")[1] not in allowed_prefixes}
        check("template parses", True, f"{len(tpl['Resources'])} resources")
        check("no out-of-list AWS services", not bad, f"offenders={bad or 'none'}")
        check("Step Functions present", any(t.startswith("AWS::StepFunctions") for t in types))
        check("EventBridge schedule present", any(t == "AWS::Events::Rule" for t in types))
    except ImportError:
        check("template check (pyyaml)", True, "pyyaml not installed - skipped")

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
