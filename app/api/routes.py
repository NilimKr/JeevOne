"""
api/routes.py
=============
Flask REST API exposing processed pipeline data to the local dashboard.

Endpoints:
  GET /api/health         – service liveness check
  GET /api/status         – pipeline stats
  GET /api/latest         – latest reading + risk state (in-memory, fast)
  GET /api/risk           – risk breakdown
  GET /api/history        – recent sensor readings from DB
  GET /api/alerts         – recent alert history
  GET /api/baseline       – current personal baseline
"""

from __future__ import annotations

import json
import logging

from flask import Blueprint, jsonify, Response

from app.alerts.manager import alert_manager
from app.pipeline_state import state_store
from app.processing.baseline import baseline_engine
from app.storage.repository import get_recent_readings, get_recent_risk_states

_log = logging.getLogger(__name__)

api_bp = Blueprint("api", __name__, url_prefix="/api")


@api_bp.route("/health", methods=["GET"])
def health() -> Response:
    """Liveness check – always returns 200 if the service is up."""
    return jsonify({"status": "ok", "service": "personal-health-companion"})


@api_bp.route("/status", methods=["GET"])
def status() -> Response:
    """Pipeline statistics."""
    snap = state_store.snapshot()
    return jsonify({
        "status": "ok",
        "last_update": snap.last_update,
        "total_readings": snap.total_readings,
        "total_rejected": snap.total_rejected,
        "has_data": snap.reading is not None,
    })


@api_bp.route("/latest", methods=["GET"])
def latest() -> Response:
    """Latest reading and risk state from in-memory store (fast path)."""
    snap = state_store.snapshot()
    if snap.reading is None:
        return jsonify({"status": "no_data", "message": "No readings received yet"}), 200

    return jsonify({
        "latest": snap.reading.to_dict(),
        "risk": snap.fused_risk.to_dict() if snap.fused_risk else None,
        "last_update": snap.last_update,
    })


@api_bp.route("/risk", methods=["GET"])
def risk() -> Response:
    """Current risk breakdown."""
    snap = state_store.snapshot()
    if snap.fused_risk is None:
        return jsonify({"status": "no_data"}), 200

    return jsonify(snap.fused_risk.to_dict())


@api_bp.route("/history", methods=["GET"])
def history() -> Response:
    """Recent sensor readings from the database (last 60 by default)."""
    try:
        records = get_recent_readings(limit=60)
        data = [
            {
                "id": r.id,
                "timestamp": r.timestamp_iso,
                "device_id": r.device_id,
                "heart_rate": r.heart_rate,
                "spo2": r.spo2,
                "body_temperature": r.body_temperature,
                "room_temperature": r.room_temperature,
                "humidity": r.humidity,
                "bp_sys": r.bp_sys,
                "bp_dia": r.bp_dia,
            }
            for r in records
        ]
        return jsonify({"count": len(data), "readings": data})
    except Exception as exc:
        _log.error("Error fetching history: %s", exc)
        return jsonify({"error": "Database error"}), 500


@api_bp.route("/alerts", methods=["GET"])
def alerts() -> Response:
    """Recent alert history."""
    return jsonify({
        "alerts": [a.to_dict() for a in alert_manager.recent_alerts]
    })


@api_bp.route("/baseline", methods=["GET"])
def baseline() -> Response:
    """Current personal baseline."""
    bl = baseline_engine.current
    return jsonify({
        "heart_rate": bl.heart_rate,
        "spo2": bl.spo2,
        "body_temperature": bl.body_temperature,
        "sample_count": bl.sample_count,
        "is_established": bl.is_established,
    })
