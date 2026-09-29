"""
mqtt/client.py
==============
Robust MQTT client for the Raspberry Pi health-processing service.

Responsibilities:
  - Connect to the local Mosquitto broker.
  - Subscribe to health/sensors.
  - Receive raw JSON payloads and pass them to a user-supplied callback.
  - Handle malformed messages without crashing.
  - Log all connection / disconnection events.
  - Reconnect automatically if the broker goes away temporarily.

This module contains NO health-risk logic.
"""

from __future__ import annotations

import json
import logging
import time
from typing import Callable

import paho.mqtt.client as mqtt

from app.config_loader import cfg
from app.mqtt.topics import TOPIC_SENSORS

_log = logging.getLogger(__name__)

# Type alias: callback receives the parsed dict (already JSON-decoded)
MessageCallback = Callable[[dict], None]


class HealthMQTTClient:
    """
    Wraps paho-mqtt with automatic reconnect and structured logging.

    Usage::

        def on_message(payload: dict) -> None:
            print(payload)

        client = HealthMQTTClient(on_message_callback=on_message)
        client.start()          # blocks until client.stop() is called
    """

    def __init__(self, on_message_callback: MessageCallback) -> None:
        self._callback = on_message_callback
        self._running = False

        self._client = mqtt.Client(
            client_id=cfg.mqtt_client_id,
            callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
        )

        # Optional broker auth
        if cfg.mqtt_username and cfg.mqtt_password:
            self._client.username_pw_set(cfg.mqtt_username, cfg.mqtt_password)

        # Wire paho callbacks
        self._client.on_connect = self._on_connect
        self._client.on_disconnect = self._on_disconnect
        self._client.on_message = self._on_message
        self._client.on_subscribe = self._on_subscribe

        # Automatic reconnect (paho v2 style)
        self._client.reconnect_delay_set(
            min_delay=cfg.mqtt_reconnect_delay_min,
            max_delay=cfg.mqtt_reconnect_delay_max,
        )

    # ── Public API ──────────────────────────────────────────────────────────

    def start(self) -> None:
        """Connect and block in the MQTT network loop."""
        self._running = True
        self._connect()
        _log.info("MQTT loop starting – press Ctrl+C to exit")
        try:
            self._client.loop_forever(retry_first_connection=True)
        except KeyboardInterrupt:
            _log.info("Keyboard interrupt received – stopping MQTT client")
        finally:
            self.stop()

    def stop(self) -> None:
        """Graceful shutdown."""
        self._running = False
        self._client.disconnect()
        self._client.loop_stop()
        _log.info("MQTT client stopped")

    # ── Private helpers ─────────────────────────────────────────────────────

    def _connect(self) -> None:
        host = cfg.mqtt_broker_host
        port = cfg.mqtt_broker_port
        _log.info("Connecting to MQTT broker at %s:%d …", host, port)
        try:
            self._client.connect(host, port, keepalive=cfg.mqtt_keepalive)
        except OSError as exc:
            _log.error(
                "Initial connection to %s:%d failed: %s – will retry",
                host, port, exc,
            )

    # ── paho callbacks ──────────────────────────────────────────────────────

    def _on_connect(
        self,
        client: mqtt.Client,
        userdata,
        connect_flags,
        reason_code,
        properties=None,
    ) -> None:
        if reason_code == 0 or (hasattr(reason_code, "is_failure") and not reason_code.is_failure()):
            _log.info(
                "Connected to broker %s:%d (rc=%s)",
                cfg.mqtt_broker_host, cfg.mqtt_broker_port, reason_code,
            )
            # Re-subscribe on every connect (handles broker restart)
            result, mid = client.subscribe(TOPIC_SENSORS, qos=1)
            _log.debug("Subscribed to '%s' (mid=%s, result=%s)", TOPIC_SENSORS, mid, result)
        else:
            _log.error("Connection refused – reason code: %s", reason_code)

    def _on_disconnect(
        self,
        client: mqtt.Client,
        userdata,
        disconnect_flags,
        reason_code,
        properties=None,
    ) -> None:
        if reason_code == 0:
            _log.info("Cleanly disconnected from broker")
        else:
            _log.warning(
                "Unexpected disconnection (rc=%s) – paho will reconnect automatically",
                reason_code,
            )

    def _on_subscribe(
        self,
        client: mqtt.Client,
        userdata,
        mid,
        reason_code_list,
        properties=None,
    ) -> None:
        _log.info(
            "Subscription confirmed for '%s' (mid=%s, granted QoS=%s)",
            TOPIC_SENSORS, mid, reason_code_list,
        )

    def _on_message(
        self,
        client: mqtt.Client,
        userdata,
        message: mqtt.MQTTMessage,
    ) -> None:
        """
        Receive raw MQTT message.
        - Decode bytes → str → dict.
        - Pass dict to the application callback.
        - Never propagate exceptions; log and continue.
        """
        try:
            raw = message.payload.decode("utf-8")
        except UnicodeDecodeError as exc:
            _log.warning("Cannot decode MQTT payload as UTF-8: %s", exc)
            return

        _log.debug("Raw MQTT message on '%s': %s", message.topic, raw[:200])

        try:
            payload = json.loads(raw)
        except json.JSONDecodeError as exc:
            _log.warning("Malformed JSON on topic '%s': %s | raw=%s", message.topic, exc, raw[:100])
            return

        if not isinstance(payload, dict):
            _log.warning(
                "Expected JSON object, got %s on topic '%s'",
                type(payload).__name__, message.topic,
            )
            return

        try:
            self._callback(payload)
        except Exception as exc:  # pylint: disable=broad-except
            _log.error("Unhandled error in message callback: %s", exc, exc_info=True)
