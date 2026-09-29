"""
risk/fusion.py
==============
Combines Heat, Vital, and Respiratory risk into a single overall status.

Logic:
  - Any HIGH sub-risk → overall HIGH RISK
  - Any WATCH sub-risk (no HIGH) → overall WATCH
  - All NORMAL/LOW → overall NORMAL

The fusion is explicit and auditable – no opaque scoring.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List

from app.risk.heat import HeatRiskResult
from app.risk.recommendations import get_recommendation
from app.risk.respiratory import RespiratoryRiskResult
from app.risk.vital import VitalRiskResult

NORMAL = "NORMAL"
WATCH = "WATCH"
HIGH = "HIGH"

_WATCH_SET = {WATCH, HIGH}
_HIGH_SET = {HIGH}


@dataclass
class FusedRisk:
    heat_risk: str
    vital_risk: str
    respiratory_risk: str
    overall_status: str
    reasons: List[str]
    recommendation: str

    def to_dict(self) -> dict:
        return {
            "heat_risk": self.heat_risk,
            "vital_risk": self.vital_risk,
            "respiratory_risk": self.respiratory_risk,
            "overall_status": self.overall_status,
            "reasons": self.reasons,
            "recommendation": self.recommendation,
        }


def fuse_risks(
    heat: HeatRiskResult,
    vital: VitalRiskResult,
    respiratory: RespiratoryRiskResult,
) -> FusedRisk:
    """
    Produce an overall risk status and aggregate reasons.
    All contributing reasons from sub-engines are surfaced.
    """
    all_risks = {heat.risk, vital.risk, respiratory.risk}

    if _HIGH_SET & all_risks:
        overall = HIGH
    elif _WATCH_SET & all_risks:
        overall = WATCH
    else:
        overall = NORMAL

    # Aggregate all reasons with source labels
    reasons: List[str] = []
    reasons += [f"[Heat] {r}" for r in heat.reasons]
    reasons += [f"[Vital] {r}" for r in vital.reasons]
    reasons += [f"[SpO₂] {r}" for r in respiratory.reasons]

    recommendation = get_recommendation(
        heat_risk=heat.risk,
        vital_risk=vital.risk,
        respiratory_risk=respiratory.risk,
        overall_status=overall,
    )

    return FusedRisk(
        heat_risk=heat.risk,
        vital_risk=vital.risk,
        respiratory_risk=respiratory.risk,
        overall_status=overall,
        reasons=reasons,
        recommendation=recommendation,
    )
