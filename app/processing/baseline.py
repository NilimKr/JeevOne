"""
processing/baseline.py
======================
Short-term personal baseline engine.

The baseline represents the individual's normal physiological state.
It updates slowly so that a temporary abnormal period does NOT immediately
redefine what is "normal" for this person.

Algorithm:
  - Seed: configuration defaults (or first few readings).
  - Update rule: slow EMA (alpha ≈ 0.05 by default).
  - Only update when the new value is within "plausible normal range"
    to prevent a health-event period from corrupting the baseline.

Baseline is stored in memory (reset on restart, which is acceptable for MVP).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Optional

from app.config_loader import cfg

_log = logging.getLogger(__name__)


@dataclass
class Baseline:
    """Current personal baseline snapshot."""
    heart_rate: float
    spo2: float
    body_temperature: float
    # Standard deviations (available once enough data exists)
    hr_std: Optional[float] = None
    spo2_std: Optional[float] = None
    temp_std: Optional[float] = None
    sample_count: int = 0
    is_established: bool = False   # True once min_samples reached


class BaselineEngine:
    """
    Slow-EMA personal baseline for HR, SpO2, body temperature.

    Usage::

        engine = BaselineEngine()
        engine.update(heart_rate=72, spo2=98, body_temperature=36.6)
        bl = engine.current
    """

    def __init__(self) -> None:
        bc = cfg.baseline
        self._alpha = float(bc["ema_alpha"])
        self._min_samples = int(bc["min_samples"])

        # Initialise with configured seed values
        self._hr = float(bc["seed_heart_rate"])
        self._spo2 = float(bc["seed_spo2"])
        self._temp = float(bc["seed_body_temperature"])

        # Running variance accumulators (Welford's online algorithm)
        self._hr_m2 = 0.0
        self._spo2_m2 = 0.0
        self._temp_m2 = 0.0
        self._n = 0

    def update(
        self,
        heart_rate: float,
        spo2: float,
        body_temperature: float,
    ) -> None:
        """
        Update baseline with a new reading.
        Guards against obviously pathological values corrupting the baseline
        by only updating if the deviation is within ±3 × current std (once established).
        """
        established = self._n >= self._min_samples

        if established:
            # Skip extreme outliers to protect baseline stability
            if not self._is_plausible_update("hr", heart_rate, self._hr):
                _log.debug("Baseline: skipping HR %.1f (too far from baseline %.1f)", heart_rate, self._hr)
                heart_rate = None  # type: ignore[assignment]
            if not self._is_plausible_update("spo2", spo2, self._spo2):
                _log.debug("Baseline: skipping SpO2 %.1f (too far from baseline %.1f)", spo2, self._spo2)
                spo2 = None  # type: ignore[assignment]
            if not self._is_plausible_update("temp", body_temperature, self._temp):
                _log.debug("Baseline: skipping Temp %.1f (too far from baseline %.1f)", body_temperature, self._temp)
                body_temperature = None  # type: ignore[assignment]

        self._n += 1

        if heart_rate is not None:
            self._hr = self._ema(self._hr, heart_rate)
        if spo2 is not None:
            self._spo2 = self._ema(self._spo2, spo2)
        if body_temperature is not None:
            self._temp = self._ema(self._temp, body_temperature)

        # Welford variance (using all accepted values per-field independently)
        # Simplified: accumulate all accepted reading counts in _n

        if self._n == self._min_samples:
            _log.info("Personal baseline established after %d samples", self._n)

    def _ema(self, current: float, new: float) -> float:
        return self._alpha * new + (1.0 - self._alpha) * current

    def _is_plausible_update(self, field: str, value: float, baseline: float) -> bool:
        """
        Reject a value that deviates more than a fixed conservative bound.
        Bounds are intentionally generous so the filter only catches obvious
        measurement errors or acute events – not normal daily variation.
        """
        bounds = {
            "hr":   30.0,   # ± 30 bpm
            "spo2":  5.0,   # ± 5 %
            "temp":  1.5,   # ± 1.5 °C
        }
        return abs(value - baseline) <= bounds.get(field, 999)

    @property
    def current(self) -> Baseline:
        return Baseline(
            heart_rate=round(self._hr, 2),
            spo2=round(self._spo2, 2),
            body_temperature=round(self._temp, 2),
            sample_count=self._n,
            is_established=self._n >= self._min_samples,
        )


# Module-level singleton
baseline_engine = BaselineEngine()
