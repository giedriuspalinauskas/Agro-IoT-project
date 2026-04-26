#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
n8n workflow setup for Agro IoT recommendations.
Creates two workflows:
  1. Manual webhook  — triggered by button in UI
  2. Weekly schedule — every Sunday at 18:00

Usage: python setup_n8n.py
"""
import requests
import json
import sys
sys.stdout.reconfigure(encoding='utf-8')

N8N_BASE  = "http://192.168.0.177:5678"
EMAIL     = "giedrius.pal274@go.kauko.lt"
PASSWORD  = "Admin.123"
OLD_WF_ID = "fvisIBpeJtufxrm3"

# ── Login ──────────────────────────────────────────────────────────────────
s = requests.Session()
r = s.post(f"{N8N_BASE}/rest/login", json={"emailOrLdapLoginId": EMAIL, "password": PASSWORD})
r.raise_for_status()
print("[OK] Prisijungta prie n8n")

# ── Extract Claude API key from old workflow ───────────────────────────────
claude_key = None
try:
    r = s.get(f"{N8N_BASE}/rest/workflows/{OLD_WF_ID}")
    if r.ok:
        nodes = r.json()["data"]["nodes"]
        for node in nodes:
            for h in node.get("parameters", {}).get("headerParameters", {}).get("parameters", []):
                if h.get("name") == "x-api-key" and h.get("value", "").startswith("sk-"):
                    claude_key = h["value"]
                    break
            if claude_key:
                break
        if claude_key:
            print(f"[OK] Claude API raktas rastas: {claude_key[:20]}...")
        else:
            print("! Claude API raktas nerastas senoje workflow")
except Exception as e:
    print(f"! Nepavyko nuskaityti senos workflow: {e}")

if not claude_key:
    claude_key = input("Iveskite Claude API rakta (sk-ant-...): ").strip()
    if not claude_key:
        sys.exit("Claude API raktas butinas")

# ── Create / find PostgreSQL credential ───────────────────────────────────
PG_CRED_NAME = "Agro IoT DB"
r = s.get(f"{N8N_BASE}/rest/credentials")
creds = r.json().get("data", [])
pg_cred_id = None
for c in creds:
    if c.get("type") == "postgres" and "agro" in c.get("name", "").lower():
        pg_cred_id = str(c["id"])
        PG_CRED_NAME = c["name"]
        print(f"[OK] PostgreSQL kredencialai rasti (id={pg_cred_id})")
        break

if not pg_cred_id:
    r = s.post(f"{N8N_BASE}/rest/credentials", json={
        "name": PG_CRED_NAME,
        "type": "postgres",
        "data": {
            "host": "n8n-postgres",
            "port": 5432,
            "database": "agro_iot",
            "user": "agro_user",
            "password": "agropass",
            "ssl": "disable"
        }
    })
    r.raise_for_status()
    pg_cred_id = str(r.json()["data"]["id"])
    print(f"[OK] PostgreSQL kredencialai sukurti (id={pg_cred_id})")

# ── Helper: PostgreSQL node ────────────────────────────────────────────────
def pg_node(uid, name, sql, x, y):
    return {
        "id": uid, "name": name,
        "type": "n8n-nodes-base.postgres",
        "typeVersion": 2.4,
        "position": [x, y],
        "parameters": {
            "operation": "executeQuery",
            "query": sql,
            "options": {}
        },
        "credentials": {
            "postgres": {"id": pg_cred_id, "name": PG_CRED_NAME}
        }
    }

# ── Helper: HTTP Request node ──────────────────────────────────────────────
def http_node(uid, name, method, url_expr, extra_params, x, y):
    node = {
        "id": uid, "name": name,
        "type": "n8n-nodes-base.httpRequest",
        "typeVersion": 4.2,
        "position": [x, y],
        "parameters": {"method": method, "url": url_expr, "options": {}}
    }
    node["parameters"].update(extra_params)
    return node

# ── SQL / JS code strings ──────────────────────────────────────────────────

SQL_LOC_BY_ID = """
SELECT l.id, l.name, l.address, l.latitude, l.longitude,
       COALESCE(STRING_AGG(p.name, ', ' ORDER BY p.name), 'Nenurodyta') AS plants
FROM locations l
LEFT JOIN location_plant lp ON l.id = lp.location_id
LEFT JOIN plants p ON lp.plant_id = p.id
WHERE l.id = {{ $json.body.location_id }}
GROUP BY l.id, l.name, l.address, l.latitude, l.longitude
""".strip()

SQL_SENSORS_BY_LOC = """
SELECT DISTINCT ON (dfm.display_name)
       dfm.display_name AS field, dfm.unit,
       mv.field_value AS value, mv.received_at
FROM measurement_values mv
JOIN devices d ON d.id = mv.device_id
JOIN device_field_mapping dfm
     ON dfm.device_id = d.id AND dfm.source_field = mv.field_key
WHERE d.location_id = {{ $('Get Location').first().json.id }}
ORDER BY dfm.display_name, mv.received_at DESC
""".strip()

SQL_ALL_LOCS = """
SELECT DISTINCT l.id, l.name, l.latitude, l.longitude,
       COALESCE(STRING_AGG(p.name, ', ' ORDER BY p.name), 'Nenurodyta') AS plants
FROM locations l
JOIN location_plant lp ON l.id = lp.location_id
JOIN plants p ON lp.plant_id = p.id
JOIN devices d ON d.location_id = l.id
JOIN measurement_values mv ON mv.device_id = d.id
WHERE l.latitude IS NOT NULL AND l.longitude IS NOT NULL
GROUP BY l.id, l.name, l.latitude, l.longitude
""".strip()

SQL_SENSORS_LOOP = """
SELECT DISTINCT ON (dfm.display_name)
       dfm.display_name AS field, dfm.unit,
       mv.field_value AS value, mv.received_at
FROM measurement_values mv
JOIN devices d ON d.id = mv.device_id
JOIN device_field_mapping dfm
     ON dfm.device_id = d.id AND dfm.source_field = mv.field_key
WHERE d.location_id = {{ $('Loop').first().json.id }}
ORDER BY dfm.display_name, mv.received_at DESC
""".strip()

# JavaScript: build prompt (webhook variant — location from 'Get Location')
JS_BUILD_PROMPT_WH = r"""
const loc     = $('Get Location').first().json;
const sensors = $('Get Sensors').all().map(i => i.json);
const weather = $('Get Weather').first().json;
const nl      = String.fromCharCode(10);

let sensorText = sensors.length
  ? sensors.map(s => s.field + ': ' + parseFloat(s.value || 0).toFixed(1) + ' ' + (s.unit || '')).join(nl)
  : 'Jutikliu duomenys nepasiekiami';

let weatherText = 'Oru duomenys nepasiekiami';
try {
  const d = weather.daily;
  weatherText = d.time.slice(0, 7).map((day, i) =>
    day + ': max ' + d.temperature_2m_max[i] + '°C, min ' + d.temperature_2m_min[i] +
    '°C, krituliai ' + d.precipitation_sum[i] + 'mm'
  ).join(nl);
} catch(_) {}

const sys_p = 'Tu esi patyres agronomas-konsultantas. Pateiki praktiskas savaitines rekomendacijas ukininukui lietuviu kalba.' + nl + nl +
  'Privalomas formatas - tiksliai 4 rekomendacijos, kiekviena naujoje eiluteje:' + nl +
  '1. **Veiksmazodziu pradedamas trumpas pavadinimas** - Konkretus paaiškinimas su duomenimis' + nl +
  '2. **Veiksmazodziu pradedamas trumpas pavadinimas** - Konkretus paaiškinimas su duomenimis' + nl +
  '3. **Veiksmazodziu pradedamas trumpas pavadinimas** - Konkretus paaiškinimas su duomenimis' + nl +
  '4. **Veiksmazodziu pradedamas trumpas pavadinimas** - Konkretus paaiškinimas su duomenimis' + nl + nl +
  'Draudziama: antrascres su # simboliu, ivadiniai sakiniai, daugiau arba maziau nei 4 rekomendacijos.';

const usr_p = 'Vieta: ' + loc.name + nl +
  'Auginami augalai: ' + (loc.plants || 'Nenurodyta') + nl + nl +
  'Jutikliu duomenys:' + nl + sensorText + nl + nl +
  '7 dienu oru prognoze:' + nl + weatherText;

const claude_body = JSON.stringify({
  model: 'claude-haiku-4-5-20251001',
  max_tokens: 1024,
  system: sys_p,
  messages: [{ role: 'user', content: usr_p }]
});

return [{ json: { claude_body, locationId: loc.id } }];
"""

# JavaScript: build prompt (scheduled variant — location from 'Loop')
JS_BUILD_PROMPT_SC = r"""
const loc     = $('Loop').first().json;
const sensors = $('Get Sensors').all().map(i => i.json);
const weather = $('Get Weather').first().json;
const nl      = String.fromCharCode(10);

let sensorText = sensors.length
  ? sensors.map(s => s.field + ': ' + parseFloat(s.value || 0).toFixed(1) + ' ' + (s.unit || '')).join(nl)
  : 'Jutikliu duomenys nepasiekiami';

let weatherText = 'Oru duomenys nepasiekiami';
try {
  const d = weather.daily;
  weatherText = d.time.slice(0, 7).map((day, i) =>
    day + ': max ' + d.temperature_2m_max[i] + '°C, min ' + d.temperature_2m_min[i] +
    '°C, krituliai ' + d.precipitation_sum[i] + 'mm'
  ).join(nl);
} catch(_) {}

const sys_p = 'Tu esi patyres agronomas-konsultantas. Pateiki praktiskas savaitines rekomendacijas ukininukui lietuviu kalba.' + nl + nl +
  'Privalomas formatas - tiksliai 4 rekomendacijos, kiekviena naujoje eiluteje:' + nl +
  '1. **Veiksmazodziu pradedamas trumpas pavadinimas** - Konkretus paaiškinimas su duomenimis' + nl +
  '2. **Veiksmazodziu pradedamas trumpas pavadinimas** - Konkretus paaiškinimas su duomenimis' + nl +
  '3. **Veiksmazodziu pradedamas trumpas pavadinimas** - Konkretus paaiškinimas su duomenimis' + nl +
  '4. **Veiksmazodziu pradedamas trumpas pavadinimas** - Konkretus paaiškinimas su duomenimis' + nl + nl +
  'Draudziama: antrascres su # simboliu, ivadiniai sakiniai, daugiau arba maziau nei 4 rekomendacijos.';

const usr_p = 'Savaitine apzvalga.' + nl +
  'Vieta: ' + loc.name + nl +
  'Auginami augalai: ' + (loc.plants || 'Nenurodyta') + nl + nl +
  'Jutikliu duomenys:' + nl + sensorText + nl + nl +
  '7 dienu oru prognoze:' + nl + weatherText;

const claude_body = JSON.stringify({
  model: 'claude-haiku-4-5-20251001',
  max_tokens: 1024,
  system: sys_p,
  messages: [{ role: 'user', content: usr_p }]
});

return [{ json: { claude_body, locationId: loc.id, locationName: loc.name } }];
"""

# JavaScript: extract Claude response and build INSERT SQL
JS_EXTRACT = r"""
const resp      = $input.first().json;
const content   = (resp.content && resp.content[0]) ? resp.content[0].text : 'Klaida generuojant rekomendacijas';
const locationId = $('Build Prompt').first().json.locationId;
const escaped   = content.replace(/'/g, "''");
const sql       = "INSERT INTO recommendations (location_id, content) VALUES (" + locationId + ", '" + escaped + "') RETURNING id";
return [{ json: { content, locationId, sql } }];
"""

CLAUDE_HEADERS = [
    {"name": "x-api-key",          "value": claude_key},
    {"name": "anthropic-version",  "value": "2023-06-01"},
    {"name": "content-type",       "value": "application/json"}
]

CLAUDE_BODY_PARAMS = {
    "sendHeaders": True,
    "headerParameters": {"parameters": CLAUDE_HEADERS},
    "sendBody": True,
    "contentType": "raw",
    "rawContentType": "application/json",
    "body": "={{ $json.claude_body }}"
}

def weather_url(lat_expr, lon_expr):
    return (
        "={{ '" +
        "https://api.open-meteo.com/v1/forecast" +
        "?latitude=' + " + lat_expr +
        " + '&longitude=' + " + lon_expr +
        " + '&daily=temperature_2m_max,temperature_2m_min,precipitation_sum,weathercode" +
        "&timezone=Europe%2FVilnius&forecast_days=7' }}"
    )

# ═══════════════════════════════════════════════════════════════════════════
#  WORKFLOW 1 — Manual webhook
# ═══════════════════════════════════════════════════════════════════════════

wh_nodes = [
    {
        "id": "wh-1", "name": "Webhook",
        "type": "n8n-nodes-base.webhook",
        "typeVersion": 1,
        "position": [0, 300],
        "webhookId": "agro-rec-prod-001",
        "parameters": {
            "path": "agro-recommendations",
            "httpMethod": "POST",
            "responseMode": "responseNode"
        }
    },
    pg_node("wh-2", "Get Location", SQL_LOC_BY_ID, 220, 300),
    pg_node("wh-3", "Get Sensors",  SQL_SENSORS_BY_LOC, 440, 300),
    http_node("wh-4", "Get Weather", "GET",
              weather_url(
                  "$('Get Location').first().json.latitude",
                  "$('Get Location').first().json.longitude"
              ), {}, 660, 300),
    {
        "id": "wh-5", "name": "Build Prompt",
        "type": "n8n-nodes-base.code",
        "typeVersion": 2,
        "position": [880, 300],
        "parameters": {"jsCode": JS_BUILD_PROMPT_WH}
    },
    http_node("wh-6", "Call Claude", "POST",
              "https://api.anthropic.com/v1/messages",
              CLAUDE_BODY_PARAMS, 1100, 300),
    {
        "id": "wh-7", "name": "Extract Response",
        "type": "n8n-nodes-base.code",
        "typeVersion": 2,
        "position": [1320, 300],
        "parameters": {"jsCode": JS_EXTRACT}
    },
    pg_node("wh-8", "Save Recommendation", "={{ $json.sql }}", 1540, 300),
    {
        "id": "wh-9", "name": "Respond",
        "type": "n8n-nodes-base.respondToWebhook",
        "typeVersion": 1,
        "position": [1760, 300],
        "parameters": {
            "respondWith": "json",
            "responseBody": "={{ {ok: true, id: $('Save Recommendation').first().json.id} }}"
        }
    }
]

wh_connections = {
    "Webhook":           {"main": [[{"node": "Get Location",       "type": "main", "index": 0}]]},
    "Get Location":      {"main": [[{"node": "Get Sensors",        "type": "main", "index": 0}]]},
    "Get Sensors":       {"main": [[{"node": "Get Weather",        "type": "main", "index": 0}]]},
    "Get Weather":       {"main": [[{"node": "Build Prompt",       "type": "main", "index": 0}]]},
    "Build Prompt":      {"main": [[{"node": "Call Claude",        "type": "main", "index": 0}]]},
    "Call Claude":       {"main": [[{"node": "Extract Response",   "type": "main", "index": 0}]]},
    "Extract Response":  {"main": [[{"node": "Save Recommendation","type": "main", "index": 0}]]},
    "Save Recommendation":{"main": [[{"node": "Respond",           "type": "main", "index": 0}]]}
}

webhook_workflow = {
    "name": "Agro IoT - Rekomendacijos (rankinis)",
    "nodes": wh_nodes,
    "connections": wh_connections,
    "active": False,
    "settings": {"executionOrder": "v1"}
}

# ═══════════════════════════════════════════════════════════════════════════
#  WORKFLOW 2 — Weekly schedule (every Sunday 18:00)
# ═══════════════════════════════════════════════════════════════════════════

sc_nodes = [
    {
        "id": "sc-1", "name": "Schedule",
        "type": "n8n-nodes-base.scheduleTrigger",
        "typeVersion": 1.1,
        "position": [0, 300],
        "parameters": {
            "rule": {
                "interval": [{"field": "cronExpression", "expression": "0 18 * * 0"}]
            }
        }
    },
    pg_node("sc-2", "Get All Locations", SQL_ALL_LOCS, 220, 300),
    {
        "id": "sc-3", "name": "Loop",
        "type": "n8n-nodes-base.splitInBatches",
        "typeVersion": 3,
        "position": [440, 300],
        "parameters": {"batchSize": 1, "options": {}}
    },
    pg_node("sc-4", "Get Sensors", SQL_SENSORS_LOOP, 660, 300),
    http_node("sc-5", "Get Weather", "GET",
              weather_url(
                  "$('Loop').first().json.latitude",
                  "$('Loop').first().json.longitude"
              ), {}, 880, 300),
    {
        "id": "sc-6", "name": "Build Prompt",
        "type": "n8n-nodes-base.code",
        "typeVersion": 2,
        "position": [1100, 300],
        "parameters": {"jsCode": JS_BUILD_PROMPT_SC}
    },
    http_node("sc-7", "Call Claude", "POST",
              "https://api.anthropic.com/v1/messages",
              CLAUDE_BODY_PARAMS, 1320, 300),
    {
        "id": "sc-8", "name": "Extract Response",
        "type": "n8n-nodes-base.code",
        "typeVersion": 2,
        "position": [1540, 300],
        "parameters": {"jsCode": JS_EXTRACT}
    },
    pg_node("sc-9", "Save Recommendation", "={{ $json.sql }}", 1760, 300)
]

sc_connections = {
    "Schedule":          {"main": [[{"node": "Get All Locations",  "type": "main", "index": 0}]]},
    "Get All Locations": {"main": [[{"node": "Loop",               "type": "main", "index": 0}]]},
    # Loop output[0]=loop branch, output[1]=done branch
    "Loop": {"main": [
        [{"node": "Get Sensors", "type": "main", "index": 0}],
        []
    ]},
    "Get Sensors":       {"main": [[{"node": "Get Weather",        "type": "main", "index": 0}]]},
    "Get Weather":       {"main": [[{"node": "Build Prompt",       "type": "main", "index": 0}]]},
    "Build Prompt":      {"main": [[{"node": "Call Claude",        "type": "main", "index": 0}]]},
    "Call Claude":       {"main": [[{"node": "Extract Response",   "type": "main", "index": 0}]]},
    "Extract Response":  {"main": [[{"node": "Save Recommendation","type": "main", "index": 0}]]},
    # Loop-back: last processing node feeds back into Loop
    "Save Recommendation": {"main": [[{"node": "Loop",             "type": "main", "index": 0}]]}
}

scheduled_workflow = {
    "name": "Agro IoT - Rekomendacijos (savaitinis, sekmadienis 18:00)",
    "nodes": sc_nodes,
    "connections": sc_connections,
    "active": False,
    "settings": {"executionOrder": "v1"}
}

# ── Create and activate ────────────────────────────────────────────────────

def create_and_activate(wf_def):
    r = s.post(f"{N8N_BASE}/rest/workflows", json=wf_def)
    if not r.ok:
        print(f"  ! Klaida kuriant workflow: {r.status_code} {r.text[:300]}")
        return None
    data = r.json()["data"]
    wf_id      = data["id"]
    version_id = data.get("versionId", "")
    print(f"  Sukurta: id={wf_id}")

    r2 = s.post(f"{N8N_BASE}/rest/workflows/{wf_id}/activate",
                json={"versionId": version_id})
    if r2.ok:
        print(f"  Aktyvuota.")
    else:
        print(f"  ! Nepavyko aktyvuoti: {r2.status_code} {r2.text[:200]}")
    return wf_id

print("\n[1/2] Rankinio webhook workflow...")
wh_id = create_and_activate(webhook_workflow)

print("\n[2/2] Savaitinio schedule workflow...")
sc_id = create_and_activate(scheduled_workflow)

# ── Delete old workflow ────────────────────────────────────────────────────
print(f"\nTriname sena workflow {OLD_WF_ID}...")
s.post(f"{N8N_BASE}/rest/workflows/{OLD_WF_ID}/deactivate")
s.post(f"{N8N_BASE}/rest/workflows/{OLD_WF_ID}/archive")
r = s.delete(f"{N8N_BASE}/rest/workflows/{OLD_WF_ID}")
print(f"  Rezultatas: {r.status_code}" + (" (nerasta)" if r.status_code == 404 else ""))

# ── Summary ───────────────────────────────────────────────────────────────
print("\n" + "="*60)
print("BAIGTA")
print(f"  Rankinis webhook : n8n workflow id={wh_id}")
print(f"  Savaitinis       : n8n workflow id={sc_id}")
print(f"  Webhook URL      : http://192.168.0.177:5678/webhook/agro-recommendations")
print("="*60)
