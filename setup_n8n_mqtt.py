#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Creates n8n MQTT workflow:
  MQTT Trigger (agro/sensors/#) → Code → HTTP POST /api/measurements/direct

Run: python setup_n8n_mqtt.py
"""
import requests, sys
sys.stdout.reconfigure(encoding='utf-8')

N8N_BASE = "http://192.168.0.177:5678"
EMAIL    = "giedrius.pal274@go.kauko.lt"
PASSWORD = "Admin.123"

s = requests.Session()
r = s.post(f"{N8N_BASE}/rest/login",
           json={"emailOrLdapLoginId": EMAIL, "password": PASSWORD})
r.raise_for_status()
print("[OK] Prisijungta")

# ── Create MQTT credential ─────────────────────────────────────────────────────
MQTT_CRED_NAME = "Agro Mosquitto"
r = s.get(f"{N8N_BASE}/rest/credentials")
creds = r.json().get("data", [])
mqtt_cred_id = None
for c in creds:
    if c.get("type") == "mqtt" and "mosquitto" in c.get("name", "").lower():
        mqtt_cred_id = str(c["id"])
        print(f"[OK] MQTT kredencialai rasti (id={mqtt_cred_id})")
        break

if not mqtt_cred_id:
    r = s.post(f"{N8N_BASE}/rest/credentials", json={
        "name": MQTT_CRED_NAME,
        "type": "mqtt",
        "data": {
            "host": "192.168.0.177",
            "port": 1883,
            "protocol": "mqtt",
            "clean": True
        }
    })
    r.raise_for_status()
    mqtt_cred_id = str(r.json()["data"]["id"])
    print(f"[OK] MQTT kredencialai sukurti (id={mqtt_cred_id})")

# ── JavaScript for Code node ───────────────────────────────────────────────────
# Parses MQTT message and forwards to agro-backend /api/measurements/direct
JS_CODE = r"""
const raw = $input.first().json.message;
let body;
try {
  body = typeof raw === 'string' ? JSON.parse(raw) : raw;
} catch(e) {
  return [{ json: { ok: false, error: 'JSON parse failed: ' + String(e) } }];
}

if (!body.unique_id || !body.data) {
  return [{ json: { ok: false, error: 'Missing unique_id or data' } }];
}

return [{ json: body }];
"""

# ── Workflow nodes ─────────────────────────────────────────────────────────────
nodes = [
    {
        "id": "mqtt-1",
        "name": "MQTT Trigger",
        "type": "n8n-nodes-base.mqttTrigger",
        "typeVersion": 1,
        "position": [0, 300],
        "credentials": {
            "mqtt": {"id": mqtt_cred_id, "name": MQTT_CRED_NAME}
        },
        "parameters": {
            "topic": "agro/sensors/#",
            "qos": 0
        }
    },
    {
        "id": "mqtt-2",
        "name": "Parse Payload",
        "type": "n8n-nodes-base.code",
        "typeVersion": 2,
        "position": [220, 300],
        "parameters": {"jsCode": JS_CODE}
    },
    {
        "id": "mqtt-3",
        "name": "Save to DB",
        "type": "n8n-nodes-base.httpRequest",
        "typeVersion": 4.2,
        "position": [440, 300],
        "parameters": {
            "method": "POST",
            "url": "http://agro-backend:8000/api/measurements/direct",
            "sendHeaders": True,
            "headerParameters": {
                "parameters": [
                    {"name": "content-type", "value": "application/json"}
                ]
            },
            "sendBody": True,
            "contentType": "json",
            "bodyParameters": {
                "parameters": [
                    {"name": "unique_id", "value": "={{ $json.unique_id }}"},
                    {"name": "data",      "value": "={{ $json.data }}"}
                ]
            },
            "options": {}
        }
    }
]

connections = {
    "MQTT Trigger":  {"main": [[{"node": "Parse Payload", "type": "main", "index": 0}]]},
    "Parse Payload": {"main": [[{"node": "Save to DB",    "type": "main", "index": 0}]]}
}

workflow = {
    "name": "Agro IoT - Pico W MQTT priemimas",
    "nodes": nodes,
    "connections": connections,
    "active": False,
    "settings": {"executionOrder": "v1"}
}

# ── Create and activate ────────────────────────────────────────────────────────
r = s.post(f"{N8N_BASE}/rest/workflows", json=workflow)
if not r.ok:
    print(f"[!] Klaida: {r.status_code} {r.text[:300]}")
    sys.exit(1)

wf_data   = r.json()["data"]
wf_id     = wf_data["id"]
ver_id    = wf_data.get("versionId", "")
print(f"[OK] Workflow sukurta: id={wf_id}")

r2 = s.post(f"{N8N_BASE}/rest/workflows/{wf_id}/activate",
            json={"versionId": ver_id})
if r2.ok:
    print(f"[OK] Aktyvuota")
else:
    print(f"[!] Aktyvavimas nepavyko: {r2.status_code} {r2.text[:200]}")

print()
print("="*60)
print(f"MQTT workflow id: {wf_id}")
print(f"Broker: 192.168.0.177:1883 (host Mosquitto)")
print(f"Topic:  agro/sensors/#")
print(f"API:    http://agro-backend:8000/api/measurements/direct")
print("="*60)
