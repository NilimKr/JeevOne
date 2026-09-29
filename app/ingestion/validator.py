"""
ingestion/validator.py
======================
Validates every incoming MQTT payload before anything else touches it.

Rules:
  1. Required fields exist.
  2. Numeric fields are actually numeric.
  3. Timestamp is a positive integer/float.
  4. Physical plausibility ranges (from config).

IMPORTANT: Validation failure = sensor/transmission error, NOT a health event.
Log rejections. Never crash the process.
"""

from __future__ import annotations

import logging
from typing import Any

from app.config_loader import cfg

_log = logging.getLogger(__name__)

_REQUIRED_FIELDS = [
    "device_id",
    "timestamp",
    "heart_rate",
    "spo2",
    "body_temperature",
    "room_temperature",
    "humidity",
]

_NUMERIC_FIELDS = [
    "heart_rate",
    "spo2",
    "body_temperature",
    "room_temperature",
    "humidity",
    "timestamp",
]


class ValidationError(Exception):
    """Raised (and caught) when a payload fails validation."""


def validate(payload: dict) -> dict:
    """
    Return the payload dict unchanged if valid.
    Raise ValidationError with a descriptive message if not.
    """
    _check_required_fields(payload)
    _check_types(payload)
    _check_timestamp(payload)
    _check_plausibility(payload)
    return payload


# ── Private checks ──────────────────────────────────────────────────────────

def _check_required_fields(payload: dict) -> None:
    missing = [f for f in _REQUIRED_FIELDS if f not in payload]
    if missing:
        raise ValidationError(f"Missing required fields: {missing}")


def _check_types(payload: dict) -> None:
    for field in _NUMERIC_FIELDS:
        val = payload.get(field)
        if val is None:
            raise ValidationError(f"Null value for required numeric field '{field}'")
        if not isinstance(val, (int, float)):
            raise ValidationError(
                f"Field '{field}' must be numeric, got {type(val).__name__!r}: {val!r}"
            )


def _check_timestamp(payload: dict) -> None:
    ts = payload["timestamp"]
    # Unix epoch: must be a positive number; reject obvious zeros or negatives
    if ts <= 0:
        raise ValidationError(f"Invalid timestamp: {ts}")
    # Sanity: timestamps before 2020 or after 2100 are almost certainly errors
    if not (1_577_836_800 <= ts <= 4_102_444_800):
        raise ValidationError(
            f"Timestamp {ts} is outside plausible range [2020-01-01, 2100-01-01]"
        )


def _check_plausibility(payload: dict) -> None:
    """Reject physically impossible sensor values using config ranges."""
    ranges = cfg.validation
    checks = {
        "heart_rate":        ranges["heart_rate"],
        "spo2":              ranges["spo2"],
        "body_temperature":  ranges["body_temperature"],
        "room_temperature":  ranges["room_temperature"],
        "humidity":          ranges["humidity"],
    }
    for field, bounds in checks.items():
        val = payload[field]
        lo, hi = bounds["min"], bounds["max"]
        if not (lo <= val <= hi):
            raise ValidationError(
                f"Field '{field}' value {val} is outside plausible range [{lo}, {hi}] – likely sensor error"
            )
