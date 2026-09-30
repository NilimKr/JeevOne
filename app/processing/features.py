"""
processing/features.py
======================
Derives secondary features from raw readings + windows + baseline.

All features are deterministic and interpretable.
No machine learning here.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import numpy as np

from app.ingestion.normalizer import SensorReading
from app.processing.baseline import Baseline
from app.processing.filters import rolling_median, moving_average
from app.processing.windows import SensorWindows


@dataclass
class Features:
    """All derived features for one time-step."""
    # Raw (latest reading)
    heart_rate: float
    spo2: float
    body_temperature: float
    room_temperature: float
    humidity: float
    bp_sys: float                # mmHg
    bp_dia: float                # mmHg

    # Smoothed (rolling median over short window)
    heart_rate_smooth: float
    spo2_smooth: float
    body_temperature_smooth: float
    bp_sys_smooth: float         # mmHg

    # Moving averages
    heart_rate_ma: float
    spo2_ma: float
    body_temperature_ma: float

    # Deviation from personal baseline
    hr_deviation: float          # bpm
    spo2_deviation: float        # %
    temp_deviation: float        # °C

    # Environmental heat burden (simplified Heat Index, °C)
    heat_index: float

    # Combined physiological strain (dimensionless, 0–100 scale)
    physiological_strain: float

    # Context
    baseline_established: bool


def compute_features(
    reading: SensorReading,
    windows: SensorWindows,
    baseline: Baseline,
) -> Features:
    """Compute all derived features for the current reading."""

    hr_vals = windows.heart_rate.values()
    spo2_vals = windows.spo2.values()
    temp_vals = windows.body_temperature.values()
    bp_sys_vals = windows.bp_sys.values()

    hr_smooth = rolling_median(hr_vals) or reading.heart_rate
    spo2_smooth = rolling_median(spo2_vals) or reading.spo2
    temp_smooth = rolling_median(temp_vals) or reading.body_temperature
    bp_sys_smooth = rolling_median(bp_sys_vals) or reading.bp_sys

    hr_ma = moving_average(hr_vals) or reading.heart_rate
    spo2_ma = moving_average(spo2_vals) or reading.spo2
    temp_ma = moving_average(temp_vals) or reading.body_temperature

    hr_dev = reading.heart_rate - baseline.heart_rate
    spo2_dev = reading.spo2 - baseline.spo2
    temp_dev = reading.body_temperature - baseline.body_temperature

    hi = _heat_index(reading.room_temperature, reading.humidity)

    strain = _physiological_strain(
        hr=reading.heart_rate,
        hr_baseline=baseline.heart_rate,
        temp=reading.body_temperature,
        temp_baseline=baseline.body_temperature,
        spo2=reading.spo2,
    )

    return Features(
        heart_rate=reading.heart_rate,
        spo2=reading.spo2,
        body_temperature=reading.body_temperature,
        room_temperature=reading.room_temperature,
        humidity=reading.humidity,
        bp_sys=reading.bp_sys,
        bp_dia=reading.bp_dia,
        heart_rate_smooth=hr_smooth,
        spo2_smooth=spo2_smooth,
        body_temperature_smooth=temp_smooth,
        bp_sys_smooth=bp_sys_smooth,
        heart_rate_ma=hr_ma,
        spo2_ma=spo2_ma,
        body_temperature_ma=temp_ma,
        hr_deviation=hr_dev,
        spo2_deviation=spo2_dev,
        temp_deviation=temp_dev,
        heat_index=hi,
        physiological_strain=strain,
        baseline_established=baseline.is_established,
    )


# ── Private helpers ──────────────────────────────────────────────────────────

def _heat_index(temp_c: float, humidity: float) -> float:
    """
    Simplified Heat Index (Steadman 1979 approximation), in °C.
    Only meaningful above 27 °C. Below that returns temp_c directly.
    """
    if temp_c < 27.0:
        return temp_c

    t = temp_c
    r = humidity

    hi = (
        -8.78469475556
        + 1.61139411 * t
        + 2.33854883889 * r
        - 0.14611605 * t * r
        - 0.012308094 * t * t
        - 0.016424828 * r * r
        + 0.002211732 * t * t * r
        + 0.00072546 * t * r * r
        - 0.000003582 * t * t * r * r
    )
    return round(hi, 1)


def _physiological_strain(
    hr: float,
    hr_baseline: float,
    temp: float,
    temp_baseline: float,
    spo2: float,
) -> float:
    """
    Combined physiological strain index (0–100, dimensionless).
    Higher = more strain. Not a medical score.

    Components:
      - HR elevation relative to baseline
      - Body temperature elevation
      - SpO2 deficit
    All clamped to [0, 1] then averaged and scaled.
    """
    hr_strain = np.clip((hr - hr_baseline) / 40.0, 0.0, 1.0)
    temp_strain = np.clip((temp - temp_baseline) / 2.0, 0.0, 1.0)
    spo2_strain = np.clip((100.0 - spo2) / 10.0, 0.0, 1.0)

    combined = (hr_strain * 0.4 + temp_strain * 0.4 + spo2_strain * 0.2)
    return round(float(combined * 100.0), 1)
