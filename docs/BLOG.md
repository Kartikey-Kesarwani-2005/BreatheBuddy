# BreatheBuddy: hyperlocal air quality that *acts*, not just reports

**Track:** Air · **Event:** AWS Environmental Hacks (Bharat Builds Tour · WeMakeDevs), Oct 2026

**Team:** codeN4PTDY - Kartikey Kesarwani, Krishna Gupta, Varun Chakraborty, @antidoe

**Repo:** https://github.com/Kartikey-Kesarwani-2005/BreatheBuddy

**Built with:** AWS open source tools (Strands Agents SDK, Cedar, OpenSearch, SAM CLI,
LocalStack) + AWS free tier (Lambda, API Gateway, Step Functions, EventBridge, S3,
DynamoDB, SNS, SQS, CloudWatch, Cognito, CloudFront, Route 53, optional SageMaker)

---

## The problem

On paper, Delhi's Air Quality Index is a number. In practice, it's a decision.

Every winter, when the AQI crosses 300, schools still line kids up for outdoor
assembly. Riders still cycle through the worst corridors at 8 a.m. Asthma patients
still walk out the door with no warning. The apps tell everyone the *same city-wide
number*: an average that is wrong for almost every street, and that says nothing
about **what to actually do**.

We picked a sharp, human problem inside the Air theme: **school safety on bad-air
days**, plus the riders, kids and asthma patients around them. The goal was not
another AQI map. It was a system that **predicts, warns, and acts**.

## What BreatheBuddy does

1. **Hyperlocal nowcast.** From station readings we build a ~500 m grid (32x44 cells)
   and predict the next 6 hours per cell using inverse-distance weighting plus a
   diurnal dispersion curve. It is explainable: you can follow every number from
   station to cell to forecast.
2. **Stubble-burning plume.** A wind-driven smoke plume is added to every cell
   *downwind* of a fire event, so the north-west of the city visibly lights up on the
   map. This is the difference between "it's polluted" and "here's *why*, and where
   it's heading".
3. **Clean-air routing.** Given a start and end, it returns the **fastest** route and
   the **cleanest** route (lower average AQI), each with a clean-index score. You can
   also just tap two points on the map.
4. **Vulnerable alerts.** A rider or asthma patient signs up with their own threshold
   and location; the moment local AQI crosses it, an alert fires (SNS on AWS).
5. **School bad-day rules (Cedar).** The heart of the project. Instead of a hard-coded
   `if aqi > 200`, the schedule rules are written as **Cedar policies**: at AQI 153
   outdoor assembly is blocked but classes continue; at 300+ the school closes and
   moves remote. The agent *asks the policy engine*, so the answer is **policy, not
   opinion**.
6. **One-screen dashboard.** Live grid, a forecast **time-slider**, route compare, a
   "Today at your school" card with an **indoor-air advisory**, and an agent you can
   just ask. The UI is bilingual (English and Hindi).

Ask it in plain language, *"Should ABC School hold outdoor assembly at 8am tomorrow?"*,
and the Strands agent fetches the AQI, runs the Cedar policy, and sends the alert,
returning a reasoned decision with an action.

## Architecture at a glance

Local (Build It): no AWS account, no pip installs.

```
 mock JSON feed -> ingest -> nowcast grid (500 m, 6 h) -> clean/fast router
                                    |
                     Strands Agents SDK agent (tools)
                                    |
                     Cedar school policy -> alerts (outbox / SNS)
                                    |
                     stdlib HTTP API -> Leaflet dashboard
```

AWS (Ship It): the same `breathebuddy` package, wired to managed services.

```
 EventBridge(15m) -> Lambda ingest -> S3 (raw) + DynamoDB (latest)
                              |
                     Step Functions (ingest -> nowcast -> decide -> alert)
                              |
             Lambda nowcast (SageMaker-swappable) -> Lambda policy (Cedar)
                              |
                    SQS buffer -> Lambda buffer -> S3 archive
                              |
                    SNS (SMS/email) -> Cognito-auth users
                              |
           API Gateway (+Cognito authorizer) -> Lambda
                              |
           CloudFront + S3 + Route 53 (or Amplify Hosting) -> dashboard
                              |
                    CloudWatch logs / metrics / alarm · OpenSearch geo index
```

## The stack

- **AWS open source (Build It):** **Strands Agents SDK** (the agent), **Cedar** (the
  policy engine, via `cedarpy` with a built-in fallback), **OpenSearch** (geo index),
  **SAM CLI** and **LocalStack** for local AWS.
- **AWS cloud (Ship It):** **Lambda**, **API Gateway**, **Step Functions**,
  **EventBridge**, **S3**, **DynamoDB**, **SNS**, **SQS**, **CloudWatch**,
  **Cognito**, **CloudFront** + **Route 53** + **S3** hosting, and an optional
  **SageMaker** nowcast endpoint.
- **Runtime:** pure Python standard library for the whole local demo (zero pip
  installs to run it), with optional packages that light up the AWS/agent paths.

The same code runs locally and ships to AWS: the local HTTP server and the API Gateway
Lambda handler share the same request logic, and the SAM template imports the same
package.

## What fought back

Hackathon projects are mostly a list of things that unexpectedly didn't work. Ours:

- **The Strands SDK API moved under us.** Our first wrapper assumed `create_agent(...)`.
  When we actually read the installed package, the real API was
  `Agent(model=BedrockModel(...), tools=[...], system_prompt=...)`, `tool(func, ...)`,
  and `agent(prompt)` returning an `AgentResult` whose `str()` is the text. We rewired
  it, kept a deterministic fallback, and added a test that asserts a **real** `Agent`
  object is constructed.
- **Cedar refused our floats.** The policy compares integer literals, and passing
  `predicted_aqi=250.0` was treated as a Decimal against a Long, so the real engine
  default-denied the whole request. A normalise step (float to int where the policy
  expects an int) fixed it, with a regression test.
- **The map said "API key required".** Our offline basemap tiles came from CARTO, which
  had started returning an *"API key required"* placeholder. Because the downloader
  saved every response blindly, all 452 tiles were the **same** placeholder image. We
  switched to keyless **Esri "World Dark Gray"** tiles, added JPEG-magic and
  minimum-size validation so a placeholder can never be cached again, and re-downloaded
  real, distinct tiles.
- **Lambda query strings aren't always strings.** API Gateway can hand you
  `{"lat": ["28.6"]}` (list) or `{"lat": "28.6"}` (string) depending on how it is
  invoked. We normalised both so the handler matches the local server exactly, verified
  by a parity self-check.
- **Offline-first demo.** Judges shouldn't need internet, credentials, or a credit card
  to see it run. So Leaflet is vendored, the tiles are vendored, and `python run.py`
  needs *nothing* installed.

## Why it is built on AWS (and how)

It uses several **AWS open source tools** (Strands, Cedar, OpenSearch, SAM CLI,
LocalStack), which on its own satisfies the eligibility rule, and it also **deploys on
the AWS free tier** through a single SAM template. Nothing outside the Build It / Ship
It lists is used.

The AWS path is deliberately serverless and cheap: EventBridge triggers a Lambda ingest
every 15 minutes into S3 + DynamoDB; Step Functions orchestrates nowcast, decide and
alert; SNS delivers and SQS buffers alerts to an archive Lambda; Cognito guards the
write endpoints; CloudWatch watches the pipeline; API Gateway serves the API; CloudFront
+ S3 + Route 53 host the dashboard.

## Read the code

The repo is organised so a reviewer can follow the whole story:

- `docs/ARCHITECTURE.md` - the code map, request lifecycle and reading order.
- `docs/DESIGN_NOTES.md` - why each non-obvious choice was made.
- `docs/DEPLOY.md` - deploy it yourself with SAM.

## Try it

```bash
git clone https://github.com/Kartikey-Kesarwani-2005/BreatheBuddy
cd BreatheBuddy
python run.py                 # dashboard at http://localhost:8000 (stdlib only)
python run.py --demo          # CLI walkthrough of every acceptance criterion
python scripts/selfcheck.py   # 98/98 end-to-end checks
```

To run the cloud version:

```bash
sam build  -t infra/template.yaml
sam deploy -t infra/template.yaml --guided
```

## What's next

- 7-day trends per school, persisted (DynamoDB in prod).
- A trained SageMaker model behind the same `nowcast` interface.
- Push notifications for riders, and an SMS-first flow for feature phones.

**Har saans, safe.** Because a clean-air app that doesn't change what happens on a bad
day is just a very colourful number.

---

*Tags: #AWS #Strands #Cedar #Serverless #AirQuality #OpenSource #Hackathon*
