"""
processing/filters.py
=====================
Lightweight signal filtering.

Available filters:
  - rolling_median  : median of a sliding window
  - moving_average  : simple mean of a sliding window
  - ema             : exponential moving average (stateful, per-signal)

Raw readings are stored as-is; only the output of these filters goes to analysis.
"""

from __future__ import annotations

from collections import deque
from typing import Optional

import numpy as np

from app.config_loader import cfg


def rolling_median(values: list[float]) -> Optional[float]:
    """
    Return the median of `values`.
    Returns None if the list is empty.
    """
    if not values:
        return None
    return float(np.median(values))


def moving_average(values: list[float]) -> Optional[float]:
    """Return the mean of `values`, or None if empty."""
    if not values:
        return None
    return float(np.mean(values))


class EMAFilter:
    """
    Stateful exponential moving average for a single signal.

    EMA_t = alpha * x_t + (1 - alpha) * EMA_{t-1}

    Seeded with the first value so the first call always returns a result.
    """

    def __init__(self, alpha: Optional[float] = None) -> None:
        self._alpha = alpha if alpha is not None else cfg.filter_ema_alpha
        self._value: Optional[float] = None

    def update(self, x: float) -> float:
        if self._value is None:
            self._value = x
        else:
            self._value = self._alpha * x + (1.0 - self._alpha) * self._value
        return self._value

    @property
    def value(self) -> Optional[float]:
        return self._value

    def reset(self) -> None:
        self._value = None
