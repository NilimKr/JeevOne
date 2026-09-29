"""
risk/heat.py
============
Heat-risk indicator engine.

Combines:
  - Environmental heat burden (Heat Index)
  - Body-temperature elevation
  - HR elevation relative to personal baseline

Output: LOW | WATCH | HIGH  plus a list of human-readable reasons.

This is a RISK INDICATOR, not a medical diagnosis.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List

from app.config_loader import cfg
from app.processing.features import Features

RISK_LOW = "LOW"
RISK_WATCH = "WATCH"
RISK_HIGH = "HIGH"


@dataclass
class HeatRiskResult:
    risk: str                # LOW | WATCH | HIGH
    reasons: List[str]


def assess_heat_risk(features: Features) -> HeatRiskResult:
    """
    Evaluate heat-related risk from current features.
    Returns risk level and contributing reasons.
    """
    rc = cfg.risk["heat"]
    reasons: List[str] = []
    risk = RISK_LOW

    # ── Environmental heat burden ─────────────────────────────────────────
    hi = features.heat_index
    if hi >= rc["hi_high_threshold"]:
        reasons.append(
            f"High Heat Index ({hi:.1f} °C) – extreme heat burden"
        )
        risk = _escalate(risk, RISK_HIGH)
    elif hi >= rc["hi_watch_threshold"]:
        reasons.append(
            f"Elevated Heat Index ({hi:.1f} °C) – heat burden detected"
        )
        risk = _escalate(risk, RISK_WATCH)

    # ── Body temperature elevation ────────────────────────────────────────
    temp = features.body_temperature_smooth
    if temp >= rc["body_temp_high"]:
        reasons.append(
            f"Elevated body temperature ({temp:.1f} °C ≥ {rc['body_temp_high']} °C)"
        )
        risk = _escalate(risk, RISK_HIGH)
    elif temp >= rc["body_temp_watch"]:
        reasons.append(
            f"Body temperature slightly elevated ({temp:.1f} °C ≥ {rc['body_temp_watch']} °C)"
        )
        risk = _escalate(risk, RISK_WATCH)

    # ── HR elevation relative to personal baseline ────────────────────────
    hr_dev = features.hr_deviation
    if hr_dev >= rc["hr_deviation_high"]:
        reasons.append(
            f"Heart rate significantly elevated relative to baseline (+{hr_dev:.0f} bpm)"
        )
        risk = _escalate(risk, RISK_HIGH)
    elif hr_dev >= rc["hr_deviation_watch"]:
        reasons.append(
            f"Heart rate elevated relative to personal baseline (+{hr_dev:.0f} bpm)"
        )
        risk = _escalate(risk, RISK_WATCH)

    # ── High room temp + humidity compound ────────────────────────────────
    if features.room_temperature >= 35.0 and features.humidity >= 70.0:
        reasons.append(
            f"High room temperature ({features.room_temperature:.1f} °C) "
            f"combined with high humidity ({features.humidity:.1f} %)"
        )
        risk = _escalate(risk, RISK_WATCH)

    if not reasons:
        reasons.append("Environmental and physiological heat indicators within normal range")

    return HeatRiskResult(risk=risk, reasons=reasons)


def _escalate(current: str, candidate: str) -> str:
    """Return the higher of two risk levels."""
    order = {RISK_LOW: 0, RISK_WATCH: 1, RISK_HIGH: 2}
    return current if order[current] >= order[candidate] else candidate
