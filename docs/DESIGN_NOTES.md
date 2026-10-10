# Design notes

These are the decisions that are not obvious from the code, and the trade-offs
behind them. Written down because "why didn't you just use a library?" is the
first question a reviewer asks.

---

## 1. Stdlib-only by default

The default path (`python run.py`) has **zero third-party dependencies**. That is
a product decision, not laziness:

- A judge can clone the repo and see it work in one command, on any machine, with
  no network and no build step.
- A demo that needs `pip install` first is a demo that can fail in front of people.

So the real dependency-free model lives in `nowcast.py`, the HTTP server is
`http.server`, and the frontend has no bundler. Optional packages are treated as
*upgrades*, never requirements.

## 2. Every optional dependency degrades, never disables

`cedarpy`, the Strands Agents SDK and `boto3` each have a fallback:

| Upgrade | Used when | Fallback |
|---------|-----------|----------|
| `cedarpy` | installed | `policy.BuiltinCedar` (same .cedar file) |
| Strands SDK + Bedrock | `BB_USE_STRANDS=true` + creds | `agent.SimpleAgent` (same tools) |
| `boto3` | `BB_USE_AWS=true` | no-op bridge; local outbox + buffer |

The rule is: **a missing optional package changes which engine answers, never
whether the app works.** `agent.ask()` and `policy.evaluate()` return the same
shape either way, so the API and the tests don't branch.

## 3. A built-in Cedar evaluator

Re-implementing part of a policy language sounds risky, and normally it is. Two
things make it acceptable here:

- It parses the **same** `policies/school_rules.cedar` file the real engine runs,
  so there is one source of truth, not two copies of the rules.
- It only supports the subset we actually use: `permit`/`forbid`, one
  `action == Action::"..."`, and `context.FIELD <op> value` conditions with Cedar's
  default-deny semantics.

A test asserts `cedarpy` and the built-in agree on the sample decisions, which is
the check that keeps the two paths honest.

## 4. The float-vs-integer Cedar gotcha

This one cost real debugging time. Cedar compares the integer literals in the
policy (`predicted_aqi <= 300`) against context values. If you pass an AQI as a
Python float, the real engine sees a `Decimal` against a `Long` and **default-denies
the whole request** - every school silently closes. The fix lives in
`policy._normalize_context()`: AQI and time limits are whole numbers, so floats are
coerced to int before evaluation. There is a regression test for it.

## 5. Explainable model over a trained one

For this problem an IDW blend plus a couple of physical modifiers is genuinely
better than a black-box model:

- There is no labelled 500 m training set to learn from.
- A reviewer can follow every number from station → cell → forecast.
- It runs in milliseconds, so the UI stays interactive.

The interface is kept identical to a hosted SageMaker endpoint so the model can be
swapped later without touching the API. See `nowcast.py`.

## 6. Deterministic bundled fallback

The live OpenAQ v3 feed is the default. When it is unreachable (offline, or a
free key is not set yet), the bundled feed perturbs each station's AQI using a
hash of `station_id + 15-minute-bucket` (`ingest._jitter`), not `random()`. Two
consequences, both wanted:

- Repeated runs in the same bucket give the same numbers, so **tests are stable**.
- Values still move between cycles, so the dashboard visibly *does something* when
  you click "Run 15-min cycle".

Every ingest records which feed actually produced the readings
(`ingest.effective_source`), and the header badge shows LIVE vs PREVIEW rather
than pretending.

## 7. Alert de-duplication

`alerts.publish()` will not re-send the same `(target, kind)` alert within
`BB_ALERT_COOLDOWN_MIN` (default 60). Without it, a 15-minute pipeline would spam a
school every cycle about the same bad day. The cooldown is keyed on target+kind, not
just target, so a school can still receive a *different* alert (e.g. assembly → PE
cancelled) inside the window.

## 8. Lambda and local run the same code

`infra/handler/app.py` imports the `breathebuddy` package rather than reimplementing
anything. The only differences are the ingredients: AWS instead of stdlib serving,
Cognito instead of presence-auth.

One small parity trap: API Gateway hands you query parameters as either a string or
a list of strings depending on how the request was made. The Lambda handler
normalises that (`{k: v[0] if isinstance(v, list) else v}`) so a query succeeds
identically in both environments.

## 9. Rate limiting that is deliberately small

`ratelimit.RateLimiter` is a fixed window, one counter per client, in memory. It is
not a distributed limiter and does not pretend to be. It exists to blunt accidental
loops and abusive scripts; **API Gateway usage plans provide real account-level
throttling in production.** Keeping it tiny also keeps the write path free of any
external dependency.

## 10. Offline map tiles with a live fallback

The map must work without internet, so tiles are vendored under
`frontend/vendor/tiles/`. But a vendored set is finite, and the original provider
(CARTO) started returning "API key required" placeholder PNGs for some tiles -
which got cached. Two safeguards came out of that:

- `scripts/fetch_tiles.py` validates each tile's JPEG magic bytes and size, so a
  placeholder can never be written.
- `frontend/app.js` falls back to the live Esri tile server when a local tile is
  missing.

`scripts/selfcheck.py` checks that the cached tiles are real JPEGs, so this
regression cannot come back silently.

## 11. Dependency-free API docs

`openapi.py` hand-writes the OpenAPI 3.0 spec and a plain HTML `/docs` page instead
of pulling in Swagger UI. It keeps the "no installs" promise and the page still
renders offline. The spec is also imported directly by the Lambda handler, so
`/openapi.json` is identical in both environments.

## 12. Two layers of tests

- `tests/` - fast `unittest` cases for the logic (nowcast, routing, policy, alerts,
  ingest, auth, agent, the extra API modules). These run in CI on every push.
- `scripts/selfcheck.py` - a slower end-to-end smoke test that actually boots the
  HTTP server, hits every endpoint, imports the Lambda handler, and checks the
  vendored assets and project files. It is the "does the whole thing really work"
  gate a human would run before recording a demo.

Keeping both is intentional: unit tests catch logic regressions cheaply; the
selfcheck catches integration and packaging problems that unit tests miss.
