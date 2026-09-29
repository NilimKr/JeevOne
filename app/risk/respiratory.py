"""
risk/respiratory.py
===================
SpO₂-based respiratory risk indicator.

Uses SpO₂ as the sole available indicator (no respiratory-rate sensor exists).

Output levels:
  NORMAL | WATCH | HIGH

Single low reading → WATCH.
Persistent low readings → HIGH.

NOT a respiratory disease diagnosis.
This is a SpO₂-based respiratory risk indicator only.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List

from app.config_loader import cfg
from app.processing.features import Features

RISK_NORMAL = "NORMAL"
RISK_WATCH = "WATCH"
RISK_HIGH = "HIGH"


@dataclass
class RespiratoryRiskResult:
    risk: str
    reasons: List[str]


class RespiratoryRiskEngine:
    """
    Stateful SpO₂-based respiratory risk engine.
    Tracks consecutive low-SpO₂ readings to detect persistence.
    """

    def __init__(self) -> None:
        self._low_streak = 0

    def assess(self, features: Features) -> RespiratoryRiskResult:
        rc = cfg.risk["respiratory"]
        reasons: List[str] = []
        risk = RISK_NORMAL

        spo2 = features.spo2_smooth

        is_low = False

        if spo2 < rc["spo2_high"]:
            reasons.append(
                f"SpO₂ critically low ({spo2:.1f} % < {rc['spo2_high']} %)"
            )
            risk = RISK_HIGH
            is_low = True
        elif spo2 < rc["spo2_watch"]:
            reasons.append(
                f"SpO₂ below normal threshold ({spo2:.1f} % < {rc['spo2_watch']} %) – monitoring recommended"
            )
            risk = RISK_WATCH
            is_low = True

        # Baseline deviation
        dev = features.spo2_deviation
        if dev <= -3.0 and risk == RISK_NORMAL:
            reasons.append(
                f"SpO₂ ({spo2:.1f} %) is {abs(dev):.1f} % below personal baseline"
            )
            risk = RISK_WATCH
            is_low = True

        # Persistence
        if is_low:
            self._low_streak += 1
        else:
            self._low_streak = 0

        if self._low_streak >= rc["persistence_threshold"] and risk != RISK_HIGH:
            reasons.append(
                f"Low SpO₂ persisting for {self._low_streak} consecutive readings"
            )
            risk = RISK_HIGH

        if not reasons:
            reasons.append(f"SpO₂ within normal range ({spo2:.1f} %)")

        return RespiratoryRiskResult(risk=risk, reasons=reasons)


# Module-level singleton
respiratory_risk_engine = RespiratoryRiskEngine()
