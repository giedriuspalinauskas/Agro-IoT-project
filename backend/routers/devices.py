from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
import httpx
from database import get_db
from auth import get_current_user, require_admin
from schemas import DeviceOut, DeviceCreate, DeviceUpdate
import models

router = APIRouter()

CHIRPSTACK_URL = "http://192.168.0.186:8090"
CHIRPSTACK_API_KEY = "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJhdWQiOiJjaGlycHN0YWNrIiwiaXNzIjoiY2hpcnBzdGFjayIsInN1YiI6IjlkNzJiZGZlLWM3MGMtNDYwYS1hZDExLTU2NmNlNTZkNmI3ZiIsInR5cCI6ImtleSJ9.zAcGsAAeU01ZUB5n82wBVEWGX9MpZ-r0xh0y7-DG6h4"
CHIRPSTACK_APP_ID = "d0168e14-67a4-45e0-a8fa-f2f19636b5fc"

@router.get("/", response_model=List[DeviceOut])
def list_devices(db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    if current_user.is_admin:
        return db.query(models.Device).all()
    location_ids = [l.id for l in current_user.locations]
    return db.query(models.Device).filter(models.Device.location_id.in_(location_ids)).all()

@router.post("/import-from-chirpstack", response_model=List[DeviceOut])
async def import_from_chirpstack(
    location_id: int,
    db: Session = Depends(get_db),
    _=Depends(require_admin)
):
    headers = {"Authorization": f"Bearer {CHIRPSTACK_API_KEY}"}
    url = f"{CHIRPSTACK_URL}/api/devices?applicationId={CHIRPSTACK_APP_ID}&limit=100"
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.get(url, headers=headers)
            resp.raise_for_status()
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"ChirpStack ryšio klaida: {str(e)}")
    chirp_devices = resp.json().get("result", [])
    if not chirp_devices:
        raise HTTPException(status_code=404, detail="ChirpStack aplikacijoje nerasta įrenginių")
    loc = db.query(models.Location).filter(models.Location.id == location_id).first()
    if not loc:
        raise HTTPException(status_code=404, detail="Vieta nerasta")
    imported = []
    for d in chirp_devices:
        dev_eui = d.get("devEui", "")
        name = d.get("name", dev_eui)
        existing = db.query(models.Device).filter(
            models.Device.chirpstack_dev_eui == dev_eui
        ).first()
        if existing:
            existing.name = name
            db.commit()
            db.refresh(existing)
            imported.append(existing)
        else:
            device = models.Device(
                name=name,
                device_type="unknown",
                unique_id=dev_eui,
                chirpstack_dev_eui=dev_eui,
                location_id=location_id,
            )
            db.add(device)
            db.commit()
            db.refresh(device)
            imported.append(device)
    return imported

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

@router.put("/{device_id}", response_model=DeviceOut)
def update_device(device_id: int, data: DeviceUpdate, db: Session = Depends(get_db), _=Depends(require_admin)):
    device = db.query(models.Device).filter(models.Device.id == device_id).first()
    if not device:
        raise HTTPException(status_code=404, detail="Įrenginys nerastas")
    if data.location_id is not None and data.location_id != device.location_id:
        db.query(models.MeasurementValue).filter(models.MeasurementValue.device_id == device_id).delete()
        db.query(models.DeviceEvent).filter(models.DeviceEvent.device_id == device_id).delete()
    for k, v in data.model_dump(exclude_unset=True).items():
        setattr(device, k, v)
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
