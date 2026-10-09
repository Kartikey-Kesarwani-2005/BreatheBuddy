# BreatheBuddy — Build Prompt (saved for reuse)

ROLE
You are a senior full-stack + cloud engineer building a hackathon project. Build a working,
demo-ready project end-to-end. Prefer simple, reliable code over clever code.

PROJECT
Name: BreatheBuddy
Tagline: "Har saans, safe." (Your buddy for clean air.)
Track: Air — School safety on bad days / pollution exposure.
One-liner: A hyperlocal air-quality buddy that predicts street-level AQI, warns the most
exposed people (school kids, riders, asthma patients) on time, applies school bad-day rules,
and suggests the CLEANEST route instead of just the fastest.

PROBLEM
On bad-air days, schools still run outdoor assembly/sports and exposed people get no timely
warning. Existing apps only show an AQI number — they do not act.

CORE FEATURES (MVP)
1. Ingest AQI + weather + traffic data every 15 min (OpenAQ/CPCB-style feed; use mock data if no key).
2. Hyperlocal nowcast: predict AQI for a ~500m grid for the next 6 hours.
3. Clean-air routing: return "fastest route" vs "cleanest route" with a clean-index score.
4. Vulnerable alerts: school profile + individual exposure profile → trigger alert when thresholds cross.
5. School bad-day rules: policy-driven decisions (e.g. AQI>200 → cancel outdoor assembly, move PE indoors).
6. Dashboard: map with route comparison + a "Today at your school" alert card.

HARD CONSTRAINT — USE ONLY THESE AWS RESOURCES
You may use only the AWS tools/services listed below for anything AWS-related. Non-AWS
languages/frameworks/libraries are allowed freely. Do NOT introduce any other AWS service.

BUILD IT (local, open source, no AWS account):
- Agents/AI: Strands Agents SDK, PartyRock
- Containers/K8s: Finch, EKS Distro, EKS Anywhere
- Serverless local: SAM CLI, LocalStack
- Runtimes: Firecracker, Corretto
- Data/search: OpenSearch
- Auth/policy: Cedar

SHIP IT (deployed on AWS, free tier):
- AI: SageMaker AI
- Serverless: Lambda, API Gateway, Step Functions
- Containers: EKS, ECS, Fargate
- Servers/runtimes: EC2, Lightsail, App Runner, Amplify Hosting
- Data: S3, DynamoDB, RDS, Aurora
- Auth/policy: Cognito, Cedar
- Plumbing: CloudFront, Route 53, EventBridge, SQS, SNS, CloudWatch

ELIGIBILITY RULE
The project must use at least one AWS open source tool OR be deployed on AWS.
-> This project uses AWS open source tools (Strands Agents SDK + Cedar + OpenSearch) AND
   is deployable to AWS. Satisfy both.

ARCHITECTURE
Local (Build It):
  Strands Agents SDK agent orchestrates tools + Cedar enforces school rules + OpenSearch for
  geo/search; mock AQI data via local JSON; run with SAM CLI + LocalStack.

Deployed (Ship It):
  EventBridge (schedule, 15 min) -> Lambda ingest -> S3 (raw) + DynamoDB (latest readings)
  SageMaker AI (or Lambda container) -> AQI nowcast model endpoint
  Strands Agents SDK agent + Cedar rules -> decide alerts
  Step Functions -> orchestrate ingest -> predict -> decide -> alert
  SQS -> buffer, SNS -> SMS/push alerts
  OpenSearch -> geo/search index
  API Gatew `mbda -> REST API
  Amplify Hosting (+ CloudFront + Route 53) -> web dashboard
  Cognito -> auth for schools/admins
  CloudWatch -> logs/metrics

DATA MODEL
- reading: {station_id, lat, lon, pm25, pm10, no2, o3, aqi, ts}
- grid_cell: {cell_id, lat, lon, aqi_now, aqi_forecast[6], clean_index}
- school: {school_id, name, lat, lon, rules_ref}
- alert: {alert_id, target, kind, aqi, message, ts}
- route_request: {from, to, mode: fastest|cleanest}

CEDAR POLICY EXAMPLES (school rules)
- If predicted AQI > 200 -> deny outdoor_assembly, require indoor_activities.
- If predicted AQI > 300 -> close school / remote learning.
- If AQI > 150 -> allow sports with masks + time limit.

API ENDPOINTS (API Gateway + Lambda)
- GET /aqi?lat=&lon=            -> nowcast for a point
- GET /route?from=&to=&mode=   -> fastest vs cleanest with clean-index
- GET /school/{id}/today       -> today's alert card + allowed activities
- POST /subscribe              -> register a vulnerable user (phone/email, thresholds)

AGENT (Strands Agents SDK)
Give the agent tools: get_aqi, predict_aqi, find_cleanest_route, check_school_policy(Cedar),
send_alert(SNS). The agent takes a request like "Should ABC School hold assembly at 8am
tomorrow?" and returns a reasoned decision + action.

FRONTEND (Amplify Hosting)
- Leaflet/MapLibre map showing 500m AQI grid + fastest vs cleanest route.
- "Today at your school" card (allowed/blocked activities + AQI).
- Subscribe form for vulnerable individuals (Cognito auth).

DELIVERABLES
- Full source code, runnable locally (Build It) with mock data, no AWS account required.
- Infrastructure-as-code for the AWS deploy (prefer SAM/Lambda + DynamoDB + SNS + Amplify).
- README with run steps for BOTH paths (Build It + Ship It).
- Short demo script (60-90 seconds).

ACCEPTANCE CRITERIA
1. Runs locally with mock data in <2 commands.
2. Cleanest-route output differs from fastest and shows lower avg AQI.
3. Cedar rule correctly blocks an activity on a high-AQI day.
4. An alert is produced via SNS (or mocked locally) when threshold crosses.
5. Deployable to AWS using only the SHIP IT services above.
6. No AWS service outside the provided lists is used.

NON-GOALS
- No paid/non-listed AWS services. No advanced auth beyond Cognito. No production scaling.

BUILD ORDER
1. Local skeleton + mock data + nowcast + routing.
2. Strands agent + Cedar rules + local alerts (LocalStack for SNS/S3/DynamoDB).
3. Deploy: SAM/CDK -> Lambda + DynamoDB + SNS + API Gateway.
4. Amplify frontend + Cognito auth.
5. README + demo script.

STYLE
Clean, commented-at-a-reasonable-level code. Small files. Clear env config. Start by proposing
the file structure and tech choices, then implement step by step, running tests where possible.
