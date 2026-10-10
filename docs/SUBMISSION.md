# BreatheBuddy - submission pack (AWS Environmental Hacks)

Paste-ready answers and links for the submission form. Two placeholders remain
(video URL and published blog URL); everything else is filled.

---

## Basics

| Field | Value |
|-------|-------|
| **Project title** | BreatheBuddy |
| **Tagline** | Har saans, safe. Hyperlocal air quality that *acts*. |
| **Track** | **Air** |
| **Team** | codeN4PTDY (Dev X) - Kartikey Kesarwani (lead), Krishna Gupta, Varun Chakraborty, @antidoe |
| **Repo** | https://github.com/Kartikey-Kesarwani-2005/BreatheBuddy |
| **Demo video (3 min)** | TODO_add_video_url |
| **Blog (AWS Builder Center)** | TODO_add_blog_url  *(draft: `docs/BLOG.md`)* |
| **Deployed URL (optional)** | Local only - run `python run.py` (no AWS account needed) |
| **License** | MIT |

## Short description (<= 50 words)

BreatheBuddy predicts street-level AQI on a 500 m grid, warns the most exposed people
(school kids, riders, asthma patients) before thresholds are crossed, enforces school
bad-day rules with Cedar, and routes commuters along the *cleanest* path, not just the
fastest.

## Long description

BreatheBuddy tackles a specific problem inside Delhi's air-quality crisis: **school
safety on bad-air days**, plus the riders and asthma patients around them.

It ingests AQI readings every 15 minutes (bundled feed, or a **live OpenAQ v3** adapter
with automatic fallback) and builds a **~500 m hyperlocal nowcast** for the next 6
hours. A wind-driven **stubble-burning plume** is added to every cell downwind of a fire
event, so the dashboard shows *why* the air is bad and where it's heading. For commuters
it returns the **fastest** and the **cleanest** route with a clean-index score, and users
can tap two points on the map or use "Near me".

The decision layer is the heart of it: school schedule rules are written as **Cedar
policies**, so the answer is *policy, not opinion*. At AQI 153 outdoor assembly is
blocked but classes continue; at 300+ the school closes and moves remote. A **Strands
Agents SDK** agent answers natural-language questions ("Should Mater Dei School hold outdoor
assembly at 8am tomorrow?") by calling tools, running the Cedar policy and sending the
alert.

It runs **locally with zero dependencies** (`python run.py`, stdlib only) and ships to
AWS with a single SAM template: EventBridge -> Lambda ingest -> S3 + DynamoDB, Step
Functions orchestration, SNS alerts with an SQS buffer, Cognito-guarded write endpoints,
CloudWatch metrics/alarm, and CloudFront + S3 + Route 53 hosting.

## How AWS is used (eligibility)

- **AWS open source tools (Build It):** Strands Agents SDK, Cedar, SAM CLI,
  LocalStack.
- **Deployed on AWS free tier (Ship It):** Lambda, API Gateway, Step Functions,
  EventBridge, S3, DynamoDB, SNS, SQS, CloudWatch, Cognito, CloudFront, Route 53, and
  optional SageMaker.
- No AWS service outside the official Build It / Ship It lists is referenced.

## What fought back (blog-ready highlights)

- The Strands SDK's real API differed from the assumed one (`Agent(model=..., tools=...)`);
  we rewired it and kept a deterministic fallback plus a test that asserts a real `Agent`
  is built.
- Cedar rejected float context; fixed with a normalise step and a regression test.
- All offline map tiles were the *same* "API key required" placeholder (CARTO); switched
  to keyless Esri tiles with validation so placeholders can't be cached.
- API Gateway query strings arrive as list *or* string; normalised for exact local/Lambda
  parity.

## Verification (judges can reproduce)

```bash
python run.py                 # dashboard at http://localhost:8000 (no installs)
python scripts/selfcheck.py   # 100/100 end-to-end checks
python -m unittest discover -s tests -t .   # 52 unit tests
```

Docs for reviewers: [`ARCHITECTURE.md`](ARCHITECTURE.md) (code map),
[`DESIGN_NOTES.md`](DESIGN_NOTES.md) (why), [`DEPLOY.md`](DEPLOY.md) (deploy it).

## Checklist

- [ ] Repo is public and includes this file.
- [ ] Student status verified on **AWS Builder Center**.
- [ ] Blog published on **AWS Builder Center** and linked above.
- [ ] 3-minute video recorded and linked above.
- [ ] All `TODO_` placeholders replaced.
