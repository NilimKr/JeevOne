#!/usr/bin/env python3
"""
scripts/simulate_esp32.py
=========================
Publishes controlled MQTT test payloads to health/sensors.
Use this for development and testing WITHOUT the physical ESP32.

Scenarios:
  normal        – baseline physiology, comfortable room
  heat_stress   – high room temp + humidity, elevated HR and body temp
  abnormal_hr   – isolated elevated heart rate
  low_spo2      – isolated low SpO₂
  combined_risk – multiple simultaneous deviations

Usage:
    python scripts/simulate_esp32.py --scenario normal --interval 2
    python scripts/simulate_esp32.py --scenario heat_stress --count 20

This script is a development utility only.
It is NOT imported by any production code.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
import random
from pathlib import Path

# Allow running from project root
sys.path.insert(0, str(Path(__file__).parent.parent))

import paho.mqtt.client as mqtt

from app.config_loader import cfg

# ── Scenario definitions ──────────────────────────────────────────────────────

SCENARIOS: dict[str, dict] = {
    "normal": {
        "description": "Healthy baseline – comfortable room",
        "heart_rate":       (68, 76),   # (min, max) – random in range
        "spo2":             (97, 99),
        "body_temperature": (36.3, 36.8),
        "room_temperature": (24.0, 26.0),
        "humidity":         (45.0, 55.0),
    },
    "heat_stress": {
        "description": "Heat-stress scenario – hot humid room",
        "heart_rate":       (95, 115),
        "spo2":             (96, 98),
        "body_temperature": (37.5, 38.3),
        "room_temperature": (37.0, 40.0),
        "humidity":         (70.0, 85.0),
    },
    "abnormal_hr": {
        "description": "Isolated elevated heart rate",
        "heart_rate":       (115, 140),
        "spo2":             (97, 99),
        "body_temperature": (36.4, 36.7),
        "room_temperature": (24.0, 26.0),
        "humidity":         (45.0, 55.0),
    },
    "low_spo2": {
        "description": "Isolated low SpO₂",
        "heart_rate":       (68, 80),
        "spo2":             (88, 93),
        "body_temperature": (36.4, 36.7),
        "room_temperature": (24.0, 26.0),
        "humidity":         (45.0, 55.0),
    },
    "combined_risk": {
        "description": "Combined heat + SpO₂ + HR risk",
        "heart_rate":       (110, 135),
        "spo2":             (89, 93),
        "body_temperature": (37.8, 38.5),
        "room_temperature": (38.0, 42.0),
        "humidity":         (75.0, 90.0),
    },
}

DEVICE_ID = "esp32_sim_01"


def rand_in(lo: float, hi: float) -> float:
    return round(random.uniform(lo, hi), 1)


def build_payload(scenario_key: str) -> dict:
    s = SCENARIOS[scenario_key]
    return {
        "device_id": DEVICE_ID,
        "timestamp": int(time.time()),
        "heart_rate":        rand_in(*s["heart_rate"]),
        "spo2":              rand_in(*s["spo2"]),
        "body_temperature":  rand_in(*s["body_temperature"]),
        "room_temperature":  rand_in(*s["room_temperature"]),
        "humidity":          rand_in(*s["humidity"]),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="ESP32 MQTT simulator")
    parser.add_argument(
        "--scenario", "-s",
        choices=list(SCENARIOS.keys()),
        default="normal",
        help="Which scenario to simulate",
    )
    parser.add_argument(
        "--interval", "-i",
        type=float,
        default=2.0,
        help="Seconds between messages (default: 2)",
    )
    parser.add_argument(
        "--count", "-n",
        type=int,
        default=0,
        help="Number of messages to send (0 = unlimited)",
    )
    parser.add_argument(
        "--list", "-l",
        action="store_true",
        help="List available scenarios and exit",
    )
    args = parser.parse_args()

    if args.list:
        print("\nAvailable scenarios:")
        for key, cfg_data in SCENARIOS.items():
            print(f"  {key:20s} – {cfg_data['description']}")
        return

    client = mqtt.Client(
        client_id="esp32_simulator",
        callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
    )

    host = cfg.mqtt_broker_host
    port = cfg.mqtt_broker_port
    topic = cfg.mqtt_topic_sensors

    print(f"Connecting to {host}:{port} …")
    try:
        client.connect(host, port, keepalive=30)
    except Exception as exc:
        print(f"ERROR: Cannot connect to broker: {exc}")
        sys.exit(1)

    client.loop_start()

    print(f"Scenario : {args.scenario} – {SCENARIOS[args.scenario]['description']}")
    print(f"Topic    : {topic}")
    print(f"Interval : {args.interval}s")
    print(f"Count    : {'unlimited' if args.count == 0 else args.count}")
    print("Press Ctrl+C to stop.\n")

    sent = 0
    try:
        while True:
            payload = build_payload(args.scenario)
            msg = json.dumps(payload)
            result = client.publish(topic, msg, qos=1)
            sent += 1
            print(f"[{sent:4d}] Published: {msg}")

            if args.count > 0 and sent >= args.count:
                break

            time.sleep(args.interval)
    except KeyboardInterrupt:
        print("\nStopped.")
    finally:
        client.loop_stop()
        client.disconnect()
        print(f"Total messages sent: {sent}")


if __name__ == "__main__":
    main()
