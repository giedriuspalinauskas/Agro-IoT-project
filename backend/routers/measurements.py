from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session
from typing import List
from database import get_db
from auth import get_current_user
from schemas import MeasurementOut
import models
import json

router = APIRouter()

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
    temperature = None
    humidity = None

    if device.temperature_field and device.temperature_field in obj:
        try:
            temperature = float(obj[device.temperature_field])
        except (ValueError, TypeError):
            pass

    if device.humidity_field and device.humidity_field in obj:
        try:
            humidity = float(obj[device.humidity_field])
        except (ValueError, TypeError):
            pass

    if temperature is None:
        for key in ["temperature_c", "temperature", "temp", "Temperature", "temp_c"]:
            if key in obj:
                try:
                    temperature = float(obj[key])
                    break
                except (ValueError, TypeError):
                    pass

    if humidity is None:
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
    db.commit()
    return {"ok": True, "device": device.name, "temperature": temperature, "humidity": humidity}

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
        return {"fields": []}
    try:
        obj = json.loads(measurement.raw_data)
        fields = [k for k, v in obj.items() if isinstance(v, (int, float))]
        return {"fields": fields, "sample": obj}
    except Exception:
        return {"fields": []}

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
