# BreatheBuddy - 3-minute demo video script

> Judges see the **video**, not a live demo - so this records everything:
> what it does, who it's for, and where AWS fits. Local recording is fine
> (projects built locally and deployed projects are scored the same).

**Setup:** run `python run.py`, open http://localhost:8000. Have a second terminal
with `python run.py --demo` ready as a fallback proof. Screen-record with audio.

---

## 0:00 - 0:25 · Problem & who it's for

**On screen:** the map, slowly panning over the red hotspots.

> "On bad-air days, schools in Delhi still run outdoor assembly and sports. Kids,
> bike riders and asthma patients get no warning - apps only show one AQI number
> for the whole city. BreatheBuddy is for those people: **school admins deciding
> today's schedule, and vulnerable commuters deciding their route**. It tracks the
> air, warns the most exposed, and actually changes what happens on a bad day."

---

## 0:25 - 1:10 · What it does - hyperlocal nowcast + school card

**On screen:** hover the 500 m grid; click **Run 15-min cycle**; open
**ABC Public School** in the "Today at your school" card.

> "This is a 500-metre hyperlocal grid - not one city number, but street-level air,
> with a 6-hour nowcast per cell. Ingest runs every 15 minutes. Drag the **forecast
> slider** at the top of the map and the grid re-renders hour by hour - you can see
> the plume arrive. The map has real styles too - **Streets**, **Satellite**,
> **terrain** - switch any time; the dark style is cached so it even works offline.
> Notice the banner: a **stubble-burning spike** - the model adds a
> wind-driven smoke plume to every cell downwind, so the whole north-west lights up.
> Now look at ABC Public School: AQI 218, **poor**. The card tells the admin exactly
> what Cedar allows - outdoor assembly and PE are **blocked**, classes move indoors -
> and the **indoor air advisory** estimates indoor AQI and says keep windows shut and
> run purifiers. At AQI 300-plus it would close the school and switch to remote
> learning. This is **policy, not opinion**."

---

## 1:10 - 1:45 · Clean-air routing

**On screen:** click **Pick on map**, tap two points on the map to set start and end.

> "A student commuting to school wants the cleanest air, not just the fastest road.
> I just tap start and end right on the map. Blue dashed is the fastest route.
> Green is the cleanest - it's slightly longer, but cuts average pollution exposure
> by a few AQI points. The app shows both, with a clean-index score, so people can
> choose."

---

## 1:45 - 2:15 · Vulnerable alerts + the agent

**On screen:** submit the **Subscribe** form; point at the new alert; then
**Ask agent** with "Should ABC School hold outdoor assembly at 8am tomorrow?"

> "Riders and asthma patients subscribe with their own threshold and location.
> The moment local AQI crosses it, BreatheBuddy fires an alert - here to the local
> outbox, on AWS via SNS. And you can just ask it in plain language. The agent
> fetches the AQI, runs the Cedar school policy, and sends the alert - a reasoned
> decision with an action, in one call."

---

## 2:15 - 2:45 · Where AWS fits

**On screen:** quick cut to `src/breathebuddy/policies/school_rules.cedar`, then
`infra/template.yaml`, then the LocalStack/SAM commands.

> "BreatheBuddy is built on AWS open-source tools: the **Strands Agents SDK** for the
> agent and **Cedar** for the school rules -
> all running locally with **SAM CLI** and **LocalStack**, no AWS account needed.
> The same code ships to AWS free tier: **EventBridge** triggers **Lambda** ingest
> every 15 minutes into **S3** and **DynamoDB**; **Step Functions** orchestrates
> nowcast → decide → alert; **SNS** delivers alerts and **SQS** buffers them to an
> archive Lambda; **Cognito** guards the write endpoints; **CloudWatch** metrics and
> an alarm watch the pipeline; **API Gateway** serves the API and the dashboard ships
> on **CloudFront + S3 + Route 53** (or **Amplify Hosting**), with **SageMaker** as an
> optional drop-in for the nowcast model.
> Every AWS service I used is from the allowed Build It and Ship It lists."

---

## 2:45 - 3:00 · Impact & close

**On screen:** back to the map with the school card + routes.

> "One focused problem, solved: schools stop exposing kids to bad air, and exposed
> people get warned in time and a cleaner way to travel. BreatheBuddy -
> **Har saans, safe.**"

---

## Backup proof (if a judge asks "does it really run?")

- `python scripts/selfcheck.py` → **99/99** end-to-end checks (policy, API,
  template, stubble plume, Strands SDK, SQS buffer, JWT auth, OpenAQ adapter, no
  out-of-list AWS services).
- `python run.py --demo` → all five acceptance criteria printed.
- `python -m unittest discover -s tests -t .` → **52 tests pass** (CI runs these).

---

# Shot list - recording checklist

**Before you hit record (5 min)**
- [ ] Close noisy apps; set Windows display scaling to 100%.
- [ ] Open a terminal in `D:\Hackathon\BreatheBuddy`.
- [ ] Run `python run.py` → browser at http://localhost:8000 → **Ctrl+F5**.
- [ ] Run `python scripts/selfcheck.py` once in a second terminal so it's warmed up.
- [ ] Zoom browser to 100%; make the window 1280×720 or 1920×1080.
- [ ] Recorder ready (OBS Studio / Win+G / Loom). Mic tested.

**Recording sequence** (target 3:00)

| Time | Click / show | Say (from script) |
|------|--------------|-------------------|
| 0:00 | Map, pan slowly over red hotspots | Problem + who it's for |
| 0:25 | Click **Run 15-min cycle**, wait for map refresh | "every 15 minutes…" |
| 0:35 | Point at **stubble-burning banner** (top-right of map) | wind-driven plume raises downwind AQI |
| 0:45 | Click **ABC Public School**, read card + indoor advisory aloud | AQI 218, assembly/PE blocked, Cedar |
| 0:55 | Point at "Allowed" vs "Blocked by Cedar" chips | "policy, not opinion" |
| 1:10 | Click **Compare routes** | fastest vs cleanest, a few AQI saved |
| 1:25 | Point at blue dashed vs green line + stats box | clean-index |
| 1:45 | Fill **Subscribe** form → Submit → point at new alert | vulnerable alerts / SNS |
| 2:00 | Type question → **Ask agent** → read answer | agent decides + acts |
| 2:15 | Alt-tab: open `src/breathebuddy/policies/school_rules.cedar` | "AWS open-source: Cedar" |
| 2:25 | Alt-tab: open `infra/template.yaml` | Lambda/Step Functions/SNS/Amplify |
| 2:35 | Alt-tab: terminal `python scripts/selfcheck.py` (99/99) | "it really runs" |
| 2:45 | Back to map + school card | Impact + "Har saans, safe." |
| 3:00 | Stop recording | - |

**After recording**
- [ ] Watch it once end-to-end; make sure audio is clear and the 4 steps are visible.
- [ ] Export MP4, upload as the submission video.
- [ ] (If asked for a URL) `sam deploy` + Amplify - both optional, local is scored equally.

**Pro tips**
- If the map is slow on first paint, wait 2-3 s after load before narrating.
- If a number changes between takes, that's fine - the mock feed jitters every 15 min;
  just make sure the *blocked/allowed* logic matches what you say.
- Keep it under 3:00; trim dead time rather than speeding up.

