"""
Agro IoT - MQTT Bridge
Handles two data sources:
  1. ChirpStack LoRaWAN:  +/+/data|join|status  → POST /api/measurements/chirpstack?event=X
  2. Pico W WiFi direct:  agro/sensors/#         → POST /api/measurements/direct
"""
import paho.mqtt.client as mqtt
import requests
import json
import os
import time

MQTT_HOST = os.getenv("MQTT_HOST", "chirpstack-docker-mosquitto-1")
MQTT_PORT = int(os.getenv("MQTT_PORT", "1883"))
API_BASE  = os.getenv("API_BASE",  "http://agro-backend:8000/api")

TOPICS = [
    ("+/+/data",       0),   # ChirpStack UP events
    ("+/+/join",       0),   # ChirpStack JOIN events
    ("+/+/status",     0),   # ChirpStack STATUS events
    ("agro/sensors/#", 0),   # Pico W direct data
]

EVENT_MAP = {"data": "up", "join": "join", "status": "status"}

def on_connect(client, userdata, flags, reason_code, properties):
    if reason_code == 0:
        print(f"[MQTT] Connected to {MQTT_HOST}:{MQTT_PORT}", flush=True)
        for topic, qos in TOPICS:
            client.subscribe(topic, qos)
            print(f"[MQTT] Subscribed: {topic}", flush=True)
    else:
        print(f"[MQTT] Connect failed rc={reason_code}", flush=True)

def on_message(client, userdata, msg):
    topic = msg.topic
    parts = topic.split("/")

    try:
        payload = json.loads(msg.payload.decode("utf-8"))

        if topic.startswith("agro/sensors/"):
            # Pico W WiFi sensor
            r = requests.post(f"{API_BASE}/measurements/direct",
                              json=payload, timeout=10)
            print(f"[Pico]  {topic} → HTTP {r.status_code}", flush=True)

        elif len(parts) == 3 and parts[2] in EVENT_MAP:
            # ChirpStack LoRaWAN device
            event = EVENT_MAP[parts[2]]
            r = requests.post(f"{API_BASE}/measurements/chirpstack?event={event}",
                              json=payload, timeout=10)
            dev = payload.get("deviceInfo", {}).get("deviceName", parts[1])
            print(f"[CS]    {dev} ({event}) → HTTP {r.status_code}", flush=True)

    except json.JSONDecodeError as e:
        print(f"[ERR] {topic}: bad JSON — {e}", flush=True)
    except Exception as e:
        print(f"[ERR] {topic}: {e}", flush=True)

def run():
    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2,
                         client_id="agro-mqtt-bridge", clean_session=True)
    client.on_connect = on_connect
    client.on_message = on_message
    while True:
        try:
            print(f"[MQTT] Connecting to {MQTT_HOST}:{MQTT_PORT}…", flush=True)
            client.connect(MQTT_HOST, MQTT_PORT, keepalive=60)
            client.loop_forever()
        except Exception as e:
            print(f"[MQTT] Error: {e} — retry in 10s", flush=True)
            time.sleep(10)

if __name__ == "__main__":
    run()
