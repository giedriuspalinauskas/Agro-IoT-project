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
    """ChirpStack HTTP Integration endpoint - priima duomenis be autentifikacijos"""
    try:
        body = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON")

    # ChirpStack siunčia devEui
    dev_eui = body.get("deviceInfo", {}).get("devEui", "")
    if not dev_eui:
        # Bandome senesnį formatą
        dev_eui = body.get("devEUI", "")

    if not dev_eui:
        raise HTTPException(status_code=400, detail="devEui nerasta")

    # Randame įrenginį pagal devEUI
    device = db.query(models.Device).filter(
        models.Device.chirpstack_dev_eui == dev_eui
    ).first()

    if not device:
        # Bandome rasti pagal unique_id
        device = db.query(models.Device).filter(
            models.Device.unique_id == dev_eui
        ).first()

    if not device:
        raise HTTPException(status_code=404, detail=f"Įrenginys su devEUI {dev_eui} nerastas")

    # Dekoduojame objektą (ChirpStack jau dekoduoja jei yra codec)
    obj = body.get("object", {})
    temperature = obj.get("temperature") or obj.get("temp") or obj.get("Temperature")
    humidity = obj.get("humidity") or obj.get("hum") or obj.get("Humidity")

    # Išsaugome matavimą
    measurement = models.Measurement(
        device_id=device.id,
        temperature=float(temperature) if temperature is not None else None,
        humidity=float(humidity) if humidity is not None else None,
        raw_data=json.dumps(body),
    )
    db.add(measurement)
    db.commit()
    return {"ok": True, "device": device.name}

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

    # Tikriname ar vartotojas turi prieigą
    if not current_user.is_admin:
        user_loc_ids = [l.id for l in current_user.locations]
        if device.location_id not in user_loc_ids:
            raise HTTPException(status_code=403, detail="Nėra prieigos")

    return db.query(models.Measurement)\
        .filter(models.Measurement.device_id == device_id)\
        .order_by(models.Measurement.received_at.desc())\
        .limit(limit).all()
