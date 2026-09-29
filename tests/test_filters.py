"""
tests/test_filters.py
=====================
Unit tests for processing/filters.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.processing.filters import rolling_median, moving_average, EMAFilter


class TestRollingMedian:
    def test_empty(self):
        assert rolling_median([]) is None

    def test_single(self):
        assert rolling_median([72.0]) == 72.0

    def test_sorted(self):
        assert rolling_median([60, 70, 80]) == 70.0

    def test_noisy_list(self):
        data = [72, 74, 200, 71, 73]   # 200 is an outlier
        result = rolling_median(data)
        # Median of sorted [71,72,73,74,200] = 73
        assert result == 73.0


class TestMovingAverage:
    def test_empty(self):
        assert moving_average([]) is None

    def test_single(self):
        assert moving_average([72.0]) == 72.0

    def test_average(self):
        assert moving_average([60, 80]) == 70.0


class TestEMAFilter:
    def test_first_value(self):
        ema = EMAFilter(alpha=0.2)
        assert ema.update(100.0) == 100.0

    def test_smoothing(self):
        ema = EMAFilter(alpha=0.5)
        ema.update(100.0)
        v = ema.update(0.0)
        # 0.5*0 + 0.5*100 = 50
        assert abs(v - 50.0) < 0.01

    def test_spike_smoothed(self):
        ema = EMAFilter(alpha=0.1)
        for _ in range(20):
            ema.update(72.0)   # stabilise
        baseline_ema = ema.value
        spiked = ema.update(200.0)
        # EMA should NOT jump to 200
        assert spiked < 100.0

    def test_reset(self):
        ema = EMAFilter(alpha=0.2)
        ema.update(72.0)
        ema.reset()
        assert ema.value is None
