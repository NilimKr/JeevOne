"""
mqtt/topics.py
==============
Single place that defines all MQTT topic strings.
Import TOPIC_SENSORS (and future topics) from here.
"""

from app.config_loader import cfg

# Primary inbound topic: ESP32 → Raspberry Pi
TOPIC_SENSORS: str = cfg.mqtt_topic_sensors

# Future outbound topics can be added here without touching application logic.
# e.g. TOPIC_COMMANDS = "health/commands"
