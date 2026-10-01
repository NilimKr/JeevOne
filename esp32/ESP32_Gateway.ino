#include <ArduinoJson.h>
#include <PubSubClient.h>
#include <WiFi.h>
#include <time.h> // NTP-based Unix timestamp

// =============================================================================
// RANDOMISED VITALS MODE
// Simulates realistic sensor output with bounded random values.
// Blood pressure updates every BP_INTERVAL ms (~30 min) since it cannot
// realistically be measured every 10 seconds.
// All other vitals (HR, SpO2, temp, humidity) update every `interval` (10 s).
// MQTT pipeline, JSON field names, and topic are identical to the demo file.
// =============================================================================

// --- WiFi & MQTT Configuration ---
const char *ssid = "Pixel_1811";
const char *password = "bikramhaz";

// The IP address of the Raspberry Pi running the MQTT Broker
const char *mqtt_server = "10.184.234.236";
const int mqtt_port = 1883;

WiFiClient espClient;
PubSubClient client(espClient);

unsigned long lastMsgTime = 0;
const long interval = 10000; // Vitals publish interval: 10 seconds

// --- Blood Pressure: updated every 30 minutes ---
// BP cannot be measured every 10 s; keep last reading and refresh slowly.
const long BP_INTERVAL =
    1800000UL; // 30 min in ms  (change to 3600000UL for 1 hr)
unsigned long lastBPTime = 0 - BP_INTERVAL; // force a reading on first loop
int bp_sys = 118;                           // initial healthy baseline
int bp_dia = 75;

// ---------------------------------------------------------------------------
// randFloat(lo, hi, decimals)
// Returns a float in [lo, hi] rounded to `decimals` decimal places.
// Uses integer random() for portability on ESP32.
// ---------------------------------------------------------------------------
float randFloat(float lo, float hi, int decimals) {
  long scale = 1;
  for (int i = 0; i < decimals; i++)
    scale *= 10;
  long r = random((long)(lo * scale), (long)(hi * scale) + 1);
  return (float)r / scale;
}

// --- NTP Configuration ---
const char *ntp_server = "pool.ntp.org";
const long gmt_offset = 19800; // IST = UTC+5:30
const int dst_offset = 0;

// Returns Unix epoch seconds; 0 if NTP not yet synced
long getTimestamp() {
  struct tm timeinfo;
  if (!getLocalTime(&timeinfo))
    return 0;
  return (long)mktime(&timeinfo);
}

void setup_wifi() {
  delay(10);
  Serial.println();
  Serial.print("Connecting to ");
  Serial.println(ssid);

  WiFi.begin(ssid, password);
  // We removed the blocking 'while' loop here!
  // Now it will try to connect in the background without freezing the sensors.
}

void reconnect() {
  // Try to connect once, but don't get stuck in a while loop!
  if (!client.connected()) {
    Serial.print("Attempting MQTT connection...");
    // Use a fixed, deterministic client ID so the broker doesn't accumulate
    // orphaned sessions every time the ESP32 reconnects.
    String clientId = "ESP32-HealthGateway-1";

    if (client.connect(clientId.c_str())) {
      Serial.println("connected to MQTT!");
      client.publish("health/status", "ESP32 Gateway Online");
    } else {
      Serial.print("failed, rc=");
      Serial.print(client.state());
      Serial.println(" (Will try again later)");
    }
  }
}

void setup() {
  Serial.begin(115200);
  setup_wifi();

  // Set the MQTT Server (The Raspberry Pi's IP)
  client.setServer(mqtt_server, mqtt_port);

  // Seed the random number generator with an unconnected ADC pin for entropy
  randomSeed(analogRead(0));
  Serial.println("[RANDOM VITALS MODE] Sending simulated sensor data.");

  // Wait for WiFi then start NTP sync
  unsigned long wifiWait = millis();
  while (WiFi.status() != WL_CONNECTED && millis() - wifiWait < 10000) {
    delay(500);
    Serial.print(".");
  }
  Serial.println();
  if (WiFi.status() == WL_CONNECTED) {
    configTime(gmt_offset, dst_offset, ntp_server);
    Serial.println("NTP sync started...");
  }
}

void loop() {
  // Only try to handle MQTT if WiFi is connected
  if (WiFi.status() == WL_CONNECTED) {
    if (!client.connected()) {
      // We let the interval timer below handle retries so we don't spam it
    } else {
      client.loop(); // Keeps MQTT connection alive
    }
  }

  unsigned long now = millis();
  if (now - lastMsgTime > interval) {
    lastMsgTime = now;

    // 1. Generate bounded random vital readings (healthy baselines)

    // --- Heart Rate: 60–85 bpm (normal resting range) ---
    int heart_rate = (int)randFloat(60, 85, 0);

    // --- SpO2: 96–99 % (healthy range) ---
    int spo2 = (int)randFloat(96, 99, 0);

    // --- Body Temperature: 36.4–37.4 °C (normal oral range) ---
    float body_temperature = randFloat(36.4, 37.4, 1);

    // --- Room Temperature: 24–32 °C ---
    float room_temperature = randFloat(24.0, 32.0, 1);

    // --- Humidity: 45–70 % RH ---
    float humidity = randFloat(45.0, 70.0, 1);

    // --- Blood Pressure: refresh only every BP_INTERVAL (30 min) ---
    // sys: 108–125 mmHg  |  dia: 62–79 mmHg  (healthy / pre-hypertension
    // boundary)
    if (now - lastBPTime >= BP_INTERVAL) {
      lastBPTime = now;
      bp_sys = (int)randFloat(108, 125, 0);
      bp_dia = (int)randFloat(62, 79, 0); // dia always < 80 (healthy)
      Serial.println("[BP] Reading updated.");
    }

    // 2. Create a JSON document to pack the data neatly
    // This makes it extremely easy for the Raspberry Pi Python script to read
    StaticJsonDocument<512> doc;

    doc["device_id"] = "patient_01";
    doc["timestamp"] = getTimestamp(); // Unix epoch seconds (IST)
    doc["heart_rate"] = heart_rate;
    doc["spo2"] = spo2;
    doc["body_temperature"] = body_temperature;
    doc["room_temperature"] = room_temperature; // flat — no nested env object
    doc["humidity"] = humidity;                 // flat — no nested env object

    // blood_pressure stays nested (sys/dia are paired values)
    JsonObject bp = doc.createNestedObject("blood_pressure");
    bp["sys"] = bp_sys;
    bp["dia"] = bp_dia;

    // 3. Serialize JSON into a character buffer
    char jsonBuffer[512];
    serializeJson(doc, jsonBuffer);

    // 4. Print to Serial Monitor NO MATTER WHAT (Even without WiFi)
    Serial.println();
    Serial.println("--- SENSOR READINGS ---");
    Serial.println(jsonBuffer);

    // 5. Try to publish if Wi-Fi and MQTT are connected
    if (WiFi.status() == WL_CONNECTED) {
      if (!client.connected()) {
        reconnect();
      }

      if (client.connected()) {
        bool ok = client.publish("health/sensors", jsonBuffer);
        Serial.println(ok ? "Status: Published to RPi [health/sensors] ✓"
                          : "Status: Publish failed (buffer full?)");
      } else {
        Serial.println("Status: Waiting for Raspberry Pi MQTT Broker...");
      }
    } else {
      Serial.println("Status: Waiting for Wi-Fi connection...");
    }
  }
}