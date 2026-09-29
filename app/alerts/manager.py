"""
alerts/manager.py
=================
Local alert engine with state-change detection and cooldown/debouncing.

Generates an alert only when:
  1. The overall risk state changes (e.g. NORMAL → WATCH).
  2. OR the cooldown period has elapsed and the state is still elevated.

This prevents flooding the log/dashboard with identical repeated alerts.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import List, Optional

from app.config_loader import cfg
from app.risk.fusion import FusedRisk

_log = logging.getLogger(__name__)


@dataclass
class Alert:
    """A single alert event."""
    severity: str           # NORMAL | WATCH | HIGH
    category: str           # heat | vital | respiratory | overall
    message: str
    reasons: List[str]
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> dict:
        return {
            "severity": self.severity,
            "category": self.category,
            "message": self.message,
            "reasons": self.reasons,
            "timestamp": self.timestamp,
        }


class AlertManager:
    """
    Tracks risk-state history and emits alerts on state transitions.

    Cooldown:
      Once an alert is emitted for a given category, the same category
      will not re-alert until `cooldown_seconds` have passed,
      UNLESS the state escalates further.
    """

    def __init__(self) -> None:
        self._cooldown = cfg.alert_cooldown
        self._previous_overall: Optional[str] = None
        self._last_alert_time: float = 0.0
        self._alert_history: List[Alert] = []

    def process(self, fused: FusedRisk) -> Optional[Alert]:
        """
        Evaluate the fused risk state and return an Alert if warranted.
        Returns None if no alert should be emitted now.
        """
        now = time.time()
        overall = fused.overall_status

        state_changed = overall != self._previous_overall
        cooldown_elapsed = (now - self._last_alert_time) >= self._cooldown
        is_elevated = overall in ("WATCH", "HIGH")

        should_alert = state_changed or (is_elevated and cooldown_elapsed)

        if not should_alert:
            return None

        if overall == "NORMAL" and not state_changed:
            # Don't re-alert on sustained NORMAL
            return None

        alert = self._build_alert(fused, now)
        self._previous_overall = overall
        self._last_alert_time = now
        self._alert_history.append(alert)

        # Keep history bounded (last 100 alerts)
        if len(self._alert_history) > 100:
            self._alert_history = self._alert_history[-100:]

        _log.info(
            "ALERT [%s] %s – %s",
            alert.severity, alert.category, alert.message,
        )
        return alert

    @property
    def recent_alerts(self) -> List[Alert]:
        """Last 20 alerts, newest first."""
        return list(reversed(self._alert_history[-20:]))

    def _build_alert(self, fused: FusedRisk, ts: float) -> Alert:
        messages = {
            "NORMAL": "All health indicators have returned to normal.",
            "WATCH":  "Health monitoring alert – elevated readings detected.",
            "HIGH":   "HIGH RISK alert – significant health indicators detected. Please take action.",
        }
        return Alert(
            severity=fused.overall_status,
            category="overall",
            message=messages.get(fused.overall_status, "Health status changed."),
            reasons=fused.reasons,
            timestamp=ts,
        )


# Module-level singleton
alert_manager = AlertManager()
