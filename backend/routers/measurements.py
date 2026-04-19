from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session
from typing import List, Optional
from database import get_db
from auth import get_current_user
from schemas import MeasurementOut
import models
import json

router = APIRouter()

@router.post("/chirpstack")
async def receive_chirpstack(request: Request, db: Session = Depends(get_db)):
    event = request.query_params.get("event", "")
    # Saugome tik uplink duomenis
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

    # Dinaminis mapingas – naudoja device konfigūraciją
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

    # Jei mapingas nenurodytas – bandome automatinius laukus
    if temperature is None:
        for key in ["temperature_c", "temperature", "temp", "Temperature", "temp_c"]:
            if key in obj:
                try:
                    temperature = float(obj[key])
