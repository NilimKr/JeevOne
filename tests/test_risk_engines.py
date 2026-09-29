"""
tests/test_risk_engines.py
==========================
Unit tests for risk engines: heat, vital, respiratory, and fusion.

Scenarios tested:
  - Normal
  - Heat stress
  - Abnormal HR (isolated)
  - Low SpO₂ (isolated)
  - Combined risk
"""

import sys
import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.ingestion.normalizer import SensorReading
from app.processing.baseline import Baseline
from app.processing.features import compute_features
from app.processing.windows import SensorWindows
from app.risk.heat import assess_heat_risk
from app.risk.vital import VitalRiskEngine
from app.risk.respiratory import RespiratoryRiskEngine
from app.risk.fusion import fuse_risks


def make_reading(**overrides) -> SensorReading:
    defaults = dict(
        timestamp=datetime.datetime(2024, 9, 30, 0, 0, 0, tzinfo=datetime.timezone.utc),
        timestamp_epoch=1727650000.0,
        device_id="test_device",
        heart_rate=72.0,
        spo2=98.0,
        body_temperature=36.6,
        room_temperature=25.0,
        humidity=50.0,
    )
    defaults.update(overrides)
    return SensorReading(**defaults)


def make_features(reading: SensorReading, baseline_hr=72.0, baseline_spo2=98.0, baseline_temp=36.6):
    windows = SensorWindows()
    for _ in range(5):
        windows.push(reading)
    baseline = Baseline(
        heart_rate=baseline_hr,
        spo2=baseline_spo2,
        body_temperature=baseline_temp,
        is_established=True,
        sample_count=20,
    )
    return compute_features(reading, windows, baseline)


# ── Normal scenario ───────────────────────────────────────────────────────────

class TestNormalScenario:
    def test_heat_low(self):
        r = make_reading()
        f = make_features(r)
        result = assess_heat_risk(f)
        assert result.risk in ("LOW", "WATCH")  # 25°C room temp = LOW

    def test_vital_normal(self):
        r = make_reading()
        f = make_features(r)
        eng = VitalRiskEngine()
        result = eng.assess(f)
        assert result.risk == "NORMAL"

    def test_respiratory_normal(self):
        r = make_reading()
        f = make_features(r)
        eng = RespiratoryRiskEngine()
        result = eng.assess(f)
        assert result.risk == "NORMAL"


# ── Heat stress scenario ──────────────────────────────────────────────────────

class TestHeatStressScenario:
    def test_heat_high(self):
        r = make_reading(
            heart_rate=105.0,
            body_temperature=38.2,
            room_temperature=39.0,
            humidity=80.0,
        )
        f = make_features(r, baseline_hr=72.0)
        result = assess_heat_risk(f)
        assert result.risk == "HIGH"
        assert len(result.reasons) > 0

    def test_heat_watch(self):
        r = make_reading(
            heart_rate=85.0,
            body_temperature=37.6,
            room_temperature=33.0,
            humidity=65.0,
        )
        f = make_features(r, baseline_hr=72.0)
        result = assess_heat_risk(f)
        assert result.risk in ("WATCH", "HIGH")


# ── Abnormal HR scenario ──────────────────────────────────────────────────────

class TestAbnormalHRScenario:
    def test_elevated_hr_watch(self):
        r = make_reading(heart_rate=108.0)
        f = make_features(r)
        eng = VitalRiskEngine()
        result = eng.assess(f)
        assert result.risk in ("WATCH", "HIGH")

    def test_persistent_elevated_hr_high(self):
        eng = VitalRiskEngine()
        r = make_reading(heart_rate=115.0)
        # Drive the persistence counter above the threshold
        for _ in range(5):
            result = eng.assess(make_features(r))
        assert result.risk == "HIGH"


# ── Low SpO₂ scenario ────────────────────────────────────────────────────────

class TestLowSpo2Scenario:
    def test_low_spo2_watch(self):
        r = make_reading(spo2=93.0)
        f = make_features(r, baseline_spo2=98.0)
        eng = RespiratoryRiskEngine()
        result = eng.assess(f)
        assert result.risk in ("WATCH", "HIGH")

    def test_critically_low_spo2_high(self):
        r = make_reading(spo2=88.0)
        f = make_features(r, baseline_spo2=98.0)
        eng = RespiratoryRiskEngine()
        result = eng.assess(f)
        assert result.risk == "HIGH"


# ── Combined risk scenario ────────────────────────────────────────────────────

class TestCombinedRiskScenario:
    def test_combined_overall_high(self):
        r = make_reading(
            heart_rate=120.0,
            spo2=89.0,
            body_temperature=38.3,
            room_temperature=40.0,
            humidity=82.0,
        )
        f = make_features(r, baseline_hr=72.0, baseline_spo2=98.0, baseline_temp=36.6)
        heat = assess_heat_risk(f)
        vital = VitalRiskEngine().assess(f)
        resp = RespiratoryRiskEngine().assess(f)
        fused = fuse_risks(heat, vital, resp)
        assert fused.overall_status == "HIGH"
        assert len(fused.reasons) > 0
        assert fused.recommendation


# ── Fusion logic ──────────────────────────────────────────────────────────────

class TestFusion:
    def _fuse(self, heat="NORMAL", vital="NORMAL", resp="NORMAL"):
        from app.risk.heat import HeatRiskResult
        from app.risk.vital import VitalRiskResult
        from app.risk.respiratory import RespiratoryRiskResult
        return fuse_risks(
            HeatRiskResult(risk=heat, reasons=[]),
            VitalRiskResult(risk=vital, reasons=[]),
            RespiratoryRiskResult(risk=resp, reasons=[]),
        )

    def test_all_normal_is_normal(self):
        assert self._fuse().overall_status == "NORMAL"

    def test_one_watch_is_watch(self):
        assert self._fuse(heat="WATCH").overall_status == "WATCH"

    def test_one_high_is_high(self):
        assert self._fuse(resp="HIGH").overall_status == "HIGH"

    def test_watch_plus_watch_is_watch(self):
        assert self._fuse(heat="WATCH", vital="WATCH").overall_status == "WATCH"

    def test_watch_plus_high_is_high(self):
        assert self._fuse(heat="WATCH", vital="HIGH").overall_status == "HIGH"
