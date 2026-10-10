# Architecture

This document is the map. If you only have five minutes before a demo or a code
review, read this file top to bottom and you will know where everything lives.

---

## The one-paragraph version

BreatheBuddy is a small pipeline with a thin API in front of it.

1. **Ingest** pulls AQI readings (bundled mock feed, or the live OpenAQ v3 API).
2. **Nowcast** turns those scattered stations into a 500 m grid covering the next
   6 hours, adding a wind-driven stubble-burning plume on top.
3. **Policy** (Cedar) decides what a school is allowed to do today, and
   **alerts** notifies vulnerable people whose local AQI crosses their threshold.
4. A **Strands agent** answers natural-language questions by calling the same
   tools the pipeline uses - so the agent and the system never disagree.
5. A **stdlib HTTP server** serves a Leaflet dashboard that renders all of it.

Everything runs with `python run.py` and **no pip installs**. Optional packages
(cedarpy, the Strands SDK, boto3) light up the "real" engines when present, but the
code degrades gracefully when they are not - see [Design notes](DESIGN_NOTES.md)
for why that matters.

---

## Where the code lives

```
run.py                      entry point (--demo or serve the API)
src/breathebuddy/
  config.py                 all settings, env-driven (BB_* variables)
  models.py                 plain dataclasses: Reading, GridCell, School, Alert, RouteResult
  geo.py                    distance / bearing / lat-lon <-> grid offsets
  store.py                  in-memory state (+ optional S3/DynamoDB mirror)
  ingest.py                 feed adapters: mock + OpenAQ v3, PM2.5 -> CPCB AQI
  nowcast.py                the 500 m grid model, plume, clean_index, point forecast
  routing.py                Dijkstra: fastest route vs cleanest route
  policy.py                 Cedar evaluation (+ built-in fallback evaluator)
  alerts.py                 threshold + policy alerts, cooldown, publish
  agent.py                  Strands agent + deterministic SimpleAgent
  auth.py                   Cognito JWT/JWKS verification
  awsio.py                  every AWS SDK call, isolated in one class
  service.py                orchestration: bootstrap(), run_cycle(), the query helpers
  api.py                    the stdlib HTTP server (do_GET / do_POST)
  openapi.py                OpenAPI 3.0 spec + the /docs page
  ratelimit.py              per-client write limiter (429)
  demo.py                   CLI demo that exercises each feature
  policies/school_rules.cedar   the actual school rules, as code
frontend/                   Leaflet dashboard (index.html, app.js, styles.css, vendor/)
infra/
  template.yaml             SAM template: every AWS resource
  handler/app.py            Lambda entry points (same package as local)
  localstack/docker-compose.yml
scripts/
  selfcheck.py              end-to-end verification (98 checks)
  fetch_tiles.py            download/refresh the offline map tiles
tests/                      stdlib unittest suite
```

---

## Request lifecycle (local)

```
browser ──GET /aqi?lat=..&lon=..──► api.Handler._route_get
                                        │
                                        ▼
                                   service.aqi_query
                                        │  bootstrap() once, then:
                                        ▼
                                   nowcast.nowcast_point   (blend nearest grid cells)
                                        │
                                        ▼
                                   JSON back to the dashboard
```

`POST /subscribe` and `POST /cycle` go through the rate limiter
(`ratelimit.WRITE_LIMITER`) and then the auth gate (`auth.authorized`) before they
touch the store. Reads are open so the dashboard works without a login.

---

## The pipeline cycle

`service.run_cycle()` is the whole system in one function, and it is what
EventBridge / Step Functions trigger on AWS:

```
ingest_once(store)                 # fetch + store readings, mirror to S3/DynamoDB
      │
build_grid(store)                  # 500 m grid, IDW + plume + diurnal forecast
      │
check_school(school)  x N schools  # Cedar decides -> create alert if unsafe
check_subscribers(store)           # threshold crossings -> alerts
      │
put_metric(...)                    # CloudWatch (no-op locally)
```

The grid is cached on the store, so the API queries after a cycle are cheap.

---

## The nowcast model (the part worth explaining)

There is no trained ML model in the default path - deliberately. The model is
small, explainable, and fast, which matters when you are standing in front of
judges. It is three ideas stacked:

- **Inverse-distance weighting.** Each grid cell takes a weighted blend of nearby
  stations, with a high power (3) so a station's influence drops off sharply and
  local hotspots stay visible.
- **Physical modifiers.** Each station's contribution is nudged by traffic
  (`1 + 0.15·congestion`) and by wind dispersion (more wind → cleaner).
- **A stubble plume.** Fires in `data/events.json` project a wind-aligned smoke
  cone onto the grid: strongest straight downwind, zero upwind, fading with
  distance. Switch it off with `BB_STUBBLE_BURNING=false` to show the clean baseline.

`nowcast_point()` blends the four nearest cells for an arbitrary coordinate, which
is what `/aqi` returns. If `BB_SAGEMAKER_ENDPOINT` is set, the same call delegates
to a deployed endpoint and the response is tagged `engine: sagemaker` - the
interface does not change.

---

## AWS mapping

Every AWS call is in `awsio.py` and every resource is in `infra/template.yaml`.
The Lambda handlers in `infra/handler/app.py` import the **same** `breathebuddy`
package, so local and deployed behaviour use one code path.

| Concern | Local | AWS |
|---------|-------|-----|
| Schedule | `python run.py` | EventBridge 15-min rule |
| Ingest | `ingest.fetch_readings` | Lambda `lambda_ingest` → S3 + DynamoDB |
| Orchestration | `run_cycle()` | Step Functions state machine |
| Policy | `policy.evaluate` (Cedar) | Lambda `lambda_policy` |
| Alerts | outbox + local buffer | SNS + SQS → `lambda_buffer` → S3 |
| API | `api.serve` (stdlib) | API Gateway + Lambda `lambda_api` |
| Auth | presence check | Cognito authorizer + JWKS verify |
| Metrics | log only | CloudWatch metrics + alarm |
| Search | in-memory grid | OpenSearch geo index |
| Hosting | stdlib static files | CloudFront + S3 + Route 53 (or Amplify) |

---

## Reading order

If you are new to the repo, read in this order and you will have the whole story:

1. `run.py` - the two entry points.
2. `service.py` - the orchestration; this is the table of contents for the domain.
3. `nowcast.py` - the model behind every number the UI shows.
4. `policy.py` + `policies/school_rules.cedar` - the decision layer.
5. `api.py` - how the browser talks to all of it.
6. `frontend/app.js` - the map, the time-slider, routing and the agent card.
7. `infra/template.yaml` - how it becomes a deployed system.

For the reasoning behind the non-obvious choices, see
[Design notes](DESIGN_NOTES.md).
