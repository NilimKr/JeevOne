"""
ingestion/processor.py
======================
Glues validate → normalize together.
Called by the MQTT client callback.
Returns a SensorReading or None (logged rejection).
"""

from __future__ import annotations

import logging
from typing import Optional

from app.ingestion.normalizer import SensorReading, normalize
from app.ingestion.validator import ValidationError, validate

_log = logging.getLogger(__name__)


def process_raw(payload: dict) -> Optional[SensorReading]:
    """
    Validate then normalize a raw MQTT payload.

    Returns SensorReading on success, None on validation failure.
    Never raises; validation errors are logged as warnings.
    """
    try:
        validate(payload)
    except ValidationError as exc:
        _log.warning("Payload rejected [sensor/transmission error]: %s | payload=%s", exc, payload)
        return None

    reading = normalize(payload)
    _log.debug(
        "Ingested reading from %s @ %s – HR=%.0f SpO2=%.1f Temp=%.1f",
        reading.device_id,
        reading.timestamp.isoformat(),
        reading.heart_rate,
        reading.spo2,
        reading.body_temperature,
    )
    return reading
