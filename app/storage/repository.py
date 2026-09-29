"""
storage/repository.py
=====================
All database read/write operations live here.
No SQL scattered through application logic.
"""

from __future__ import annotations

import json
import logging
from typing import List, Optional

from app.ingestion.normalizer import SensorReading
from app.storage.database import get_session
from app.storage.models import RiskStateRecord, SensorReadingRecord

_log = logging.getLogger(__name__)


# ── Sensor readings ─────────────────────────────────────────────────────────

def insert_reading(reading: SensorReading) -> None:
    """Persist one validated+normalised sensor reading."""
    record = SensorReadingRecord(
        timestamp_epoch=reading.timestamp_epoch,
        timestamp_iso=reading.timestamp.isoformat(),
        device_id=reading.device_id,
        heart_rate=reading.heart_rate,
        spo2=reading.spo2,
        body_temperature=reading.body_temperature,
        room_temperature=reading.room_temperature,
        humidity=reading.humidity,
    )
    _execute_write(record)


def get_latest_reading() -> Optional[SensorReadingRecord]:
    """Return the most recent sensor reading, or None."""
    with get_session() as session:
        return (
            session.query(SensorReadingRecord)
            .order_by(SensorReadingRecord.timestamp_epoch.desc())
            .first()
        )


def get_recent_readings(limit: int = 60) -> List[SensorReadingRecord]:
    """Return the `limit` most recent readings, newest first."""
    with get_session() as session:
        return (
            session.query(SensorReadingRecord)
            .order_by(SensorReadingRecord.timestamp_epoch.desc())
            .limit(limit)
            .all()
        )


# ── Risk states ─────────────────────────────────────────────────────────────

def insert_risk_state(
    reading: SensorReading,
    heat_risk: str,
    vital_risk: str,
    respiratory_risk: str,
    overall_status: str,
    recommendation: str,
    reasons: list,
) -> None:
    """Persist a processed risk-state snapshot."""
    record = RiskStateRecord(
        timestamp_epoch=reading.timestamp_epoch,
        timestamp_iso=reading.timestamp.isoformat(),
        heat_risk=heat_risk,
        vital_risk=vital_risk,
        respiratory_risk=respiratory_risk,
        overall_status=overall_status,
        recommendation=recommendation,
        reasons=json.dumps(reasons),
    )
    _execute_write(record)


def get_latest_risk_state() -> Optional[RiskStateRecord]:
    """Return the most recent risk-state record, or None."""
    with get_session() as session:
        return (
            session.query(RiskStateRecord)
            .order_by(RiskStateRecord.timestamp_epoch.desc())
            .first()
        )


def get_recent_risk_states(limit: int = 60) -> List[RiskStateRecord]:
    """Return the `limit` most recent risk states, newest first."""
    with get_session() as session:
        return (
            session.query(RiskStateRecord)
            .order_by(RiskStateRecord.timestamp_epoch.desc())
            .limit(limit)
            .all()
        )


# ── Helpers ─────────────────────────────────────────────────────────────────

def _execute_write(record) -> None:
    """Commit a single record; log and absorb DB errors so pipeline keeps running."""
    try:
        with get_session() as session:
            session.add(record)
            session.commit()
    except Exception as exc:  # pylint: disable=broad-except
        _log.error("Database write failed for %s: %s", type(record).__name__, exc, exc_info=True)
