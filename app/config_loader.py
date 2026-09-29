"""
config_loader.py
================
Loads config/config.yaml and merges environment variable overrides.
All modules import `cfg` from here – never scatter constants in business logic.
"""

from __future__ import annotations

import os
import logging
from pathlib import Path
from typing import Any

import yaml

_log = logging.getLogger(__name__)

# Resolve project root relative to this file's location: app/ → project root
_PROJECT_ROOT = Path(__file__).parent.parent
_CONFIG_FILE = _PROJECT_ROOT / "config" / "config.yaml"


def _deep_get(d: dict, *keys: str, default: Any = None) -> Any:
    """Safely traverse nested dict."""
    for k in keys:
        if not isinstance(d, dict):
            return default
        d = d.get(k, default)
    return d


class Config:
    """
    Immutable view of the merged YAML + env-var configuration.

    Environment variables (from .env or shell) always win over YAML values.
    Variable names follow the pattern: SECTION_KEY (upper-cased, _ separated).
    Examples:
        MQTT_BROKER_HOST overrides mqtt.broker_host
        DB_PATH          overrides database.path
        API_PORT         overrides api.port
        LOG_LEVEL        overrides logging.level
    """

    def __init__(self) -> None:
        self._raw = self._load_yaml()
        self._apply_env_overrides()

    # ── Public accessors ────────────────────────────────────────────────────

    @property
    def mqtt_broker_host(self) -> str:
        return self._raw["mqtt"]["broker_host"]

    @property
    def mqtt_broker_port(self) -> int:
        return int(self._raw["mqtt"]["broker_port"])

    @property
    def mqtt_topic_sensors(self) -> str:
        return self._raw["mqtt"]["topic_sensors"]

    @property
    def mqtt_client_id(self) -> str:
        return self._raw["mqtt"]["client_id"]

    @property
    def mqtt_username(self) -> str | None:
        return self._raw["mqtt"].get("username") or None

    @property
    def mqtt_password(self) -> str | None:
        return self._raw["mqtt"].get("password") or None

    @property
    def mqtt_keepalive(self) -> int:
        return int(self._raw["mqtt"]["keepalive"])

    @property
    def mqtt_reconnect_delay_min(self) -> int:
        return int(self._raw["mqtt"]["reconnect_delay_min"])

    @property
    def mqtt_reconnect_delay_max(self) -> int:
        return int(self._raw["mqtt"]["reconnect_delay_max"])

    @property
    def db_path(self) -> Path:
        raw = self._raw["database"]["path"]
        p = Path(raw)
        if not p.is_absolute():
            p = _PROJECT_ROOT / p
        return p

    @property
    def api_host(self) -> str:
        return self._raw["api"]["host"]

    @property
    def api_port(self) -> int:
        return int(self._raw["api"]["port"])

    @property
    def log_level(self) -> str:
        return self._raw["logging"]["level"].upper()

    @property
    def log_format(self) -> str:
        return self._raw["logging"]["format"]

    @property
    def filter_window_size(self) -> int:
        return int(self._raw["filters"]["window_size"])

    @property
    def filter_ema_alpha(self) -> float:
        return float(self._raw["filters"]["ema_alpha"])

    @property
    def window_short(self) -> int:
        return int(self._raw["windows"]["short_window"])

    @property
    def window_long(self) -> int:
        return int(self._raw["windows"]["long_window"])

    @property
    def baseline(self) -> dict:
        return self._raw["baseline"]

    @property
    def validation(self) -> dict:
        return self._raw["validation"]

    @property
    def risk(self) -> dict:
        return self._raw["risk"]

    @property
    def alert_cooldown(self) -> int:
        return int(self._raw["alerts"]["cooldown_seconds"])

    # ── Internal helpers ────────────────────────────────────────────────────

    def _load_yaml(self) -> dict:
        if not _CONFIG_FILE.exists():
            raise FileNotFoundError(f"Config file not found: {_CONFIG_FILE}")
        with _CONFIG_FILE.open() as fh:
            data = yaml.safe_load(fh)
        _log.debug("Loaded config from %s", _CONFIG_FILE)
        return data

    def _apply_env_overrides(self) -> None:
        """Merge explicit env-var overrides into the parsed YAML dict."""
        overrides = {
            ("mqtt", "broker_host"):     os.getenv("MQTT_BROKER_HOST"),
            ("mqtt", "broker_port"):     os.getenv("MQTT_BROKER_PORT"),
            ("mqtt", "username"):        os.getenv("MQTT_USERNAME"),
            ("mqtt", "password"):        os.getenv("MQTT_PASSWORD"),
            ("database", "path"):        os.getenv("DB_PATH"),
            ("api", "host"):             os.getenv("API_HOST"),
            ("api", "port"):             os.getenv("API_PORT"),
            ("logging", "level"):        os.getenv("LOG_LEVEL"),
        }
        for (section, key), value in overrides.items():
            if value is not None:
                self._raw.setdefault(section, {})[key] = value
                _log.debug("Env override: %s.%s = %s", section, key, value)


# Singleton – import this everywhere
cfg = Config()
