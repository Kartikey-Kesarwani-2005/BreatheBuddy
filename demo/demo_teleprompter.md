# BreatheBuddy — Teleprompter Script (narration only)

> For recording: paste into a notepad/teleprompter with a large font, or have a
> second monitor showing this file. Pauses are marked `…`. Say what you see —
> numbers drift every 15 min, so read the *live* AQI on screen.

---

## 0:00 · Problem

"On bad-air days, schools in Delhi still run outdoor assembly and sports.

Kids, bike riders and asthma patients get no warning —
apps just show one AQI number for the whole city.

BreatheBuddy is for those people:
school admins deciding today's schedule,
and vulnerable commuters deciding their route.

It tracks the air, warns the most exposed,
and actually changes what happens on a bad day. …"

---

## 0:25 · Hyperlocal nowcast

"This is a 500-metre hyperlocal grid —
not one city number, but street-level air,
with a six-hour forecast for every cell.

Ingest runs every fifteen minutes.

Drag the forecast slider —
the grid re-renders hour by hour,
you can watch the plume arrive.

Look at the banner: a stubble-burning spike.
The model adds a wind-driven smoke plume
to every cell downwind,
so the whole north-west lights up. …"

---

## 0:45 · School card

"Now let's look at a school — Mater Dei School.

AQI [read live number on screen] … poor.

The card tells the admin exactly what the policy allows:
outdoor assembly and PE blocked —
classes move indoors.

It even estimates the indoor air
and says keep windows shut, run purifiers.

At AQI three hundred-plus,
it would close the school and switch to remote learning.

This is policy — not opinion. …"

---

## 1:10 · Clean-air routing

"A student commuting to school
wants the cleanest air, not just the fastest road.

Tap your start on the map, tap the destination —
done.

Blue dashed is the fastest route.
Green is the cleanest:
slightly longer, but it cuts pollution exposure.

The app shows both with a clean-index score,
so people can choose. …"

---

## 1:45 · Alerts + agent

"Riders and asthma patients subscribe
with their own threshold and location.

The moment local AQI crosses it,
BreatheBuddy fires an alert —
here to the outbox, on AWS via SNS.

And you can just ask it in plain language. …

'Should Mater Dei School hold outdoor assembly at 8am tomorrow?'

[Read the agent's answer aloud.]

It fetched the AQI, ran the school policy,
and sent the alert —
a reasoned decision with an action, in one call. …"

---

## 2:15 · Where AWS fits

"BreatheBuddy is built on AWS open-source tools:
the Strands Agents SDK for the agent,
and Cedar for the school rules —
running locally with SAM CLI and LocalStack,
no AWS account needed.

The same code ships to the AWS free tier:

EventBridge triggers Lambda ingest every fifteen minutes
into S3 and DynamoDB.

Step Functions orchestrates:
nowcast, decide, alert.

SNS delivers alerts,
SQS buffers them to an archive Lambda.

Cognito guards the write endpoints.

API Gateway serves the API,
and the dashboard runs on CloudFront and S3,
or Amplify Hosting.

[Optional] Every AWS service we used
is from the official Build It and Ship It lists. …"

---

## 2:45 · Impact & close

"One focused problem, solved:

schools stop exposing kids to bad air,
and exposed people get warned in time
and a cleaner way to travel.

BreatheBuddy —
Har saans, safe."