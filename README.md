# Personal Health Companion

Privacy-preserving, offline-capable health monitoring pipeline for the Raspberry Pi edge device.

```
Sensors → ESP32 → MQTT → Raspberry Pi → Local Processing → Risk Engine → Local Dashboard
```

## Architecture

- **ESP32**: Sensor acquisition + MQTT publish only
- **Raspberry Pi** (this codebase): complete edge-processing platform — MQTT broker, subscriber, validation, SQLite, risk engines, REST API, dashboard

Internet access is NOT required for core operation.

---

## Quick Start

### 1. Install dependencies

```bash
pip install -r requirements.txt
```

### 2. Install and start Mosquitto broker

**macOS (dev):**
```bash
brew install mosquitto
mkdir -p /tmp/mosquitto_health
/opt/homebrew/opt/mosquitto/sbin/mosquitto -c config/mosquitto.conf -d
```

**Raspberry Pi:**
```bash
sudo apt install mosquitto mosquitto-clients -y
sudo cp config/mosquitto.conf /etc/mosquitto/conf.d/health.conf
sudo systemctl restart mosquitto
```

### 3. Start the processing pipeline + API + Dashboard

```bash
python -m app.main
```

Open `http://localhost:8000` in a browser.

### 4. Run the ESP32 simulator (if hardware is not connected)

```bash
# Normal scenario
python scripts/simulate_esp32.py --scenario normal --interval 2

# Heat-stress test
python scripts/simulate_esp32.py --scenario heat_stress --count 30

# Available scenarios: normal | heat_stress | abnormal_hr | low_spo2 | combined_risk
python scripts/simulate_esp32.py --list
```

---

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/health` | Service liveness check |
| GET | `/api/status` | Pipeline statistics |
| GET | `/api/latest` | Latest reading + risk state |
| GET | `/api/risk` | Risk breakdown |
| GET | `/api/history` | Recent sensor readings (DB) |
| GET | `/api/alerts` | Recent alert history |
| GET | `/api/baseline` | Current personal baseline |
| GET | `/stream` | SSE real-time update stream |

---

## MQTT Topics

| Topic | Direction | Description |
|-------|-----------|-------------|
| `health/sensors` | ESP32 → Pi | Sensor data JSON payload |

### Expected Payload
```json
{
  "device_id": "esp32_01",
  "timestamp": 1727650000,
  "heart_rate": 72,
  "spo2": 98,
  "body_temperature": 36.8,
  "room_temperature": 28.4,
  "humidity": 61.2
}
```

---

## Project Structure

```
personal-health-companion/
├── config/
│   ├── config.yaml          # All tunable parameters (no scattered constants)
│   └── mosquitto.conf       # Broker configuration
├── app/
│   ├── main.py              # Entry point – wires the complete pipeline
│   ├── config_loader.py     # Singleton config access
│   ├── logger.py            # Structured logging setup
│   ├── pipeline_state.py    # Thread-safe shared state (MQTT ↔ API)
│   ├── mqtt/
│   │   ├── client.py        # Robust MQTT client (reconnect, error isolation)
│   │   └── topics.py        # Topic registry
│   ├── ingestion/
│   │   ├── validator.py     # Schema + type + plausibility checks
│   │   ├── normalizer.py    # Raw dict → SensorReading dataclass
│   │   └── processor.py     # validate → normalize pipeline
│   ├── storage/
│   │   ├── database.py      # SQLite engine init (WAL mode)
│   │   ├── models.py        # ORM models (sensor_readings, risk_states)
│   │   └── repository.py    # All DB reads/writes
│   ├── processing/
│   │   ├── filters.py       # Rolling median, moving average, EMA
│   │   ├── windows.py       # Sliding windows for each sensor channel
│   │   ├── features.py      # Derived features (heat index, strain, deviations)
│   │   └── baseline.py      # Slow-EMA personal baseline engine
│   ├── risk/
│   │   ├── heat.py          # Heat-risk indicator (LOW|WATCH|HIGH)
│   │   ├── vital.py         # Vital-signs risk indicator (stateful persistence)
│   │   ├── respiratory.py   # SpO₂-based respiratory risk indicator
│   │   ├── fusion.py        # Combines three engines → overall status
│   │   └── recommendations.py  # Conservative wellness recommendations
│   ├── alerts/
│   │   └── manager.py       # State-change detection + cooldown debouncing
│   └── api/
│       ├── routes.py        # Flask REST API (6 endpoints)
│       └── websocket.py     # SSE real-time stream (/stream)
├── dashboard/
│   ├── templates/index.html # Dark-mode dashboard UI
│   └── static/
│       ├── css/dashboard.css
│       └── js/dashboard.js  # SSE client + canvas sparkline charts
├── scripts/
│   └── simulate_esp32.py   # ESP32 simulator (5 scenarios, dev-only)
├── tests/
│   ├── test_validator.py
│   ├── test_filters.py
│   ├── test_baseline.py
│   └── test_risk_engines.py
├── requirements.txt
├── .env.example
└── .gitignore
```

---

## Configuration

All parameters live in `config/config.yaml`.
Environment variables (from `.env` or shell) override YAML values.

See `.env.example` for the available overrides.

---

## Running Tests

```bash
python -m pytest tests/ -v
```

All 54 tests should pass without a broker connection.

---

## Pipeline

```
MQTT message received
     ↓
validate (schema + types + timestamp + plausibility)
     ↓
normalize → SensorReading dataclass
     ↓
SQLite insert (raw reading)
     ↓
sliding windows updated
     ↓
personal baseline updated (slow EMA, outlier-guarded)
     ↓
feature extraction (heat index, deviations, strain)
     ↓
heat risk engine
vital risk engine
respiratory (SpO₂) risk engine
     ↓
risk fusion → overall status
     ↓
recommendation engine
     ↓
SQLite insert (risk state)
     ↓
shared in-memory state updated
     ↓
alert manager (state-change + cooldown)
     ↓
SSE notification → dashboard
```

---

## Offline Operation

The system requires no internet. All of the following run locally on the Pi:

- Mosquitto MQTT broker
- Python processing pipeline
- SQLite database
- Flask API
- Dashboard

The only external dependency at startup is the Google Fonts CDN link in the dashboard HTML. To make this fully offline, download the fonts and serve them locally.

---

## Important Notes

- **Sensor error ≠ health event.** Malformed/impossible readings are rejected at validation. A bad packet never produces a health alert.
- **Not a medical device.** All risk outputs are wellness monitoring indicators. Language in recommendations is intentionally conservative.
- **Personal baseline** updates slowly (EMA α=0.05) and rejects outliers, so a temporary abnormal period does not corrupt the individual's baseline.
