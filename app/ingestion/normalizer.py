"""
ingestion/normalizer.py
=======================
Converts a validated raw MQTT dict into a canonical SensorReading dataclass.
All downstream code works with SensorReading – never raw dicts.
"""

from __future__ import annotations

import datetime
from dataclasses import dataclass


@dataclass(frozen=True)
class SensorReading:
    """
    Canonical internal representation of one sensor sample.
    All fields are typed and immutable.
    """
    timestamp: datetime.datetime   # UTC datetime (timezone-aware)
    device_id: str
    heart_rate: float              # bpm
    spo2: float                    # %
    body_temperature: float        # °C
    room_temperature: float        # °C
    humidity: float                # %

    # Epoch seconds kept for DB storage
    timestamp_epoch: float

    def to_dict(self) -> dict:
        return {
            "timestamp": self.timestamp.isoformat(),
            "timestamp_epoch": self.timestamp_epoch,
            "device_id": self.device_id,
            "heart_rate": self.heart_rate,
            "spo2": self.spo2,
            "body_temperature": self.body_temperature,
            "room_temperature": self.room_temperature,
            "humidity": self.humidity,
        }


def normalize(payload: dict) -> SensorReading:
    """
    Convert a validated MQTT payload dict to a SensorReading.

    Timestamp handling:
      - Assumes Unix epoch seconds (as ESP32 publishes).
      - Converts to UTC datetime.
    """
    epoch = float(payload["timestamp"])
    dt = datetime.datetime.fromtimestamp(epoch, tz=datetime.timezone.utc)

    return SensorReading(
        timestamp=dt,
        timestamp_epoch=epoch,
        device_id=str(payload["device_id"]),
        heart_rate=float(payload["heart_rate"]),
        spo2=float(payload["spo2"]),
        body_temperature=float(payload["body_temperature"]),
        room_temperature=float(payload["room_temperature"]),
        humidity=float(payload["humidity"]),
    )
