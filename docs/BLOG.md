# BreatheBuddy — hyperlocal air quality that *acts*, not just reports

> **Track:** Air · **Event:** AWS Environmental Hacks (Bharat Builds Tour · WeMakeDevs), Oct 2026
> **Team:** codeN4PTDY · Kartikey Kesarwani, Krishna Gupta, Varun Chakraborty, @antidoe
> **Repo:** _&lt;add your GitHub URL&gt;_ · **Built with:** AWS open source tools + AWS free tier

---

## The problem

On paper, Delhi's Air Quality Index is a number. In practice, it's a decision.

Every winter, when the AQI crosses 300, schools still line kids up for outdoor assembly.
Riders still cycle through the worst corridors at 8 a.m. Asthma patients still walk out the
door with no warning. The apps tell everyone the *same city-wide number* — an average that's
wrong for almost every street, and tells you nothing about **what to actually do**.

We picked the Air track and a sharp, human problem inside it: **school safety on bad-air
days** (plus the riders, kids and asthma patients around them). The goal was not another AQI
map. It was a system that **predicts → warns → acts**.

## What BreatheBuddy does

1. **Hyperlocal nowcast.** From station readings we build a ~500 m grid (32×44 cells) and
   predict the next 6 hours per cell using inverse-distance-weighting plus a diurnal
   dispersion curve — explainable, no black box required to demo it.
2. **Stubble-burning plume.** A wind-driven smoke plume is added to every cell *downwind* of a
   fire event, so the north-west of the city visibly lights up in the dashboard. This is the
   difference between "it's polluted" and "here's *why*, and where it's heading".
3. **Clean-air routing.** Given a start and end, we return the **fastest** route *and* the
   **cleanest** route (lower average AQI), each with a clean-index score. You can also just tap
   two points on the map.
4. **Vulnerable alerts.** A rider or asthma patient signs up with their own threshold and
   location; the moment local AQI crosses it, an alert fires (SNS on AWS).
5. **School bad-day rules (Cedar).** The heart of the project. Rather than a hard-coded
   `if aqi > 200`, the schedule rules are written as **Cedar policies**: at AQI 153 outdoor
   assembly is blocked but classes continue; at 300+ the school closes and moves remote.
   The agent *asks the policy engine*, so the answer is **policy, not opinion**.
6. **One-screen dashboard.** Live grid, a forecast **time-slider**, route compare, the
   "Today at your school" card with an **indoor-air advisory**, and an agent you can just ask.

Ask it in plain language — *"Should ABC School hold outdoor assembly at 8am tomorrow?"* — and
the Strands agent fetches the AQI, runs the Cedar policy, and sends the alert, returning a
reasoned decision with an action.

## The stack

- **AWS open source (Build It):** **Strands Agents SDK** (the agent), **Cedar** (the policy
  engine — via `cedarpy`, with a built-in fallback), **OpenSearch** (geo index), **SAM CLI** and
  **LocalStack** for local AWS.
- **AWS cloud (Ship It):** **Lambda**, **API Gateway**, **Step Functions**, **EventBridge**,
  **S3**, **DynamoDB**, **SNS**, **SQS**, **CloudWatch**, **Cognito**, **CloudFront** +
  **Route 53** + **S3** hosting, and an optional **SageMaker** nowcast endpoint.
- **Runtime:** pure Python standard library for the whole local demo (zero pip installs to run
  it), with optional packages that light up the AWS/agent paths.

The same code runs locally and ships to AWS: the local HTTP server and the API Gateway Lambda
handler share the same request logic, and the SAM template imports the same package.

## What fought back

Hackathon projects are mostly a list of things that unexpectedly didn't work. Ours:

- **The Strands SDK API moved under us.** Our first wrapper assumed `create_agent(...)`. When
  we actually read the installed package, the real API was `Agent(model=BedrockModel(...),
  tools=[...], system_prompt=...)`, `tool(func, ...)`, and `agent(prompt)` returning an
  `AgentResult` whose `str()` is the text. We rewired it, kept a deterministic fallback, and
  added a test that asserts a **real** `Agent` object is constructed.
- **Cedar refused our floats.** The policy expects integer context in places; passing
  `predicted_aqi=250.0` silently failed a rule. A normalise step (`float → int` where the policy
  expects an int) fixed it, with a regression test.
- **The map said "API key required".** Our offline basemap tiles were fetched from CARTO, which
  had started returning an *"API key required"* placeholder — and because the downloader saved
  every response blindly, all 452 tiles were the **same** placeholder image. We switched to the
  keyless **Esri "World Dark Gray"** tiles, added JPEG-magic + minimum-size validation so a
  placeholder can never be cached again, and re-downloaded real distinct tiles.
- **Lambda query strings aren't always strings.** API Gateway can hand you `{"lat": ["28.6"]}`
  (list) or `{"lat": "28.6"}` (string) depending on how it's invoked. We normalised both so the
  handler matches the local server exactly — verified by a parity self-check.
- **Offline-first demo.** Judges shouldn't need internet, credentials, or a credit card to see
  it run. So Leaflet is vendored, the tiles are vendored, and `python run.py` needs *nothing*
  installed.

## Why it's built on AWS (and how)

It uses several **AWS open source tools** (Strands, Cedar, OpenSearch, SAM CLI, LocalStack),
which on its own satisfies the eligibility rule — and it also **deploys on the AWS free tier**
via a single SAM template. Nothing outside the Build It / Ship It lists is used.

The AWS path is deliberately serverless and cheap: EventBridge triggers a Lambda ingest every
15 minutes into S3 + DynamoDB; Step Functions orchestrates nowcast → decide → alert; SNS
delivers and SQS buffers alerts to an archive Lambda; Cognito guards the write endpoints;
CloudWatch watches the pipeline; API Gateway serves the API; CloudFront + S3 + Route 53 host
the dashboard.

## What's next

- Persistence (SQLite locally / DynamoDB in prod) and 7-day trends per school.
- Hindi localisation and a mobile-first pass for the people who need it most.
- A trained SageMaker model behind the same `nowcast` interface.
- Push notifications for riders, and an SMS-first flow for feature phones.

## Try it

```bash
git clone <repo>
cd BreatheBuddy
python run.py            # dashboard at http://localhost:8000 (stdlib only)
python run.py --demo     # CLI walkthrough of all five acceptance criteria
python scripts/selfcheck.py   # 96/96 end-to-end checks
```

**Har saans, safe.** — because a clean-air app that doesn't change what happens on a bad day
is just a very colourful number.
