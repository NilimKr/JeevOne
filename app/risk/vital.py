"""
risk/vital.py
=============
Vital-signs risk indicator.

Analyzes HR and body temperature against absolute thresholds and personal
baseline deviation.

Single abnormal reading → WATCH (continue monitoring).
Persistent or combined deviations → HIGH.

All thresholds are read from config – none hardcoded here.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List

from app.config_loader import cfg
from app.processing.features import Features

RISK_NORMAL = "NORMAL"
RISK_WATCH = "WATCH"
RISK_HIGH = "HIGH"


@dataclass
class VitalRiskResult:
    risk: str
    reasons: List[str]


class VitalRiskEngine:
    """
    Stateful vital-risk engine.
    Tracks consecutive abnormal readings to distinguish transient from persistent.
    """

    def __init__(self) -> None:
        self._abnormal_streak = 0

    def assess(self, features: Features) -> VitalRiskResult:
        rc = cfg.risk["vital"]
        reasons: List[str] = []
        is_abnormal = False
        risk = RISK_NORMAL

        hr = features.heart_rate_smooth
        temp = features.body_temperature_smooth

        # ── Absolute HR thresholds ───────────────────────────────────────
        if hr >= rc["hr_high_high"]:
            reasons.append(f"Heart rate very high ({hr:.0f} bpm ≥ {rc['hr_high_high']} bpm)")
            risk = _escalate(risk, RISK_HIGH)
            is_abnormal = True
        elif hr <= rc["hr_low_high"]:
            reasons.append(f"Heart rate very low ({hr:.0f} bpm ≤ {rc['hr_low_high']} bpm)")
            risk = _escalate(risk, RISK_HIGH)
            is_abnormal = True
        elif hr >= rc["hr_high_watch"]:
            reasons.append(f"Heart rate elevated ({hr:.0f} bpm ≥ {rc['hr_high_watch']} bpm)")
            risk = _escalate(risk, RISK_WATCH)
            is_abnormal = True
        elif hr <= rc["hr_low_watch"]:
            reasons.append(f"Heart rate low ({hr:.0f} bpm ≤ {rc['hr_low_watch']} bpm)")
            risk = _escalate(risk, RISK_WATCH)
            is_abnormal = True

        # ── Absolute temperature thresholds ──────────────────────────────
        if temp >= rc["temp_high"]:
            reasons.append(f"Elevated body temperature ({temp:.1f} °C ≥ {rc['temp_high']} °C)")
            risk = _escalate(risk, RISK_HIGH)
            is_abnormal = True
        elif temp >= rc["temp_watch"]:
            reasons.append(f"Body temperature slightly elevated ({temp:.1f} °C ≥ {rc['temp_watch']} °C)")
            risk = _escalate(risk, RISK_WATCH)
            is_abnormal = True

        # ── Persistence escalation ────────────────────────────────────────
        if is_abnormal:
            self._abnormal_streak += 1
        else:
            self._abnormal_streak = 0

        if self._abnormal_streak >= rc["persistence_threshold"]:
            reasons.append(
                f"Abnormal vital signs persisting for {self._abnormal_streak} consecutive readings"
            )
            risk = _escalate(risk, RISK_HIGH)

        if not reasons:
            reasons.append("Heart rate and body temperature within normal range")

        return VitalRiskResult(risk=risk, reasons=reasons)


def _escalate(current: str, candidate: str) -> str:
    order = {RISK_NORMAL: 0, RISK_WATCH: 1, RISK_HIGH: 2}
    return current if order[current] >= order[candidate] else candidate


# Module-level singleton (stateful – maintains streak counter)
vital_risk_engine = VitalRiskEngine()
