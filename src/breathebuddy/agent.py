"""The BreatheBuddy agent.

Uses the Strands Agents SDK when it is installed *and* a model is available
(Bedrock on AWS, or a local model). Otherwise it falls back to a deterministic,
rule-based responder that calls exactly the same tools, so the agent still works
with no cloud credentials.

Tools exposed to the agent:
    get_aqi, predict_aqi, find_cleanest_route, check_school_policy, send_alert
"""
from __future__ import annotations

import logging

from . import alerts as alerting
from . import config
from .models import Alert
from .nowcast import nowcast_point
from .policy import evaluate
from .routing import find_routes
from .service import aqi_category, bootstrap
from .store import STORE

log = logging.getLogger("breathebuddy.agent")

# --------------------------------------------------------------------------
# Tool implementations (plain functions -> easy to test without an LLM)
# --------------------------------------------------------------------------
def get_aqi(lat: float, lon: float) -> dict:
    """Return the current AQI and 6-hour forecast for a coordinate."""
    bootstrap()
    nc = nowcast_point(lat, lon, STORE)
    nc["category"] = aqi_category(nc["aqi_now"])
    return nc


def predict_aqi(lat: float, lon: float, hours: int = 6) -> dict:
    """Return the AQI forecast for the next `hours` hours at a coordinate."""
    bootstrap()
    nc = nowcast_point(lat, lon, STORE)
    f = nc["aqi_forecast"][:hours]
    return {"lat": lat, "lon": lon, "hours": hours, "forecast": f,
            "peak": max(f) if f else nc["aqi_now"]}


def find_cleanest_route(from_lat: float, from_lon: float,
                        to_lat: float, to_lon: float) -> dict:
    """Compare fastest vs cleanest route; returns the cleaner option summary."""
    bootstrap()
    res = find_routes((from_lat, from_lon), (to_lat, to_lon), STORE)
    return {
        "winner": res["winner"],
        "aqi_saved": res["aqi_saved_on_cleanest"],
        "fastest": {k: res["fastest"][k] for k in ("distance_m", "avg_aqi", "clean_index")},
        "cleanest": {k: res["cleanest"][k] for k in ("distance_m", "avg_aqi", "clean_index")},
    }


def check_school_policy(school_id: str, activity: str, predicted_aqi: float,
                        masks_available: bool = True, time_limit_minutes: int = 45) -> dict:
    """Evaluate a school activity against the Cedar bad-day policy."""
    school = STORE.get_school(school_id)
    ref = school.rules_ref if school else "school_rules.cedar"
    res = evaluate(activity, {
        "predicted_aqi": predicted_aqi,
        "masks_available": masks_available,
        "time_limit_minutes": time_limit_minutes,
    }, ref)
    res["school_id"] = school_id
    return res


def send_alert(target: str, kind: str, aqi: float, message: str) -> dict:
    """Send an alert via SNS (or the mock outbox) and return delivery info."""
    bootstrap()
    alert = Alert.create(target=target, kind=kind, aqi=aqi, message=message)
    return alerting.publish(alert, STORE)


TOOL_FUNCTIONS = [get_aqi, predict_aqi, find_cleanest_route,
                  check_school_policy, send_alert]


def _school_from_text(text: str):
    for s in STORE.schools.values():
        if s.school_id.lower() in text.lower() or s.name.lower() in text.lower():
            return s
    return None


def _activity_from_text(text: str) -> str | None:
    t = text.lower()
    if "assembly" in t:
        return "hold_outdoor_assembly"
    if "pe" in t or "sport" in t or "physical" in t or "games" in t:
        return "hold_physical_education"
    if "close" in t or "remote" in t:
        return "close_school"
    if "class" in t:
        return "hold_classes"
    return None


# --------------------------------------------------------------------------
# Deterministic fallback responder
# --------------------------------------------------------------------------
class SimpleAgent:
    """Rule-based agent calling the same tools. Deterministic + offline."""

    engine = "simple"

    def ask(self, question: str) -> dict:
        bootstrap()
        q = question.lower()
        steps: list[str] = []
        school = _school_from_text(question)

        if school and ("should" in q or "assembly" in q or "sport" in q
                       or "pe" in q or "close" in q):
            activity = _activity_from_text(question) or "hold_outdoor_assembly"
            aqi_info = get_aqi(school.lat, school.lon)
            predicted = aqi_info["aqi_forecast"][-1] if "tomorrow" in q else aqi_info["aqi_now"]
            steps.append(f"Fetched AQI at {school.name}: {aqi_info['aqi_now']} "
                         f"(6h peak {max(aqi_info['aqi_forecast'])}).")
            steps.append(f"Using predicted AQI {predicted} for the requested time.")
            decision = check_school_policy(school.school_id, activity, predicted)
            steps.append(f"Cedar: {activity} -> "
                         f"{'ALLOWED' if decision['allowed'] else 'DENIED'} "
                         f"({decision['reason']})")
            action = "No alert needed."
            if not decision["allowed"]:
                msg = (f"{school.name}: {activity} blocked. Predicted AQI {predicted}. "
                       f"Switch to indoor activities.")
                send_alert(f"school:{school.school_id}", "agent_decision", predicted, msg)
                action = "Alert sent to school admin via SNS."
            answer = (f"{'Yes' if decision['allowed'] else 'No'}: {activity.replace('_', ' ')} "
                      f"at {school.name} is {'allowed' if decision['allowed'] else 'not allowed'} "
                      f"(predicted AQI {predicted}). {action}")
            return {"answer": answer, "steps": steps, "decision": decision,
                    "engine": self.engine}

        if "route" in q or ("clean" in q and "fast" in q):
            steps.append("Compare fastest vs cleanest route requested.")
            return {"answer": "Ask with coordinates, or use the dashboard's route tool.",
                    "steps": steps, "engine": self.engine}

        # default: report AQI at city centre
        info = get_aqi(28.6139, 77.2090)
        return {"answer": f"Current AQI near city centre: "
                          f"{info['aqi_now']} ({info['category']}). "
                          f"6h forecast {info['aqi_forecast']}.",
                "steps": ["Reported city-centre AQI."], "engine": self.engine}


# --------------------------------------------------------------------------
# Strands path (optional): real Strands Agents SDK + Amazon Bedrock model
# --------------------------------------------------------------------------
SYSTEM_PROMPT = (
    "You are BreatheBuddy, a hyperlocal air-quality agent for a city. Use the "
    "available tools to check AQI, forecast, compare cleanest vs fastest routes, "
    "and enforce school Cedar policies. When a policy denies an outdoor activity, "
    "call send_alert. Always answer with a clear decision and the action taken."
)

_MODEL = None       # cached BedrockModel (holds the boto client)
_TOOLS = None       # cached Strands-wrapped tool list


def _strands_tools():
    global _TOOLS
    if _TOOLS is None:
        from strands import tool as strands_tool
        _TOOLS = [strands_tool(f) for f in TOOL_FUNCTIONS]
    return _TOOLS


def _bedrock_model():
    """Build (and cache) the Bedrock model, configured from the environment."""
    global _MODEL
    if _MODEL is not None:
        return _MODEL
    from strands.models import BedrockModel
    kwargs: dict = {"region_name": config.AWS_REGION}
    if config.AWS_ENDPOINT:
        kwargs["endpoint_url"] = config.AWS_ENDPOINT
    if config.BEDROCK_API_KEY:
        kwargs["api_key"] = config.BEDROCK_API_KEY
    if config.STRANDS_MODEL_ID:
        kwargs["model_id"] = config.STRANDS_MODEL_ID
    _MODEL = BedrockModel(**kwargs)
    log.info("Strands BedrockModel ready (model_id=%s, region=%s)",
             _MODEL.config.get("model_id"), config.AWS_REGION)
    return _MODEL


def build_strands_agent():
    """Return a Strands ``Agent`` wired with our tools, or None if unavailable.

    Uses the Strands Agents SDK directly: ``Agent(model=BedrockModel(...),
    tools=[...], system_prompt=...)``.
    """
    try:
        from strands import Agent
        return Agent(model=_bedrock_model(), tools=_strands_tools(),
                     system_prompt=SYSTEM_PROMPT)
    except Exception as exc:  # pragma: no cover - Strands/model optional
        log.info("Strands agent unavailable (%s); using SimpleAgent.", exc)
        return None


def _strands_steps(result) -> list[str]:
    """Extract tool-call steps from a Strands AgentResult for the UI."""
    steps = []
    try:
        for item in (result.message or {}).get("content", []):
            if isinstance(item, dict) and "toolUse" in item:
                tu = item["toolUse"]
                steps.append(f"Called {tu.get('name')}({tu.get('input')})")
    except Exception:  # pragma: no cover
        pass
    return steps


def get_agent(prefer_strands: bool | None = None):
    """Return a Strands Agent when enabled/available, else the SimpleAgent."""
    if prefer_strands is None:
        prefer_strands = config.USE_STRANDS
    if prefer_strands:
        agent = build_strands_agent()
        if agent is not None:
            return agent
    return SimpleAgent()


def ask(question: str, prefer_strands: bool | None = None) -> dict:
    if prefer_strands is None:
        prefer_strands = config.USE_STRANDS
    if prefer_strands:
        agent = build_strands_agent()
        if agent is not None:
            try:
                result = agent(question)
                text = str(result).strip()
                return {"answer": text or "(no answer)", "steps": _strands_steps(result),
                        "engine": "strands"}
            except Exception as exc:  # pragma: no cover - depends on model/creds
                log.warning("Strands invocation failed (%s); using SimpleAgent.", exc)
    return SimpleAgent().ask(question)
