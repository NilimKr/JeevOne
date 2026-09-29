"""
main.py
=======
Application entry point for the Raspberry Pi health-processing service.

Start order:
  1. Configure logging
  2. Initialise SQLite database
  3. Start Flask API server in a background thread
  4. Start MQTT client (blocking, in the main thread)

The MQTT thread feeds the processing pipeline.
The Flask thread serves API / SSE requests.
Both share state through pipeline_state.state_store (thread-safe).

Run with:
    python -m app.main
or:
    python app/main.py
"""

from __future__ import annotations

import logging
import threading

from flask import Flask
from flask_cors import CORS

from app.api.routes import api_bp
from app.api.websocket import notify_update, ws_bp
from app.alerts.manager import alert_manager
from app.config_loader import cfg
from app.ingestion.processor import process_raw
from app.logger import configure_logging
from app.mqtt.client import HealthMQTTClient
from app.pipeline_state import state_store
from app.processing.baseline import baseline_engine
from app.processing.features import compute_features
from app.processing.windows import sensor_windows
from app.risk.fusion import fuse_risks
from app.risk.heat import assess_heat_risk
from app.risk.respiratory import respiratory_risk_engine
from app.risk.vital import vital_risk_engine
from app.storage.database import init_db
from app.storage.repository import insert_reading, insert_risk_state

_log = logging.getLogger(__name__)


# ── Pipeline callback (called by MQTT client on every message) ───────────────

def on_sensor_message(payload: dict) -> None:
    """
    Full processing pipeline for one incoming MQTT message.

    Stages:
      validate → normalize → store raw → update windows → update baseline
      → compute features → assess risks → fuse → recommend
      → store risk state → update shared state → notify SSE clients
    """
    # 1. Validate + normalize
    reading = process_raw(payload)
    if reading is None:
        state_store.increment_rejected()
        return

    # 2. Store raw reading in SQLite (fire-and-forget; errors are logged in repo)
    insert_reading(reading)

    # 3. Update sliding windows
    sensor_windows.push(reading)

    # 4. Update personal baseline
    baseline_engine.update(
        heart_rate=reading.heart_rate,
        spo2=reading.spo2,
        body_temperature=reading.body_temperature,
    )
    baseline = baseline_engine.current

    # 5. Compute derived features
    features = compute_features(reading, sensor_windows, baseline)

    # 6. Run risk engines
    heat_result = assess_heat_risk(features)
    vital_result = vital_risk_engine.assess(features)
    resp_result = respiratory_risk_engine.assess(features)

    # 7. Fuse risks → overall status + recommendation
    fused = fuse_risks(heat_result, vital_result, resp_result)

    _log.info(
        "Risk | Heat=%s Vital=%s SpO₂=%s → Overall=%s | Device=%s",
        fused.heat_risk, fused.vital_risk, fused.respiratory_risk,
        fused.overall_status, reading.device_id,
    )

    # 8. Persist risk state
    insert_risk_state(
        reading=reading,
        heat_risk=fused.heat_risk,
        vital_risk=fused.vital_risk,
        respiratory_risk=fused.respiratory_risk,
        overall_status=fused.overall_status,
        recommendation=fused.recommendation,
        reasons=fused.reasons,
    )

    # 9. Update shared in-memory state (for API fast path)
    state_store.update(reading, fused)

    # 10. Alert engine
    alert_manager.process(fused)

    # 11. Notify SSE clients
    notify_update()


# ── Flask app factory ────────────────────────────────────────────────────────

def create_app() -> Flask:
    app = Flask(__name__, template_folder="../dashboard/templates", static_folder="../dashboard/static")
    CORS(app)
    app.register_blueprint(api_bp)
    app.register_blueprint(ws_bp)

    # Serve dashboard index
    @app.route("/")
    def dashboard():
        from flask import render_template
        return render_template("index.html")

    return app


# ── Main entry point ─────────────────────────────────────────────────────────

def main() -> None:
    configure_logging(level=cfg.log_level, fmt=cfg.log_format)
    _log.info("=== Personal Health Companion starting ===")

    # Initialise database
    init_db()

    # Start Flask in a daemon thread
    flask_app = create_app()

    def run_flask():
        _log.info("API server starting at http://%s:%d", cfg.api_host, cfg.api_port)
        flask_app.run(
            host=cfg.api_host,
            port=cfg.api_port,
            debug=False,
            use_reloader=False,  # must be False when running in a thread
            threaded=True,
        )

    api_thread = threading.Thread(target=run_flask, name="flask-api", daemon=True)
    api_thread.start()

    # Start MQTT client (blocks until Ctrl+C)
    mqtt_client = HealthMQTTClient(on_message_callback=on_sensor_message)
    mqtt_client.start()

    _log.info("=== Personal Health Companion stopped ===")


if __name__ == "__main__":
    main()
