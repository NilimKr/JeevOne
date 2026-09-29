"""
risk/recommendations.py
=======================
Maps risk conditions to wellness recommendations.

Language is conservative and wellness-oriented – never clinical diagnosis.
Every recommendation is framed as an informational suggestion.
"""

from __future__ import annotations

from typing import List

# Risk-level constants (matched to what engines return)
LOW = "LOW"
NORMAL = "NORMAL"
WATCH = "WATCH"
HIGH = "HIGH"

_HEAT_RECOMMENDATIONS = {
    LOW:   "Environmental conditions are comfortable. No action required.",
    NORMAL: "Environmental conditions are comfortable. No action required.",
    WATCH: (
        "Elevated heat detected. Consider moving to a cooler area. "
        "Stay hydrated and avoid strenuous activity."
    ),
    HIGH: (
        "High heat burden detected. Move to a cooler environment immediately. "
        "Rest and maintain fluid intake. Recheck readings. "
        "If discomfort persists or worsens, seek appropriate assistance."
    ),
}

_VITAL_RECOMMENDATIONS = {
    NORMAL: "Vital signs appear normal. Continue regular monitoring.",
    WATCH: (
        "Minor vital sign deviation noted. Stop strenuous activity and rest. "
        "Continue monitoring. If the reading persists or you experience symptoms, "
        "seek appropriate medical attention."
    ),
    HIGH: (
        "Persistent or significant vital-sign abnormality detected. "
        "Stop all physical exertion and rest in a comfortable position. "
        "Continue monitoring closely. If symptoms are present or condition persists, "
        "seek medical attention promptly."
    ),
}

_RESPIRATORY_RECOMMENDATIONS = {
    NORMAL: "SpO₂ is within the normal range.",
    WATCH: (
        "SpO₂ reading is below the normal threshold. "
        "Sit in an upright position in a well-ventilated area. "
        "Take slow, deep breaths. Recheck in a few minutes. "
        "If it does not improve or you feel breathless, seek medical advice."
    ),
    HIGH: (
        "SpO₂ level is significantly low. "
        "Move to a well-ventilated area immediately. "
        "Sit upright and breathe slowly and deeply. "
        "This reading warrants prompt medical assessment."
    ),
}

_DISCLAIMER = (
    " Note: These are wellness monitoring suggestions only. "
    "This system does not provide medical diagnosis."
)


def get_recommendation(
    heat_risk: str,
    vital_risk: str,
    respiratory_risk: str,
    overall_status: str,
) -> str:
    """
    Return a composite wellness recommendation string.
    Selects the most relevant recommendations based on dominant risk.
    """
    parts: List[str] = []

    # Always include the most prominent risk recommendation
    if overall_status == HIGH:
        # Lead with the most severe sub-risk
        if heat_risk == HIGH:
            parts.append(_HEAT_RECOMMENDATIONS[HIGH])
        if vital_risk == HIGH:
            parts.append(_VITAL_RECOMMENDATIONS[HIGH])
        if respiratory_risk == HIGH:
            parts.append(_RESPIRATORY_RECOMMENDATIONS[HIGH])

    elif overall_status == WATCH:
        if heat_risk == WATCH or heat_risk == HIGH:
            parts.append(_HEAT_RECOMMENDATIONS[WATCH])
        if vital_risk == WATCH or vital_risk == HIGH:
            parts.append(_VITAL_RECOMMENDATIONS[WATCH])
        if respiratory_risk == WATCH or respiratory_risk == HIGH:
            parts.append(_RESPIRATORY_RECOMMENDATIONS[WATCH])

    else:
        parts.append("All monitored indicators are within normal range. Continue regular activity.")

    if not parts:
        parts.append("Continue monitoring.")

    # Deduplicate while preserving order
    seen: set = set()
    unique_parts: List[str] = []
    for p in parts:
        if p not in seen:
            seen.add(p)
            unique_parts.append(p)

    return " ".join(unique_parts) + _DISCLAIMER
