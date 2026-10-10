"""Plain dataclasses for the BreatheBuddy data model.

Kept dependency-free (stdlib only) so the project runs without pip installs.
Each model knows how to serialise itself to/from the API / storage shape.
"""
from __future__ import annotations

import uuid
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from typing import Any


def now_iso() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat()


def _clean(d: dict[str, Any]) -> dict[str, Any]:
    return {k: v for k, v in d.items() if v is not None}


@dataclass
class Reading:
    """A single station observation (OpenAQ/CPCB-style)."""
    station_id: str
    lat: float
    lon: float
    aqi: float
    pm25: float = 0.0
    pm10: float = 0.0
    no2: float = 0.0
    o3: float = 0.0
    wind_speed: float = 0.0      # m/s, optional weather enrichment
    wind_dir: float = 0.0        # degrees, optional
    traffic: float = 0.0         # 0..1 congestion factor, optional
    ts: str = field(default_factory=now_iso)

    def to_dict(self) -> dict[str, Any]:
        return _clean(asdict(self))

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> Reading:
        return cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})


@dataclass
class GridCell:
    """A ~500 m cell of the hyperlocal nowcast grid."""
    cell_id: str
    lat: float
    lon: float
    aqi_now: float
    aqi_forecast: list[float] = field(default_factory=list)
    clean_index: float = 0.0
    plume: float = 0.0          # stubble-burning contribution to aqi_now
    row: int = 0
    col: int = 0

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class School:
    school_id: str
    name: str
    lat: float
    lon: float
    rules_ref: str = "school_rules.cedar"
    students: int = 0
    contact_email: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return _clean(asdict(self))

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> School:
        return cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})


@dataclass
class Alert:
    alert_id: str
    target: str
    kind: str
    aqi: float
    message: str
    ts: str = field(default_factory=now_iso)
    channel: str = "sns"

    @classmethod
    def create(cls, target: str, kind: str, aqi: float, message: str,
               channel: str = "sns") -> Alert:
        return cls(alert_id="alr_" + uuid.uuid4().hex[:10], target=target, kind=kind,
                   aqi=aqi, message=message, channel=channel)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class RouteResult:
    mode: str
    distance_m: float
    duration_min: float
    avg_aqi: float
    max_aqi: float
    clean_index: float
    geometry: list[tuple[float, float]] = field(default_factory=list)
    cells: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["geometry"] = [[lat, lon] for lat, lon in self.geometry]
        return d
