from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session
from typing import List
from datetime import datetime, timezone
from collections import OrderedDict
from database import get_db
from auth import get_current_user, require_admin
from schemas import FieldMappingIn, FieldMappingOut
import models
import json

router = APIRouter()

SENSOR_TYPES = {
    "temperature": {"label": "Temperatūra", "unit": "°C", "icon": "🌡"},
    "humidity": {"label": "Drėgmė", "unit": "%", "icon": "💧"},
    "co2": {"label": "CO₂", "unit": "ppm", "icon": "🌫"},
    "pressure": {"label": "Slėgis", "unit": "hPa", "icon": "🔵"},
    "soil_moisture": {"label": "Dirvožemio drėgmė", "unit": "%", "icon": "🌱"},
    "rain": {"label": "Lietus", "unit": "mm", "icon": "🌧"},
    "other": {"label": "Kita", "unit": "", "icon": "📡"},
}

@router.get("/sensor-types")
def get_sensor_types():
    return SENSOR_TYPES

@router.post("/chirpstack")
async def receive_chirpstack(request: Request, db: Session = Depends(get_db)):
    event = request.query_params.get("event", "")
    if event not in ("up", "join", "status"):
        return {"ok": True, "skipped": True}
    try:
        body = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON")

    dev_eui = body.get("deviceInfo", {}).get("devEui", "")
    if not dev_eui:
        return {"ok": True, "skipped": True}

    device = db.query(models.Device).filter(
        models.Device.chirpstack_dev_eui == dev_eui
    ).first()
    if not device:
        device = db.query(models.Device).filter(
            models.Device.unique_id == dev_eui
        ).first()
    if not device:
        return {"ok": True, "skipped": True, "reason": "device not found"}

    # Use sensor reading time from ChirpStack payload, fall back to server time
    time_str = body.get("time")
    try:
        now = datetime.fromisoformat(time_str.replace("Z", "+00:00")) if time_str else datetime.now(timezone.utc)
    except Exception:
        now = datetime.now(timezone.utc)

    if event in ("join", "status"):
        battery = None
        if event == "status":
            raw_battery = body.get("batteryLevel")
            if raw_battery is not None:
                try:
                    battery = float(raw_battery)
                except (ValueError, TypeError):
                    pass
        dev_event = models.DeviceEvent(
            device_id=device.id,
            event_type=event,
            battery_level=battery,
            raw_data=json.dumps(body),
            received_at=now,
        )
        db.add(dev_event)
        db.commit()
        return {"ok": True, "device": device.name, "event": event}

    # UP event
    obj = body.get("object", {})

    dev_event = models.DeviceEvent(
        device_id=device.id,
        event_type="up",
        raw_data=json.dumps(obj),
        received_at=now,
    )
    db.add(dev_event)

    mappings = db.query(models.DeviceFieldMapping).filter(
        models.DeviceFieldMapping.device_id == device.id
    ).all()

    saved_values = []
    for mapping in mappings:
        if mapping.source_field in obj:
            try:
                val = float(obj[mapping.source_field])
                mv = models.MeasurementValue(
                    device_id=device.id,
                    field_key=mapping.source_field,
                    field_value=val,
                    received_at=now,
                )
                db.add(mv)
                saved_values.append({"field": mapping.source_field, "value": val})
            except (ValueError, TypeError):
                pass

    db.commit()
    return {"ok": True, "device": device.name, "values": saved_values}

@router.post("/direct")
async def receive_direct(body: dict, db: Session = Depends(get_db)):
    """Direct data ingestion from WiFi devices (e.g. Pico W via MQTT/n8n)."""
    unique_id = body.get("unique_id", "")
    data = body.get("data", {})
    if not unique_id or not isinstance(data, dict):
        raise HTTPException(status_code=400, detail="unique_id and data required")

    device = db.query(models.Device).filter(
        (models.Device.unique_id == unique_id) |
        (models.Device.chirpstack_dev_eui == unique_id)
    ).first()
    if not device:
        raise HTTPException(status_code=404, detail=f"Device '{unique_id}' not found")

    # Use Unix timestamp from Pico W if provided, otherwise server time
    ts = body.get("ts")
    try:
        now = datetime.fromtimestamp(float(ts), tz=timezone.utc) if ts else datetime.now(timezone.utc)
    except Exception:
        now = datetime.now(timezone.utc)

    dev_event = models.DeviceEvent(
        device_id=device.id,
        event_type="up",
        raw_data=json.dumps(data),
        received_at=now,
    )
    db.add(dev_event)

    mappings = db.query(models.DeviceFieldMapping).filter(
        models.DeviceFieldMapping.device_id == device.id
    ).all()

    saved = []
    for mapping in mappings:
        if mapping.source_field in data:
            try:
                mv = models.MeasurementValue(
                    device_id=device.id,
                    field_key=mapping.source_field,
                    field_value=float(data[mapping.source_field]),
                    received_at=now,
                )
                db.add(mv)
                saved.append(mapping.source_field)
            except (ValueError, TypeError):
                pass

    db.commit()
    return {"ok": True, "device": device.name, "saved": saved}

@router.get("/events/summary")
def get_events_summary(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    events = db.query(models.DeviceEvent)\
        .filter(models.DeviceEvent.event_type.in_(["join", "status"]))\
        .order_by(models.DeviceEvent.device_id, models.DeviceEvent.received_at.desc())\
        .all()
    result = {}
    for e in events:
        key = str(e.device_id)
        if key not in result:
            result[key] = {}
        if e.event_type == "join" and "last_join" not in result[key]:
            result[key]["last_join"] = e.received_at.isoformat()
        if e.event_type == "status" and "battery_level" not in result[key]:
            result[key]["battery_level"] = e.battery_level
    return result

@router.get("/device/{device_id}/fields")
def get_available_fields(
    device_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    event = db.query(models.DeviceEvent)\
        .filter(
            models.DeviceEvent.device_id == device_id,
            models.DeviceEvent.event_type == "up"
        )\
        .order_by(models.DeviceEvent.received_at.desc())\
        .first()
    if not event or not event.raw_data:
        return {"fields": [], "sample": {}}
    try:
        obj = json.loads(event.raw_data)
        def _is_numeric(v):
            if isinstance(v, (int, float)):
                return True
            if isinstance(v, str):
                try:
                    float(v)
                    return True
                except ValueError:
                    pass
            return False
        fields = [k for k, v in obj.items() if _is_numeric(v)]
        return {"fields": fields, "sample": obj}
    except Exception:
        return {"fields": [], "sample": {}}

@router.get("/device/{device_id}/mappings", response_model=List[FieldMappingOut])
def get_mappings(
    device_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    return db.query(models.DeviceFieldMapping).filter(
        models.DeviceFieldMapping.device_id == device_id
    ).all()

@router.post("/device/{device_id}/mappings")
def save_mappings(
    device_id: int,
    mappings: List[FieldMappingIn],
    db: Session = Depends(get_db),
    _=Depends(require_admin)
):
    db.query(models.DeviceFieldMapping).filter(
        models.DeviceFieldMapping.device_id == device_id
    ).delete()
    for m in mappings:
        mapping = models.DeviceFieldMapping(
            device_id=device_id,
            source_field=m.source_field,
            display_name=m.display_name,
            unit=m.unit,
            sensor_type=m.sensor_type,
        )
        db.add(mapping)
    db.commit()
    return {"ok": True}

@router.get("/device/{device_id}/events")
def get_device_events(
    device_id: int,
    limit: int = 20,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    device = db.query(models.Device).filter(models.Device.id == device_id).first()
    if not device:
        raise HTTPException(status_code=404, detail="Įrenginys nerastas")
    if not current_user.is_admin:
        user_loc_ids = [l.id for l in current_user.locations]
        if device.location_id not in user_loc_ids:
            raise HTTPException(status_code=403, detail="Nėra prieigos")
    events = db.query(models.DeviceEvent)\
        .filter(models.DeviceEvent.device_id == device_id)\
        .order_by(models.DeviceEvent.received_at.desc())\
        .limit(limit).all()
    return [
        {
            "id": e.id,
            "event_type": e.event_type,
            "battery_level": e.battery_level,
            "received_at": e.received_at.isoformat(),
        }
        for e in events
    ]

@router.get("/device/{device_id}")
def get_device_measurements(
    device_id: int,
    limit: int = 50,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    device = db.query(models.Device).filter(models.Device.id == device_id).first()
    if not device:
        raise HTTPException(status_code=404, detail="Įrenginys nerastas")
    if not current_user.is_admin:
        user_loc_ids = [l.id for l in current_user.locations]
        if device.location_id not in user_loc_ids:
            raise HTTPException(status_code=403, detail="Nėra prieigos")

    rows = db.query(models.MeasurementValue)\
        .filter(models.MeasurementValue.device_id == device_id)\
        .order_by(models.MeasurementValue.received_at.desc())\
        .all()

    groups: OrderedDict = OrderedDict()
    for v in rows:
        key = v.received_at.isoformat()
        if key not in groups:
            if len(groups) >= limit:
                break
            groups[key] = {"received_at": v.received_at, "values": []}
        groups[key]["values"].append({"field_key": v.field_key, "field_value": v.field_value})

    return [
        {"received_at": g["received_at"], "values": g["values"]}
        for g in groups.values()
    ]
