"""
processing/windows.py
=====================
Maintains short sliding windows of recent sensor readings.
Used for:
  - smoothing (feed into filters)
  - baseline calculation
  - persistence detection (how many consecutive readings are abnormal)
  - trend direction
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from typing import Optional

import numpy as np

from app.config_loader import cfg
from app.ingestion.normalizer import SensorReading


@dataclass
class WindowStats:
    """Summary statistics of a window (returned to callers)."""
    mean: float
    std: float
    min: float
    max: float
    count: int
    latest: float


class SignalWindow:
    """Fixed-size sliding window for a single numeric signal."""

    def __init__(self, maxlen: int) -> None:
        self._buf: deque[float] = deque(maxlen=maxlen)

    def push(self, value: float) -> None:
        self._buf.append(value)

    def values(self) -> list[float]:
        return list(self._buf)

    def stats(self) -> Optional[WindowStats]:
        if not self._buf:
            return None
        arr = np.array(self._buf, dtype=float)
        return WindowStats(
            mean=float(arr.mean()),
            std=float(arr.std()),
            min=float(arr.min()),
            max=float(arr.max()),
            count=len(arr),
            latest=float(arr[-1]),
        )

    def __len__(self) -> int:
        return len(self._buf)


class SensorWindows:
    """
    Maintains sliding windows for each sensor channel.

    Two window sizes (from config):
      short_window – used for smoothing and baseline seeding
      long_window  – used for trend analysis
    """

    def __init__(self) -> None:
        short = cfg.window_short
        long_ = cfg.window_long

        # Short windows (primary)
        self.heart_rate = SignalWindow(short)
        self.spo2 = SignalWindow(short)
        self.body_temperature = SignalWindow(short)
        self.room_temperature = SignalWindow(short)
        self.humidity = SignalWindow(short)

        # Long windows (trend analysis)
        self.heart_rate_long = SignalWindow(long_)
        self.spo2_long = SignalWindow(long_)
        self.body_temperature_long = SignalWindow(long_)

    def push(self, reading: SensorReading) -> None:
        """Add a new reading to all windows."""
        self.heart_rate.push(reading.heart_rate)
        self.spo2.push(reading.spo2)
        self.body_temperature.push(reading.body_temperature)
        self.room_temperature.push(reading.room_temperature)
        self.humidity.push(reading.humidity)

        self.heart_rate_long.push(reading.heart_rate)
        self.spo2_long.push(reading.spo2)
        self.body_temperature_long.push(reading.body_temperature)

    def is_ready(self, min_samples: int = 5) -> bool:
        """True once we have enough data for meaningful analysis."""
        return len(self.heart_rate) >= min_samples


# Module-level singleton shared across the pipeline
sensor_windows = SensorWindows()
