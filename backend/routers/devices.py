from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from database import get_db
from auth import get_current_user, require_admin
from schemas import DeviceOut, DeviceCreate
import models

router = APIRouter()

@router.get("/", response_model=List[DeviceOut])
def list_devices(db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    if current_user.is_admin:
        return db.query(models.Device).all()
    location_ids = [l.id for l in current_user.locations]
    return db.query(models.Device).filter(models.Device.location_id.in_(location_ids)).all()

@router.post("/", response_model=DeviceOut)
def create_device(data: DeviceCreate, db: Session = Depends(get_db), _=Depends(require_admin)):
    if db.query(models.Device).filter(models.Device.unique_id == data.unique_id).first():
        raise HTTPException(status_code=400, detail="Įrenginys su šiuo ID jau egzistuoja")
    loc = db.query(models.Location).filter(models.Location.id == data.location_id).first()
    if not loc:
        raise HTTPException(status_code=404, detail="Vieta nerasta")
    device = models.Device(**data.model_dump())
    db.add(device)
    db.commit()
    db.refresh(device)
    return device

@router.delete("/{device_id}")
def delete_device(device_id: int, db: Session = Depends(get_db), _=Depends(require_admin)):
    device = db.query(models.Device).filter(models.Device.id == device_id).first()
    if not device:
        raise HTTPException(status_code=404, detail="Įrenginys nerastas")
    db.delete(device)
    db.commit()
    return {"ok": True}
