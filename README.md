# BreatheBuddy

**Har saans, safe.** — a hyperlocal air-quality buddy that predicts street-level AQI,
warns the most exposed people on time, enforces school bad-day rules, and suggests the
**cleanest** route instead of just the fastest.

> Track: **Air — Help people breathe easier.** Sub-focus: **School safety on bad days**
> (also covers AQI, pollution exposure, **stubble burning** and **indoor air**).
> One-liner: predict → warn → act. Not just another AQI number.

## Track alignment & eligibility

The Air theme asks you to *track what's in the air, warn the people most exposed to it,
and change what happens on the bad days*. BreatheBuddy does all three:

| Track requirement | BreatheBuddy |
|-------------------|--------------|
| "Track what's in the air" | 15-min ingest + **500 m hyperlocal nowcast** (6 h) |
| "Warn the people most exposed" | vulnerable profiles (kid/rider/asthma) → **SNS alerts** on threshold |
| "Change what happens on bad days" | **Cedar** school rules: cancel assembly / move PE indoors / close school |
| Stubble burning | wind-driven **smoke plume** on the grid + event banner (`data/events.json`) |
| Indoor air | per-school **indoor AQI estimate + purifier/window advisory** |

**Eligibility (the rule that unlocks prizes):** *use at least one AWS open source tool **or**
be deployed on AWS.* BreatheBuddy satisfies **both**:

- **AWS open source tools used:** Strands Agents SDK, Cedar, OpenSearch, SAM CLI, LocalStack.
- **Deployable on AWS:** `infra/template.yaml` (SAM) deploys to the free-tier Ship It services.
- Every AWS service referenced is from the official Build It / Ship It lists — see the
  [services section](#aws-services-used-all-from-the-provided-list).

> Human step for the tournament: **verify your student status on AWS Builder Center** — it's
> required to compete and unlocks the rewards/credits.

---

## What it does

| # | Feature | Where |
|---|---------|-------|
| 1 | Ingest AQI + weather + traffic (mock feed, every 15 min) | `ingest.py`, EventBridge schedule |
| 2 | Hyperlocal nowcast on a **~500 m grid, next 6 h** | `nowcast.py` |
| 3 | **Fastest vs cleanest** route with a clean-index score | `routing.py` |
| 4 | Vulnerable-profile alerts on threshold crossing | `alerts.py`, SNS |
| 5 | Policy-driven **school bad-day rules (Cedar)** | `policies/school_rules.cedar`, `policy.py` |
| 6 | Dashboard: AQI map + route compare + "Today at your school" | `frontend/` |

## Architecture

**Build It — local, open source, no AWS account**

```
 mock JSON feed ─► ingest ─► nowcast grid (500 m, 6 h) ─► clean/fast router
                                   │
                     Strands Agents SDK agent (tools)
                                   │
                     Cedar school policy ─► alerts (mock outbox / SNS)
                                   │
                     stdlib HTTP API  ─►  Leaflet dashboard
```

**Ship It — AWS free tier (allowed services only)**

```
 EventBridge(15m) ─► Lambda ingest ─► S3 (raw) + DynamoDB (latest)
                              │
                     Step Functions  (ingest ─► nowcast ─► decide ─► alert)
                              │
              Lambda nowcast (SageMaker-swappable) ─► Lambda policy (Cedar)
                              │
                    SQS (buffer) ─► SNS (SMS/email) ─► Cognito-auth users
                              │
           API Gateway + Lambda ─► Amplify Hosting (+CloudFront/Route 53)
                              │
                        CloudWatch logs/metrics · OpenSearch geo index
```

---

## Quickstart — Build It (2 commands, zero dependencies)

Requires **Python 3.10+** (tested on 3.14). No pip installs, no AWS account.

```bash
python run.py            # 1) start API + dashboard  ->  http://localhost:8000
python run.py --demo     # or: run the CLI demo of all acceptance criteria
```

Open the dashboard, click **Run 15-min cycle**, then **Compare routes** and **Ask agent**.

### Optional: real Cedar + Strands agent

```bash
pip install -r requirements.txt
# Verified on Python 3.14. After install:
#   - cedarpy runs the REAL Cedar engine on school_rules.cedar (engine="cedar").
#   - Strands Agents SDK is available; set BB_USE_STRANDS=true + a model
#     (Bedrock on AWS) to use the LLM agent instead of the deterministic fallback.
```

### Tests

```bash
python -m unittest discover -s tests -t . -v   # 16 unit tests
python scripts/selfcheck.py                     # 42 end-to-end checks (policy, API, template)
```

---

## API (local stdlib server == API Gateway handler)

| Method | Path | Description |
|--------|------|-------------|
| GET | `/aqi?lat=&lon=` | Nowcast for a point: `aqi_now`, `aqi_forecast[6]`, `clean_index` |
| GET | `/route?from=lat,lon&to=lat,lon[&mode=fastest\|cleanest]` | Fastest vs cleanest + clean-index + winner |
| GET | `/school/{id}/today` | Alert card: allowed/blocked activities + indoor advisory + headline |
| POST | `/subscribe` | Register a vulnerable user `{name, phone/email, lat, lon, threshold_aqi, kind}` |
| POST | `/agent` | Ask the agent: `{"question": "..."}` |
| GET | `/grid`, `/schools`, `/stations`, `/alerts`, `/events`, `/health` | Dashboard helpers |
| POST | `/cycle` | Run ingest → nowcast → policy → alert once |

**Example**

```bash
curl "http://localhost:8000/aqi?lat=28.6129&lon=77.2295"
curl "http://localhost:8000/route?from=28.6,77.1&to=28.6,77.3"
curl "http://localhost:8000/school/ABC/today"
curl -X POST http://localhost:8000/subscribe \
  -H "Content-Type: application/json" \
  -d '{"name":"Ravi","phone":"+91-90000-12345","lat":28.646,"lon":77.31,"threshold_aqi":150,"kind":"asthma"}'
```

### Agent

```bash
curl -X POST http://localhost:8000/agent -H "Content-Type: application/json" \
  -d '{"question":"Should ABC School hold outdoor assembly at 8am tomorrow?"}'
# -> "No — hold outdoor assembly at ABC Public School is not allowed (predicted AQI ~210).
#     Alert sent to school admin via SNS."
```

Tools: `get_aqi`, `predict_aqi`, `find_cleanest_route`, `check_school_policy(Cedar)`, `send_alert(SNS)`.

---

## Cedar school rules (`src/breathebuddy/policies/school_rules.cedar`)

```
AQI > 150  -> outdoor assembly requires masks + time limit (forbid without)
AQI > 200  -> cancel outdoor assembly / move PE indoors
AQI > 300  -> close school / remote learning (indoor_activities permitted)
```

Cedar uses **default-deny**; a `forbid` always overrides a `permit`. The built-in
evaluator parses the same `.cedar` file when `cedarpy` is not installed.

---

## Project structure

```
BreatheBuddy/
├── run.py                     # launcher: server or --demo
├── requirements.txt           # optional full-path deps
├── data/                      # mock stations + schools (+ alerts outbox)
├── src/breathebuddy/
│   ├── config.py models.py geo.py
│   ├── store.py ingest.py nowcast.py routing.py
│   ├── policy.py + policies/school_rules.cedar
│   ├── alerts.py agent.py awsio.py service.py api.py demo.py
├── frontend/                  # Leaflet dashboard (Amplify Hosting)
├── infra/                     # SAM template + Lambda handlers + Step Functions
│   ├── template.yaml  samconfig.toml
│   ├── handler/app.py
│   └── localstack/docker-compose.yml
├── scripts/                   # LocalStack bootstrap + cycle
├── tests/                     # stdlib unittest (15 tests)
└── demo/demo_script.md        # 60–90s demo narration
```

---

## Ship It — deploy to AWS (SAM)

Pre-req: an AWS account on the **Free Tier** (up to $200 credits), plus
[AWS SAM CLI](https://docs.aws.amazon.com/serverless-application-model/) and AWS credentials
(`aws configure`).

```bash
sam build   -t infra/template.yaml
sam deploy  -t infra/template.yaml --guided
# or:  make sam-build && make sam-deploy
```

This creates (allowed services only): **S3, DynamoDB, SNS, SQS, Lambda, API Gateway,
Step Functions, EventBridge, IAM, CloudWatch**.

### Go-live runbook

1. **Deploy the backend**
   ```bash
   sam deploy --guided        # accept defaults; note the ApiUrl output
   aws cloudformation describe-stacks --stack-name breathebuddy \
     --query "Stacks[0].Outputs" --output table
   ```
2. **Kick a cycle** (don't wait 15 min): the EventBridge rule runs every 15 minutes, or run it
   now from the console: **Step Functions → breathebuddy-pipeline → Start execution** `{}`.
3. **Point the frontend at the API** — edit `frontend/amplify-config.js`:
   ```js
   apiBase: "https://<id>.execute-api.<region>.amazonaws.com/prod"
   ```
4. **Amplify Hosting** — connect this repo; it reads `amplify.yml` and publishes `frontend/`.
   You get a public `https://<branch>.<app>.amplifyapp.com` URL (Ship It).
5. **(Optional) Cognito** — create a user pool + app client with hosted UI; paste the login URL
   into `amplify-config.js` → `cognito.hostedUi`. The "Sign in (Cognito)" button then works.
6. **(Optional) Route 53 / CloudFront** — put a custom domain in front of the Amplify domain.
7. **(Optional) Email alerts** — redeploy with `AlertEmail=you@example.com` to subscribe it to the
   SNS topic and receive real alert emails.

> Cost note: everything here is free-tier friendly (on-demand DynamoDB, Lambda/Step Functions
> request-based, S3 storage). The mock feed keeps volumes tiny; tear down with
> `sam delete` / `aws cloudformation delete-stack` when done.

### Try the AWS path locally with LocalStack

```bash
pip install boto3
docker compose -f infra/localstack/docker-compose.yml up -d
python scripts/localstack_bootstrap.py      # prints env exports (S3/DDB/SNS/SQS)
# export the printed variables, then:
python scripts/localstack_cycle.py          # writes S3 object + DDB items + SNS msg
```

---

## Acceptance criteria — how each is met

1. **Runs locally in <2 commands** → `python run.py` (works with the stdlib; no installs).
2. **Cleanest ≠ fastest, lower avg AQI** → `python run.py --demo` step 3 shows the cleanest route
   as longer but with a lower average AQI (see `tests/test_routing.py`).
3. **Cedar blocks an activity on a high-AQI day** → `school/{id}/today` blocks
   `hold_outdoor_assembly` and reports the matching forbid rule (`tests/test_policy.py`).
4. **Alert on threshold crossing** → subscriber check creates an alert, published to SNS or
   the local `data/alerts_outbox.json` (`tests/test_alerts.py`).
5. **Deployable with only allowed services** → `infra/template.yaml` (SAM) + `amplify.yml`.
6. **No AWS service outside the list** → see services enumerated above.

---

## How this maps to the judging criteria

| Criterion | BreatheBuddy |
|-----------|--------------|
| **01 Idea & impact** | One focused problem — *school safety on bad-air days* — solved well: not a vague "air quality app" but a specific rule engine that changes today's schedule for the people exposed (kids, riders, asthma patients). |
| **02 Built on AWS** | Uses AWS **open source tools** (Strands Agents SDK, Cedar, OpenSearch; SAM CLI, LocalStack locally) **and** is deployable on AWS free tier (Lambda, DynamoDB, S3, SNS, SQS, Step Functions, API Gateway, EventBridge, Amplify). |
| **03 Design & usability** | One screen anyone can pick up: a guided 4-step strip ("Run cycle → pick a school → compare routes → ask the agent"), plain-language decision card ("Outdoor assembly cancelled"), color-coded AQI map, and a subscribe form for non-technical users. |
| **04 Execution** | Everything **runs**, not "almost": `scripts/selfcheck.py` = 42/42, 16 unit tests, real Cedar engine active, live HTTP API + dashboard. |
| **05 Demo video** | **3-minute** script covering problem, who it's for, full walkthrough, and where AWS fits — `demo/demo_script.md`. |

> Note from the rules: *there is no live demo — the video is what judges see*, and *local and
> deployed projects are scored the same*. So a local recording is fully valid.

---

## AWS services used (all from the provided list)

Build It (open source): **Strands Agents SDK**, **Cedar**, **OpenSearch**, **SAM CLI**, **LocalStack**.
Ship It: **Lambda, API Gateway, Step Functions, EKS-ready/ECS-free design, S3, DynamoDB, SNS,
SQS, EventBridge, CloudWatch, Amplify Hosting, Cognito, Route 53, CloudFront**.
No other AWS service is referenced anywhere in the code or templates.

## Configuration

All settings are environment variables (see `.env.example`): grid size, forecast horizon,
city centre, alert thresholds, and AWS endpoints/tables. Defaults target Delhi with a
32×44 grid of 500 m cells (6-hour horizon).

## Limitations (hackathon scope)

- Ingest uses a bundled mock feed with deterministic 15-minute jitter; plug a real
  OpenAQ/CPCB feed into `ingest.fetch_mock` without touching anything else.
- The nowcast is an explainable IDW + diurnal model; swap it for a SageMaker endpoint via
  `nowcast.build_grid` / `nowcast_point` (same interface).
- Deployed Lambdas seed the demo dataset; a production build would read all readings from
  DynamoDB/OpenSearch. See `demo/demo_script.md` for the pitch.
