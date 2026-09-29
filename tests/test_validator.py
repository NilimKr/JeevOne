"""
tests/test_validator.py
=======================
Unit tests for ingestion/validator.py.

Tests:
  - Valid payload passes
  - Missing field is rejected
  - Null value is rejected
  - Wrong type is rejected
  - Invalid timestamp is rejected
  - Physically impossible values are rejected
"""

import pytest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.ingestion.validator import validate, ValidationError

VALID_PAYLOAD = {
    "device_id": "esp32_01",
    "timestamp": 1727650000,
    "heart_rate": 72,
    "spo2": 98,
    "body_temperature": 36.8,
    "room_temperature": 28.4,
    "humidity": 61.2,
}


def _payload(**overrides):
    p = VALID_PAYLOAD.copy()
    p.update(overrides)
    return p


class TestValidPayload:
    def test_valid_payload_passes(self):
        result = validate(VALID_PAYLOAD.copy())
        assert result == VALID_PAYLOAD


class TestMissingFields:
    @pytest.mark.parametrize("field", [
        "device_id", "timestamp", "heart_rate",
        "spo2", "body_temperature", "room_temperature", "humidity",
    ])
    def test_missing_field_raises(self, field):
        p = VALID_PAYLOAD.copy()
        del p[field]
        with pytest.raises(ValidationError, match="Missing required fields"):
            validate(p)


class TestNullValues:
    def test_null_heart_rate(self):
        with pytest.raises(ValidationError, match="Null value"):
            validate(_payload(heart_rate=None))

    def test_null_spo2(self):
        with pytest.raises(ValidationError, match="Null value"):
            validate(_payload(spo2=None))


class TestWrongTypes:
    def test_string_heart_rate(self):
        with pytest.raises(ValidationError, match="must be numeric"):
            validate(_payload(heart_rate="fast"))

    def test_string_spo2(self):
        with pytest.raises(ValidationError, match="must be numeric"):
            validate(_payload(spo2="high"))


class TestTimestamp:
    def test_zero_timestamp(self):
        with pytest.raises(ValidationError, match="Invalid timestamp"):
            validate(_payload(timestamp=0))

    def test_negative_timestamp(self):
        with pytest.raises(ValidationError, match="Invalid timestamp"):
            validate(_payload(timestamp=-1))

    def test_year_1990_timestamp(self):
        with pytest.raises(ValidationError, match="outside plausible range"):
            validate(_payload(timestamp=631152000))  # 1990-01-01


class TestPlausibility:
    def test_hr_too_high(self):
        with pytest.raises(ValidationError, match="sensor error"):
            validate(_payload(heart_rate=300))

    def test_hr_too_low(self):
        with pytest.raises(ValidationError, match="sensor error"):
            validate(_payload(heart_rate=5))

    def test_spo2_too_high(self):
        with pytest.raises(ValidationError, match="sensor error"):
            validate(_payload(spo2=101))

    def test_spo2_impossible_low(self):
        with pytest.raises(ValidationError, match="sensor error"):
            validate(_payload(spo2=10))

    def test_body_temp_too_high(self):
        with pytest.raises(ValidationError, match="sensor error"):
            validate(_payload(body_temperature=50))

    def test_body_temp_too_low(self):
        with pytest.raises(ValidationError, match="sensor error"):
            validate(_payload(body_temperature=20))

    def test_humidity_over_100(self):
        with pytest.raises(ValidationError, match="sensor error"):
            validate(_payload(humidity=110))
