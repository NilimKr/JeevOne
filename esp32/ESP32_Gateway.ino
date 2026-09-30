#include <ArduinoJson.h>
#include <PubSubClient.h>
#include <WiFi.h>

// --- WiFi & MQTT Configuration ---
const char *ssid = "Pixel_1811";
const char *password = "bikramhaz";

// The IP address of the Raspberry Pi running the MQTT Broker
const char *mqtt_server = "10.184.234.236";
const int mqtt_port = 1883;

WiFiClient espClient;
PubSubClient client(espClient);

unsigned long lastMsgTime = 0;
const long interval = 5000; // Publish data every 5 seconds

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
    String clientId = "ESP32-HealthGateway-";
    clientId += String(random(0, 0xffff), HEX);

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

  // Initialize your sensors here
  // Wire.begin(); // For I2C (MLX90614, MAX30102)
  // Serial2.begin(9600); // For BP Sensor UART
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

    // 1. Read values from your sensors (Mock values used here for
    // demonstration)
    float temp_body = 37.1;    // Read from MLX90614
    int heart_rate = 75;       // Read from MAX30102
    int spo2 = 98;             // Read from MAX30102
    int bp_sys = 120;          // Read from BP TTL Module
    int bp_dia = 80;           // Read from BP TTL Module
    float temp_ambient = 28.5; // Read from DHT22
    float humidity = 60.0;     // Read from DHT22

    // 2. Create a JSON document to pack the data neatly
    // This makes it extremely easy for the Raspberry Pi Python script to read
    StaticJsonDocument<256> doc;

    doc["device_id"] = "patient_01";
    doc["hr"] = heart_rate;
    doc["spo2"] = spo2;
    doc["temp_body"] = temp_body;

    // Create nested objects for clarity
    JsonObject bp = doc.createNestedObject("blood_pressure");
    bp["sys"] = bp_sys;
    bp["dia"] = bp_dia;

    JsonObject env = doc.createNestedObject("environment");
    env["temp"] = temp_ambient;
    env["humidity"] = humidity;

    // 3. Serialize JSON into a character buffer
    char jsonBuffer[256];
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
        Serial.println("Status: Successfully published to Raspberry Pi!");
        client.publish("health/vitals/patient_01", jsonBuffer);
      } else {
        Serial.println("Status: Waiting for Raspberry Pi MQTT Broker...");
      }
    } else {
      Serial.println("Status: Waiting for Wi-Fi connection...");
    }
  }
}
