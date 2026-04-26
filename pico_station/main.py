"""
Agro IoT - Pico W sensor station
Reads sensors, buffers offline, sends via MQTT when connected.

Topic:   agro/sensors/<DEVICE_UID>
Payload: {"unique_id": "...", "data": {"field": value, ...}}

RPi receives via n8n (MQTT Trigger) → POST /api/measurements/direct
"""
import network
import time
import json
import os
try:
    from umqtt.robust import MQTTClient
except ImportError:
    from umqtt.simple import MQTTClient

# ── Configuration ──────────────────────────────────────────────────────────────
WIFI_SSID     = "YOUR_WIFI_SSID"
WIFI_PASSWORD = "YOUR_WIFI_PASSWORD"

MQTT_BROKER   = "192.168.0.177"   # RPi IP
MQTT_PORT     = 1883
DEVICE_UID    = "pico-001"        # must match unique_id in Agro IoT devices
MQTT_TOPIC    = ("agro/sensors/" + DEVICE_UID).encode()

READ_INTERVAL = 60                # seconds between sensor readings
MAX_RAM_BUF   = 200               # max readings kept in RAM when offline
FLASH_BUF     = "/buffer.json"    # flash fallback when RAM buffer is full

# ── Sensor reading ─────────────────────────────────────────────────────────────
def read_sensors():
    """
    Replace this with your actual sensor code.
    Must return a dict of {field_name: numeric_value}.
    Field names must match the source_field configured in Agro IoT device mapping.
    """
    # ---- Example: onboard temperature sensor ----
    import machine
    sensor = machine.ADC(4)
    reading = sensor.read_u16()
    voltage = reading * 3.3 / 65535
    temp = 27.0 - (voltage - 0.706) / 0.001721

    # ---- Add your sensors here, e.g.: ----
    # dht = dht.DHT22(machine.Pin(15))
    # dht.measure()
    # return {"temperature": dht.temperature(), "humidity": dht.humidity()}

    return {
        "temperature": round(temp, 2),
        # "humidity": ...,
        # "co2": ...,
        # "pressure": ...,
    }

# ── Flash-based buffer (for extended offline periods) ─────────────────────────
def _load_flash():
    try:
        with open(FLASH_BUF) as f:
            return json.load(f)
    except:
        return []

def _save_flash(buf):
    try:
        with open(FLASH_BUF, "w") as f:
            json.dump(buf, f)
    except Exception as e:
        print("Flash save error:", e)

def _clear_flash():
    try:
        os.remove(FLASH_BUF)
    except:
        pass

# ── WiFi ───────────────────────────────────────────────────────────────────────
_wlan = network.WLAN(network.STA_IF)

def wifi_connect():
    _wlan.active(True)
    if _wlan.isconnected():
        return True
    print("WiFi: connecting to", WIFI_SSID)
    _wlan.connect(WIFI_SSID, WIFI_PASSWORD)
    for _ in range(40):          # 20-second timeout
        if _wlan.isconnected():
            print("WiFi: connected", _wlan.ifconfig()[0])
            return True
        time.sleep(0.5)
    print("WiFi: timeout")
    return False

# ── MQTT ───────────────────────────────────────────────────────────────────────
_mqtt = None

def mqtt_connect():
    global _mqtt
    try:
        c = MQTTClient(DEVICE_UID, MQTT_BROKER, port=MQTT_PORT, keepalive=30)
        c.connect()
        _mqtt = c
        print("MQTT: connected to", MQTT_BROKER)
        return True
    except Exception as e:
        print("MQTT: connect failed:", e)
        _mqtt = None
        return False

def mqtt_publish(payload_str):
    global _mqtt
    try:
        _mqtt.publish(MQTT_TOPIC, payload_str)
        return True
    except Exception as e:
        print("MQTT: publish failed:", e)
        _mqtt = None
        return False

def flush_buffer(ram_buf, flash_buf):
    """Send all buffered messages. Returns (remaining_ram, remaining_flash)."""
    global _mqtt

    # Flash buffer first (oldest data)
    i = 0
    while i < len(flash_buf) and _mqtt:
        if mqtt_publish(flash_buf[i]):
            i += 1
        else:
            break
    flash_buf = flash_buf[i:]
    if i:
        print("Flushed", i, "flash readings")
    if not flash_buf:
        _clear_flash()
    else:
        _save_flash(flash_buf)

    # Then RAM buffer
    i = 0
    while i < len(ram_buf) and _mqtt:
        if mqtt_publish(ram_buf[i]):
            i += 1
        else:
            break
    ram_buf = ram_buf[i:]
    if i:
        print("Flushed", i, "RAM readings")

    return ram_buf, flash_buf

# ── Main loop ──────────────────────────────────────────────────────────────────
ram_buf   = []
flash_buf = _load_flash()   # restore any readings saved to flash
if flash_buf:
    print("Restored", len(flash_buf), "readings from flash")

while True:
    try:
        data = read_sensors()
        payload = json.dumps({"unique_id": DEVICE_UID, "data": data})

        if wifi_connect():
            if _mqtt is None:
                mqtt_connect()

            if _mqtt:
                # Flush buffered data first, then send current reading
                ram_buf, flash_buf = flush_buffer(ram_buf, flash_buf)
                if _mqtt:
                    if not mqtt_publish(payload):
                        ram_buf.append(payload)
            else:
                ram_buf.append(payload)
        else:
            _mqtt = None
            ram_buf.append(payload)

        # When RAM is full, spill oldest entries to flash
        if len(ram_buf) > MAX_RAM_BUF:
            spill = ram_buf[:50]
            ram_buf = ram_buf[50:]
            flash_buf.extend(spill)
            _save_flash(flash_buf)
            print("Spilled 50 readings to flash. RAM:", len(ram_buf), "Flash:", len(flash_buf))

        print("OK | RAM buf:", len(ram_buf), "| Flash buf:", len(flash_buf), "| data:", data)

    except Exception as e:
        print("Loop error:", e)

    time.sleep(READ_INTERVAL)
