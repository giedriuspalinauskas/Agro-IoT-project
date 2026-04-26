from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from database import get_db
from auth import get_current_user, require_admin
from schemas import LocationOut, LocationCreate, LocationUpdate
import models

router = APIRouter()

@router.get("/", response_model=List[LocationOut])
def list_locations(db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    if current_user.is_admin:
        return db.query(models.Location).all()
    return current_user.locations

@router.post("/", response_model=LocationOut)
def create_location(data: LocationCreate, db: Session = Depends(get_db), _=Depends(require_admin)):
    loc = models.Location(**data.model_dump())
    db.add(loc)
    db.commit()
    db.refresh(loc)
    return loc

@router.put("/{location_id}", response_model=LocationOut)
def update_location(location_id: int, data: LocationUpdate, db: Session = Depends(get_db), _=Depends(require_admin)):
    loc = db.query(models.Location).filter(models.Location.id == location_id).first()
    if not loc:
        raise HTTPException(status_code=404, detail="Vieta nerasta")
    for k, v in data.model_dump(exclude_unset=True).items():
        setattr(loc, k, v)
    db.commit()
    db.refresh(loc)
    return loc

@router.get("/{location_id}/ai-summary")
def get_ai_summary(location_id: int, db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    loc = db.query(models.Location).filter(models.Location.id == location_id).first()
    if not loc:
        raise HTTPException(status_code=404, detail="Vieta nerasta")
    sensors = []
    for device in loc.devices:
        for mapping in device.field_mappings:
            latest = db.query(models.MeasurementValue).filter(
                models.MeasurementValue.device_id == device.id,
                models.MeasurementValue.field_key == mapping.source_field
            ).order_by(models.MeasurementValue.received_at.desc()).first()
            if latest:
                sensors.append({
                    "device": device.name,
                    "field": mapping.display_name,
                    "value": latest.field_value,
                    "unit": mapping.unit or "",
                    "time": latest.received_at.isoformat()
                })
    return {
        "location_id": loc.id,
        "name": loc.name,
        "address": loc.address,
        "latitude": loc.latitude,
        "longitude": loc.longitude,
        "plants": [p.name for p in loc.plants],
        "sensors": sensors
    }

@router.delete("/{location_id}")
def delete_location(location_id: int, db: Session = Depends(get_db), _=Depends(require_admin)):
    loc = db.query(models.Location).filter(models.Location.id == location_id).first()
    if not loc:
        raise HTTPException(status_code=404, detail="Vieta nerasta")
    db.delete(loc)
    db.commit()
    return {"ok": True}
