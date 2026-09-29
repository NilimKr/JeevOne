"""
pipeline_state.py
=================
Thread-safe in-memory state shared between the MQTT processing pipeline
and the API/dashboard.

The MQTT thread writes here; the API thread reads here.
No database access needed for the /api/latest endpoint.
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field
from typing import List, Optional

from app.ingestion.normalizer import SensorReading
from app.risk.fusion import FusedRisk


@dataclass
class PipelineState:
    """Current snapshot of the pipeline's latest output."""
    reading: Optional[SensorReading] = None
    fused_risk: Optional[FusedRisk] = None
    last_update: float = 0.0
    total_readings: int = 0
    total_rejected: int = 0

    def to_dict(self) -> dict:
        if self.reading is None:
            return {"status": "no_data"}
        return {
            "reading": self.reading.to_dict(),
            "risk": self.fused_risk.to_dict() if self.fused_risk else None,
            "last_update": self.last_update,
            "total_readings": self.total_readings,
            "total_rejected": self.total_rejected,
        }


class _StateStore:
    """Thread-safe wrapper for PipelineState."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._state = PipelineState()

    def update(self, reading: SensorReading, fused_risk: FusedRisk) -> None:
        with self._lock:
            self._state.reading = reading
            self._state.fused_risk = fused_risk
            self._state.last_update = time.time()
            self._state.total_readings += 1

    def increment_rejected(self) -> None:
        with self._lock:
            self._state.total_rejected += 1

    def snapshot(self) -> PipelineState:
        with self._lock:
            # Return a shallow copy (dataclass is mutable, but fields are immutable objects)
            return PipelineState(
                reading=self._state.reading,
                fused_risk=self._state.fused_risk,
                last_update=self._state.last_update,
                total_readings=self._state.total_readings,
                total_rejected=self._state.total_rejected,
            )


# Module-level singleton
state_store = _StateStore()
