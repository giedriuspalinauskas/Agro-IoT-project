# Agro IoT — Žemės ūkio jutiklių stebėjimo sistema

Baigiamojo darbo projektas. Žemės ūkio paskirties IoT platforma, leidžianti realiuoju laiku stebėti aplinkos parametrus (temperatūrą, drėgmę, CO₂, slėgį, dirvožemio drėgmę) keliose žemės vietose, gauti AI generuojamas agronomines rekomendacijas ir vizualizuoti duomenis Grafana aplinkoje.

---

## Sistemos architektūra

```
LoRaWAN jutikliai          WiFi jutikliai
(Milesight, Dragino)       (Raspberry Pi Pico W)
        │                          │
        ▼                          ▼
  Dragino Gateway           MQTT publikavimas
  (LoRa → IP)               agro/sensors/#
        │                          │
        ▼                          │
  ChirpStack                       │
  (LoRaWAN serveris)               │
        │                          │
        └──────────┬───────────────┘
                   ▼
          Mosquitto MQTT Broker
          (192.168.0.177:1883)
                   │
                   ▼
          agro-mqtt-bridge
          (Docker konteineris)
         /          \
        ▼            ▼
  /chirpstack     /direct
  (LoRaWAN)      (Pico W)
        │            │
        └─────┬──────┘
              ▼
        FastAPI Backend
        (agro-backend:8000)
              │
              ▼
        PostgreSQL
        (agro_iot duomenų bazė)
         /         \
        ▼            ▼
  Nginx             n8n
  (Web UI)   (Automatizavimas)
                     │
              ┌──────┴──────┐
              ▼             ▼
         Open-Meteo     Claude AI
         (Orai)      (Rekomendacijos)
              └──────┬──────┘
                     ▼
                PostgreSQL
             (įrašo rekomendacijas)

  PostgreSQL ─────► Grafana
                  (vizualizacija)
```

---

## Komponentai

### Infrastruktūra (Raspberry Pi 5 — 192.168.0.177)

| Konteineris | Aprašymas | Prieiga |
|---|---|---|
| `agro-web` | Nginx — statinis frontend | :8081 |
| `agro-backend` | FastAPI REST API | :8002 |
| `agro-mqtt-bridge` | MQTT → API tiltas | vidinis |
| `n8n-postgres` | PostgreSQL (bendra DB) | :5432 |
| `n8n` | n8n workflow automatizavimas | :5678 |
| `grafana` | Grafana vizualizacija | :3000 |

### ChirpStack serveris (192.168.0.186)

| Konteineris | Aprašymas | Prieiga |
|---|---|---|
| `chirpstack` | ChirpStack v4 LoRaWAN serveris | :8080 (UI), :8090 (API) |
| `chirpstack-gateway-bridge` | Gateway tiltas | :1700 UDP |
| `chirpstack-mosquitto` | MQTT brokeris | :1883 |

### Fiziniai įrenginiai

| Įrenginys | Ryšio tipas | Matuojami parametrai |
|---|---|---|
| Milesight EM500-TH | LoRaWAN | Temperatūra (°C) |
| Milesight EM500-CO2 | LoRaWAN | CO₂ (ppm), temperatūra, drėgmė, slėgis (hPa) |
| Dragino Leaf | LoRaWAN | Lapo drėgmė (%), oro drėgmė (%), temperatūra, baterija |
| Raspberry Pi Pico W | WiFi / MQTT | Konfigūruojami jutikliai |
| Dragino Gateway | LoRa → Ethernet | LoRaWAN paketų persiuntimas |

---

## Technologijos

### Backend
- **Python 3.11** + **FastAPI** — REST API
- **SQLAlchemy** — ORM duomenų bazei
- **PostgreSQL** — duomenų saugojimas
- **JWT** — autentifikacija (8h sesija vartotojams, 1m. paslaugų žetonai)
- **Docker** + **Docker Compose** — konteinerizacija

### Frontend
- Vieno failo **SPA** (HTML + CSS + vanilla JavaScript)
- Responsive dizainas (mobilus + stalinis)
- Nginx statinis serveris

### IoT duomenų srautas
- **LoRaWAN** — ilgo nuotolio belaidis ryšys mažos galios jutikliams
- **ChirpStack v4** — LoRaWAN tinklo serveris (dekoduoja paketus, tvarko įrenginius)
- **MQTT** — lengvas žinučių protokolas IoT įrenginiams
- **Mosquitto** — MQTT brokeris
- **agro-mqtt-bridge** — Python Paho-MQTT klientas, peradresuoja MQTT žinutes į REST API
- **MicroPython** — programavimo kalba Pico W

### Automatizavimas ir AI
- **n8n** — vizualinis workflow automatizavimas
- **Claude AI** (claude-haiku-4-5-20251001, Anthropic) — AI agronominis konsultantas
- **Open-Meteo API** — nemokama 7 dienų orų prognozė pagal koordinates

### Vizualizacija
- **Grafana** — realaus laiko dashboardai su SQL užklausomis į PostgreSQL

---

## Duomenų srautas

### LoRaWAN jutikliai (Milesight, Dragino)
1. Jutiklis siunčia LoRa radijo paketą → Dragino LoRaWAN gateway
2. Gateway perduoda paketą → ChirpStack serveris (192.168.0.186)
3. ChirpStack dekoduoja ir publikuoja į MQTT temą: `{gateway_id}/{devEui}/data`
4. `agro-mqtt-bridge` prenumeruoja `+/+/data` ir siunčia `POST /api/measurements/chirpstack?event=up`
5. Backend identifikuoja įrenginį pagal DevEUI, išsaugo `device_events` (raw duomenys) ir `measurement_values` (pagal laukų mapingus)
6. **Timestamp** imamas iš ChirpStack `time` lauko — tikras nuskaitymo momentas, ne serverio gavimo laikas

### Pico W (WiFi jutiklis su buferizavimu)
1. Pico W matuoja jutiklius kas N sekundžių (nustatoma `READ_INTERVAL`)
2. Jei WiFi ir MQTT pasiekiami → publikuoja `agro/sensors/{device_uid}` JSON formatu
3. Jei ryšys nutrūkęs → duomenys kaupiami RAM buferyje (iki 200 rodmenų), perkrovus — flash atmintyje (`/buffer.json`)
4. Ryšiui atsinaujinus → pirmiausia išsiunčiamas visas buferis chronologine tvarka, tada dabartinis rodmuo
5. `agro-mqtt-bridge` prenumeruoja `agro/sensors/#` → `POST /api/measurements/direct`
6. **Timestamp** imamas iš Pico W `ts` lauko — Unix laikas nuskaitymo momento

### AI rekomendacijos
1. Vartotojas spaudžia „🤖 Generuoti" rekomendacijų puslapyje **arba** automatiškai kiekvieną sekmadienį 18:00
2. n8n SQL užklausa → gauna vietos informaciją: pavadinimas, tipas (šiltnamis/laukas), augalai, koordinatės
3. n8n SQL užklausa → gauna naujausius jutiklių rodmenis su vienetais
4. HTTP užklausa → Open-Meteo API (7 dienų prognozė: min/max temperatūra, krituliai)
5. Suformuojamas prompt Claude AI su visa kontekstine informacija
6. Claude AI grąžina **4 lietuviškas rekomendacijas** formatu: `1. **Veiksmas** — detalus paaiškinimas su duomenimis`
7. n8n įrašo į PostgreSQL `recommendations` lentelę
8. UI rodo rekomendacijas su žalia žiedinė numeracija

---

## Sistemos funkcionalumas

### Žemės vietos
- Dviejų tipų: **🌾 Atviras laukas** arba **🏠 Šiltnamis** (AI atsižvelgia į tipą)
- Adresas su automatinėmis GPS koordinatėmis (Nominatim geocoding)
- Auginami augalai — pasirenkama iš sąrašo su paieška (31 augalas)
- Priskirti vartotojai — prieigos valdymas (vartotojas mato tik savo vietas)

### Įrenginiai
- Importas iš ChirpStack pagal DevEUI su automatinio atpažinimu
- Rankinis pridėjimas su unikaliu ID
- **Laukų mapingas** — nurodoma kuris jutiklio laukas ką reiškia (pvz. `leaf_moisture` → Dirvožemio drėgmė, %)
- Automatinis laukų aptikimas iš paskutinio gauto paketo (net jei reikšmės string tipo)
- Keičiant žemės vietą — automatiškai išvalomi istoriniai duomenys (jutiklis pradeda kaupti iš naujo)
- Jutiklių tipai: 🌡 Temperatūra · 💧 Drėgmė · 🌫 CO₂ · 🔵 Slėgis · 🌱 Dirvožemis · 🌧 Lietus · 📡 Kitas

### Vartotojai
- **Administratorius** — pilna prieiga prie visų vietų, įrenginių, vartotojų valdymo
- **Paprastas vartotojas** — mato ir stebi tik jam priskirtas žemės vietas
- JWT autentifikacija su bcrypt slaptažodžių šifravimu

### Rekomendacijos
- Generavimas mygtuku konkrečiai vietai
- Savaitinis automatinis generavimas visoms vietoms su jutikliais ir augalais
- Peržiūros istorija kiekvienai vietai
- Validacija prieš generavimą: tikrina ar yra koordinatės, augalai, jutiklių duomenys

---

## Diegimas

### Reikalavimai
- Raspberry Pi su Debian Linux (arm64)
- Docker + Docker Compose
- SSH prieiga

### Deploy komanda (iš lokalaus kompiuterio)
```bash
bash deploy.sh
```

Skriptas supakuoja projektą su `tar`, perduoda per SSH, vykdo `docker compose up -d --build`.

### n8n workflow kūrimas
```bash
python setup_n8n.py        # Rekomendacijų workflows (rankinis + savaitinis)
python setup_n8n_mqtt.py   # MQTT workflow (jei reikalinga)
```

---

## Konfigūracija

**Duomenų bazė** (`docker-compose.yml`):
```
DATABASE_URL: postgresql://agro_user:agropass@n8n-postgres:5432/agro_iot
```

**MQTT Bridge** (`docker-compose.yml`):
```
MQTT_HOST: chirpstack-docker-mosquitto-1
MQTT_PORT: 1883
API_BASE:  http://agro-backend:8000/api
```

**ChirpStack** (`backend/routers/devices.py`):
```python
CHIRPSTACK_URL    = "http://192.168.0.186:8090"
CHIRPSTACK_APP_ID = "d0168e14-67a4-45e0-a8fa-f2f19636b5fc"
```

**Pico W** (`pico_station/main.py`):
```python
WIFI_SSID     = "jūsų_wifi_pavadinimas"
WIFI_PASSWORD = "slaptažodis"
DEVICE_UID    = "pico-001"   # turi sutapti su unique_id Agro IoT sistemoje
READ_INTERVAL = 60           # sekundės tarp matavimų
MAX_RAM_BUF   = 200          # max rodmenų RAM buferyje be ryšio
```

---

## Prieigos duomenys

| Sistema | URL | Vartotojas | Slaptažodis |
|---|---|---|---|
| Agro IoT UI | http://192.168.0.177:8081 | admin | admin123 |
| Agro IoT API | http://192.168.0.177:8002/docs | — | JWT Bearer |
| n8n | http://192.168.0.177:5678 | giedrius.pal274@go.kauko.lt | Admin.123 |
| Grafana | http://192.168.0.177:3000 | admin | Grafana123 |
| ChirpStack | http://192.168.0.186:8080 | admin | admin |

---

## Duomenų bazės schema

```
locations                    devices
─────────                    ───────
id                           id
name                         name
address                      device_type          (multi-select, pvz. "temperature,humidity")
location_type                unique_id
latitude / longitude         chirpstack_dev_eui
description                  location_id ──────────────► locations.id
                             field_mappings ──────────► device_field_mapping

device_field_mapping         measurement_values        device_events
────────────────────         ──────────────────        ─────────────
id                           id                        id
device_id                    device_id                 device_id
source_field                 field_key                 event_type (up/join/status)
display_name                 field_value               battery_level
unit                         received_at               raw_data
sensor_type                                            received_at

recommendations              plants                    location_plant
───────────────              ──────                    ──────────────
id                           id                        location_id
location_id                  name                      plant_id
content
weather_summary              user_location
created_at                   ─────────────
                             user_id
                             location_id
```

---

## n8n Workflows

| Workflow ID | Pavadinimas | Paleidimas |
|---|---|---|
| `rlPOkma2PJeE1wDA` | Rekomendacijos (rankinis) | `POST /webhook/agro-recommendations` |
| `YxWLpY0wGXIcyKLE` | Rekomendacijos (savaitinis) | Cron `0 18 * * 0` (sekmadienis 18:00) |

Abi workflows vykdo:
1. SQL → vietos duomenys + `location_type`
2. SQL → naujausių jutiklių rodmenys (DISTINCT ON laukų pavadinimui)
3. HTTP → Open-Meteo 7 dienų prognozė
4. Code → sudaro Claude AI prompt su visais duomenimis
5. HTTP → Claude AI API (claude-haiku-4-5-20251001)
6. SQL → `INSERT INTO recommendations`
