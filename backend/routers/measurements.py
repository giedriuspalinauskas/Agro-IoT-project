from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session
from typing import List
from database import get_db
from auth import get_current_user, require_admin
from schemas import MeasurementOut, FieldMappingIn, FieldMappingOut
import models
import json

router = APIRouter()

SENSOR_TYPES = {
    "temperature": {"label": "Temperatūra", "unit": "°C", "icon": "🌡"},
    "humidity": {"label": "Drėgmė", "unit": "%", "icon": "💧"},
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
    if event != "up":
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

    obj = body.get("object", {})

    # Saugome matavimą
    temperature = None
    humidity = None

    # Legacy laukai
    for key in ["temperature_c", "temperature", "temp", "Temperature"]:
        if key in obj:
            try:
                temperature = float(obj[key])
                break
            except (ValueError, TypeError):
                pass

    for key in ["humidity_pct", "humidity", "hum", "Humidity", "rh"]:
        if key in obj:
            try:
                humidity = float(obj[key])
                break
            except (ValueError, TypeError):
                pass

    measurement = models.Measurement(
        device_id=device.id,
        temperature=temperature,
        humidity=humidity,
        raw_data=json.dumps(obj),
    )
    db.add(measurement)
    db.flush()

    # Universalūs measurement values pagal field mappings
    mappings = db.query(models.DeviceFieldMapping).filter(
        models.DeviceFieldMapping.device_id == device.id
    ).all()

    saved_values = []
    for mapping in mappings:
        if mapping.source_field in obj:
            try:
                val = float(obj[mapping.source_field])
                mv = models.MeasurementValue(
                    measurement_id=measurement.id,
                    field_key=mapping.source_field,
                    field_value=val,
                )
                db.add(mv)
                saved_values.append({"field": mapping.source_field, "value": val})
            except (ValueError, TypeError):
                pass

    db.commit()
    return {"ok": True, "device": device.name, "values": saved_values}

@router.get("/device/{device_id}/fields")
def get_available_fields(
    device_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    measurement = db.query(models.Measurement)\
        .filter(models.Measurement.device_id == device_id)\
        .order_by(models.Measurement.received_at.desc())\
        .first()
    if not measurement or not measurement.raw_data:
        return {"fields": [], "sample": {}}
    try:
        obj = json.loads(measurement.raw_data)
        fields = [k for k, v in obj.items() if isinstance(v, (int, float))]
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
    # Ištriname senus
    db.query(models.DeviceFieldMapping).filter(
        models.DeviceFieldMapping.device_id == device_id
    ).delete()
    # Pridedame naujus
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

@router.get("/device/{device_id}", response_model=List[MeasurementOut])
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
    return db.query(models.Measurement)\
        .filter(models.Measurement.device_id == device_id)\
        .order_by(models.Measurement.received_at.desc())\
        .limit(limit).all()
