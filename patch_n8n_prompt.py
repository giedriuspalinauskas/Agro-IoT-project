#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import requests, sys, json
sys.stdout.reconfigure(encoding='utf-8')

s = requests.Session()
s.post('http://192.168.0.177:5678/rest/login',
       json={'emailOrLdapLoginId': 'giedrius.pal274@go.kauko.lt', 'password': 'Admin.123'})

NEW_SYS = (
    'Tu esi patyres agronomas-konsultantas. Pateiki praktiskas savaitines rekomendacijas ukininukui lietuviu kalba.' +
    chr(10) + chr(10) +
    'Privalomas formatas - tiksliai 4 rekomendacijos, kiekviena naujoje eiluteje:' + chr(10) +
    '1. **Veiksmazodziu pradedamas trumpas pavadinimas** - Konkretus paaiškinimas su duomenimis' + chr(10) +
    '2. **Veiksmazodziu pradedamas trumpas pavadinimas** - Konkretus paaiškinimas su duomenimis' + chr(10) +
    '3. **Veiksmazodziu pradedamas trumpas pavadinimas** - Konkretus paaiškinimas su duomenimis' + chr(10) +
    '4. **Veiksmazodziu pradedamas trumpas pavadinimas** - Konkretus paaiškinimas su duomenimis' + chr(10) + chr(10) +
    'Draudziama: antrascres su # simboliu, ivadiniai sakiniai, daugiau arba maziau nei 4 rekomendacijos.'
)

# Updated SQL — includes location_type
SQL_LOC_WH = """
SELECT l.id, l.name, l.address, l.latitude, l.longitude,
       COALESCE(l.location_type, 'laukas') AS location_type,
       COALESCE(STRING_AGG(p.name, ', ' ORDER BY p.name), 'Nenurodyta') AS plants
FROM locations l
LEFT JOIN location_plant lp ON l.id = lp.location_id
LEFT JOIN plants p ON lp.plant_id = p.id
WHERE l.id = {{ $json.body.location_id }}
GROUP BY l.id, l.name, l.address, l.latitude, l.longitude, l.location_type
""".strip()

SQL_LOC_SC = """
SELECT DISTINCT l.id, l.name, l.latitude, l.longitude,
       COALESCE(l.location_type, 'laukas') AS location_type,
       COALESCE(STRING_AGG(p.name, ', ' ORDER BY p.name), 'Nenurodyta') AS plants
FROM locations l
JOIN location_plant lp ON l.id = lp.location_id
JOIN plants p ON lp.plant_id = p.id
JOIN devices d ON d.location_id = l.id
JOIN measurement_values mv ON mv.device_id = d.id
WHERE l.latitude IS NOT NULL AND l.longitude IS NOT NULL
GROUP BY l.id, l.name, l.latitude, l.longitude, l.location_type
""".strip()

def make_js(loc_node):
    return r"""
const loc     = $('""" + loc_node + r"""').first().json;
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
    day + ': max ' + d.temperature_2m_max[i] + 'C, min ' + d.temperature_2m_min[i] +
    'C, krituliai ' + d.precipitation_sum[i] + 'mm'
  ).join(nl);
} catch(_) {}

const locType = loc.location_type === 'siltnamis' ? 'Siltnamis' : 'Atviras laukas';

const sys_p = """ + json.dumps(NEW_SYS) + r""";

const usr_p = 'Vieta: ' + loc.name + nl +
  'Vietos tipas: ' + locType + nl +
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

def patch(wf_id, loc_node, sql_loc):
    r = s.get(f'http://192.168.0.177:5678/rest/workflows/{wf_id}')
    wf = r.json()['data']
    was_active = wf['active']

    for node in wf['nodes']:
        if node['name'] == 'Build Prompt':
            node['parameters']['jsCode'] = make_js(loc_node)
            print(f'  Build Prompt patched')
        if node['name'] == 'Get Location' or node['name'] == 'Get All Locations':
            node['parameters']['query'] = sql_loc
            print(f'  SQL patched: {node["name"]}')

    if was_active:
        s.post(f'http://192.168.0.177:5678/rest/workflows/{wf_id}/deactivate')

    r2 = s.patch(f'http://192.168.0.177:5678/rest/workflows/{wf_id}', json={
        'nodes': wf['nodes'], 'connections': wf['connections'],
        'settings': wf['settings'], 'name': wf['name']
    })
    print(f'  PATCH {r2.status_code}')

    if was_active:
        ver = s.get(f'http://192.168.0.177:5678/rest/workflows/{wf_id}').json()['data']['versionId']
        r3 = s.post(f'http://192.168.0.177:5678/rest/workflows/{wf_id}/activate',
                    json={'versionId': ver})
        print(f'  Active: {r3.json()["data"]["active"]}')

print('Webhook workflow...')
patch('rlPOkma2PJeE1wDA', 'Get Location', SQL_LOC_WH)

print('Scheduled workflow...')
patch('YxWLpY0wGXIcyKLE', 'Loop', SQL_LOC_SC)

print('Done.')
