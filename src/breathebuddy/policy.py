"""Cedar policy evaluation for school bad-day rules.

Two execution paths, identical results:
  1. If the `cedarpy` package is installed -> the real Cedar engine runs the
     ``school_rules.cedar`` policy.
  2. Otherwise -> a small built-in evaluator parses the same .cedar file
     (permit/forbid + simple ``context.FIELD <op> VALUE`` conditions and
     Cedar's default-deny semantics).

Keeping the fallback means the demo works with zero installs, while still
using genuine Cedar on a machine that has cedarpy.
"""
from __future__ import annotations

import logging
import re
from typing import Any

from . import config

log = logging.getLogger("breathebuddy.policy")

ACTIVITIES = [
    "hold_outdoor_assembly",
    "hold_physical_education",
    "hold_classes",
    "indoor_activities",
    "close_school",
]

_RULE_RE = re.compile(
    r'(permit|forbid)\s*\(.*?action\s*==\s*Action::"([^"]+)".*?\)\s*'
    r'when\s*\{(.*?)\};', re.S)
_CLAUSE_RE = re.compile(
    r'context\.(\w+)\s*(<=|>=|==|<|>)\s*("?[\w.]+"?)')


def _as_number(v: str) -> float:
    return float(v)


def _parse_value(raw: str) -> Any:
    raw = raw.strip()
    if raw in ("true", "false"):
        return raw == "true"
    if raw.startswith('"') and raw.endswith('"'):
        return raw[1:-1]
    try:
        return float(raw)
    except ValueError:
        return raw


def _cmp(field_val: Any, op: str, target: Any) -> bool:
    if op == "==":
        return field_val == target
    try:
        a, b = float(field_val), float(target)
    except (TypeError, ValueError):
        return False
    if op == "<":
        return a < b
    if op == ">":
        return a > b
    if op == "<=":
        return a <= b
    if op == ">=":
        return a >= b
    return False


class BuiltinCedar:
    """Minimal evaluator for the subset of Cedar used by our school rules."""

    def __init__(self, policy_text: str) -> None:
        self.rules: list[dict] = []
        for effect, action, cond in _RULE_RE.findall(policy_text):
            clauses = [(f, op, _parse_value(v)) for f, op, v in _CLAUSE_RE.findall(cond)]
            self.rules.append({"effect": effect, "action": action, "clauses": clauses})

    def _clause_true(self, clause, ctx: dict) -> bool:
        field_, op, target = clause
        return _cmp(ctx.get(field_), op, target)

    def is_authorized(self, action: str, ctx: dict) -> dict:
        relevant = [r for r in self.rules if r["action"] == action]
        permits = [r for r in relevant if r["effect"] == "permit"]
        forbids = [r for r in relevant if r["effect"] == "forbid"]
        permit_ok = any(all(self._clause_true(c, ctx) for c in r["clauses"]) for r in permits)
        forbid_hit = any(all(self._clause_true(c, ctx) for c in r["clauses"]) for r in forbids)
        allowed = permit_ok and not forbid_hit
        if forbid_hit:
            reason = "A forbid rule matched (default-deny overrides)."
        elif not permit_ok:
            reason = "No permit rule matched (Cedar default-deny)."
        else:
            reason = "A permit rule matched and no forbid rule applied."
        return {"allowed": allowed, "reason": reason, "engine": "builtin-cedar"}


def _load_policy(policy_ref: str) -> tuple[str, dict]:
    path = config.POLICY_DIR / policy_ref
    if not path.exists():
        path = config.POLICY_DIR / "school_rules.cedar"
    return path.read_text("utf-8"), {}


def _cedarpy():
    try:
        import cedarpy  # type: ignore
        return cedarpy
    except Exception:
        return None


def load_engine(policy_ref: str = "school_rules.cedar"):
    text, _ = _load_policy(policy_ref)
    return BuiltinCedar(text)


def _normalize_context(context: dict) -> dict:
    """Cedar compares integer policy literals against context numbers; a float
    context value triggers a Long-vs-Decimal type error and default-deny in the
    real engine. AQI and time limits are whole numbers, so coerce floats to int
    for identical results in both engines."""
    out = {}
    for k, v in context.items():
        if isinstance(v, bool):
            out[k] = v
        elif isinstance(v, float):
            out[k] = int(round(v))
        else:
            out[k] = v
    return out


def evaluate(activity: str, context: dict, policy_ref: str = "school_rules.cedar") -> dict:
    """Evaluate one activity against the Cedar policy."""
    context = _normalize_context(context)
    cp = _cedarpy()
    if cp is not None:
        try:
            text, _ = _load_policy(policy_ref)
            request = {
                "principal": {"type": "User", "id": "school_staff"},
                "action": {"type": "Action", "id": activity},
                "resource": {"type": "School", "id": "school"},
                "context": context,
            }
            result = cp.is_authorized(request, policies=text, entities=[])
            allowed = bool(getattr(result, "allowed", False))
            return {"activity": activity, "allowed": allowed, "reason": "Cedar (cedarpy)",
                    "engine": "cedar"}
        except Exception as exc:  # pragma: no cover - fall back on any engine error
            log.warning("cedarpy failed, using builtin: %s", exc)
    engine = load_engine(policy_ref)
    res = engine.is_authorized(activity, context)
    res["activity"] = activity
    return res


def decide_activities(context: dict, policy_ref: str = "school_rules.cedar") -> dict:
    results = {a: evaluate(a, context, policy_ref) for a in ACTIVITIES}
    allowed = [a for a, r in results.items() if r["allowed"]]
    blocked = [a for a, r in results.items() if not r["allowed"]]
    return {"allowed": allowed, "blocked": blocked, "decisions": results}
