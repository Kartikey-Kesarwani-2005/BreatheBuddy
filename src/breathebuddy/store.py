"""Shared in-memory state for the whole app.

Everything the pipeline produces hangs off this one object. On a laptop it stays
purely in memory, plus a small JSON outbox so alerts survive a restart. When
``USE_AWS`` is on, the same method calls also mirror out to S3 and DynamoDB
through the bridge -- callers don't change either way.
"""
from __future__ import annotations

import json
import threading
import time
from typing import Any

from . import config
from .models import Alert, Reading, School


class Store:
    def __init__(self) -> None:
        self._lock = threading.RLock()
        self.readings: dict[str, Reading] = {}
        self.schools: dict[str, School] = {}
        self.grid: dict[str, Any] = {}
        self.subscribers: dict[str, dict[str, Any]] = {}
        self.alerts: list[Alert] = []
        self.buffer: list[dict[str, Any]] = []      # SQS-style delivery buffer
        self._last_alert: dict[str, float] = {}  # (target:kind) -> epoch seconds
        self.aws = None  # lazily attached AWS bridge

    # -- bootstrap --------------------------------------------------------
    def load_mock(self) -> Store:
        stations = json.loads((config.DATA_DIR / "stations.json").read_text("utf-8"))
        for r in stations["stations"]:
            reading = Reading.from_dict(r)
            self.readings[reading.station_id] = reading
        schools = json.loads((config.DATA_DIR / "schools.json").read_text("utf-8"))
        for s in schools["schools"]:
            school = School.from_dict(s)
            self.schools[school.school_id] = school
        return self

    def attach_aws(self, bridge) -> None:
        self.aws = bridge

    # -- readings ---------------------------------------------------------
    def put_readings(self, readings: list[Reading]) -> int:
        with self._lock:
            for r in readings:
                self.readings[r.station_id] = r
            if self.aws:
                self.aws.put_readings(readings)
            return len(readings)

    def all_readings(self) -> list[Reading]:
        with self._lock:
            return list(self.readings.values())

    # -- schools ----------------------------------------------------------
    def get_school(self, school_id: str) -> School | None:
        return self.schools.get(school_id)

    # -- grid -------------------------------------------------------------
    def set_grid(self, cells: dict[str, Any]) -> None:
        with self._lock:
            self.grid = cells
            if self.aws:
                self.aws.index_grid(list(cells.values()))

    def get_grid(self) -> dict[str, Any]:
        return self.grid

    # -- subscribers ------------------------------------------------------
    def add_subscriber(self, sub: dict[str, Any]) -> dict[str, Any]:
        with self._lock:
            self.subscribers[sub["subscriber_id"]] = sub
            if self.aws:
                self.aws.put_subscriber(sub)
            return sub

    def all_subscribers(self) -> list[dict[str, Any]]:
        with self._lock:
            return list(self.subscribers.values())

    # -- alerts -----------------------------------------------------------
    def add_alert(self, alert: Alert) -> Alert:
        with self._lock:
            self.alerts.append(alert)
            self._append_outbox(alert)
            if self.aws:
                self.aws.put_alert(alert)
            return alert

    def _append_outbox(self, alert: Alert) -> None:
        try:
            config.OUTBOX.parent.mkdir(parents=True, exist_ok=True)
            existing: list[dict] = []
            if config.OUTBOX.exists():
                existing = json.loads(config.OUTBOX.read_text("utf-8") or "[]")
            existing.append(alert.to_dict())
            config.OUTBOX.write_text(json.dumps(existing[-200:], indent=2), "utf-8")
        except OSError:
            pass

    def recent_alerts(self, limit: int = 50) -> list[Alert]:
        with self._lock:
            return self.alerts[-limit:][::-1]

    # -- SQS-style delivery buffer ----------------------------------------
    def buffer_message(self, message: dict[str, Any]) -> dict[str, Any]:
        """Append a delivery to the buffer and mirror it to SQS when on AWS."""
        with self._lock:
            self.buffer.append(message)
            self.buffer = self.buffer[-500:]
            if self.aws:
                return self.aws.send_to_queue(message)
            return {"queued": False, "channel": "local-buffer"}

    def drain_buffer(self, limit: int = 50) -> list[dict[str, Any]]:
        """Pop up to ``limit`` buffered messages (used by the buffer Lambda)."""
        with self._lock:
            out, self.buffer = self.buffer[:limit], self.buffer[limit:]
            return out

    # -- alert throttling -------------------------------------------------
    def alert_age_s(self, key: str) -> float:
        """Seconds since the last alert for ``key`` (large if never sent)."""
        with self._lock:
            last = self._last_alert.get(key)
        return float("inf") if last is None else time.time() - last

    def mark_alert(self, key: str) -> None:
        with self._lock:
            self._last_alert[key] = time.time()

    def reset_alert_state(self) -> None:
        with self._lock:
            self._last_alert.clear()


STORE = Store()
