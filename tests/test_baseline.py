"""
tests/test_baseline.py
======================
Unit tests for the personal baseline engine.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.processing.baseline import BaselineEngine


class TestBaselineEngine:

    def _seeded_engine(self, n: int, hr=72.0, spo2=98.0, temp=36.6) -> BaselineEngine:
        eng = BaselineEngine()
        for _ in range(n):
            eng.update(hr, spo2, temp)
        return eng

    def test_initial_baseline_uses_seed_values(self):
        eng = BaselineEngine()
        bl = eng.current
        assert 60 < bl.heart_rate < 90     # seed: 72
        assert bl.spo2 > 95                # seed: 98
        assert 35 < bl.body_temperature < 38  # seed: 36.6

    def test_not_established_initially(self):
        eng = BaselineEngine()
        eng.update(72, 98, 36.6)
        assert not eng.current.is_established

    def test_established_after_min_samples(self):
        eng = self._seeded_engine(10)
        assert eng.current.is_established

    def test_baseline_converges_toward_updates(self):
        eng = self._seeded_engine(50, hr=72.0)
        baseline_before = eng.current.heart_rate
        # Feed 50 more readings at 80 bpm
        for _ in range(50):
            eng.update(80.0, 98.0, 36.6)
        baseline_after = eng.current.heart_rate
        # Baseline should have drifted upward but not reached 80
        assert baseline_after > baseline_before
        assert baseline_after < 80.0  # slow EMA shouldn't instantly spike to 80

    def test_extreme_outlier_does_not_corrupt_baseline(self):
        eng = self._seeded_engine(20, hr=72.0)
        stable = eng.current.heart_rate
        # Push a clearly pathological value
        eng.update(250.0, 98.0, 36.6)
        after = eng.current.heart_rate
        # Baseline should remain close to 72 (outlier rejected)
        assert abs(after - stable) < 5.0

    def test_sample_count_increments(self):
        eng = BaselineEngine()
        assert eng.current.sample_count == 0
        eng.update(72, 98, 36.6)
        assert eng.current.sample_count == 1
        eng.update(72, 98, 36.6)
        assert eng.current.sample_count == 2
