from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
import httpx
from database import get_db
from auth import get_current_user, require_admin
from schemas import DeviceOut, DeviceCreate, DeviceUpdate
import models

router = APIRouter()

CHIRPSTACK_URL = "http://192.168.0.177:8080"
CHIRPSTACK_API_KEY = "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJhdWQiOiJjaGlycHN0YWNrIiwiaXNzIjoiY2hpcnBzdGFjayIsInN1YiI6ImYyN2NlYzA3LWRmOGMtNDc5OS04Y2NkLWIxOWI4YTkxNDZkNSIsInR5cCI6ImtleSJ9.EzjiNc7Zw5wOn7xj8ZECkdphcgU00UqYKDj2sQsSLG0"
CHIRPSTACK_APP_ID = "7b66c18c-fb61-48a8-b7d7-036a88bead55"

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
    devi
