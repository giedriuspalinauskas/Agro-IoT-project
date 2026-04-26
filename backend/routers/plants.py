from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from database import get_db
from auth import get_current_user, require_admin
import models

router = APIRouter()

@router.get("")
def get_plants(db: Session = Depends(get_db), _=Depends(get_current_user)):
    return [{"id": p.id, "name": p.name} for p in db.query(models.Plant).order_by(models.Plant.name).all()]

@router.post("")
def create_plant(body: dict, db: Session = Depends(get_db), _=Depends(require_admin)):
    name = (body.get("name") or "").strip()
    if not name:
        raise HTTPException(400, "Pavadinimas privalomas")
    if db.query(models.Plant).filter(models.Plant.name == name).first():
        raise HTTPException(400, "Toks augalas jau yra")
    plant = models.Plant(name=name)
    db.add(plant)
    db.commit()
    db.refresh(plant)
    return {"id": plant.id, "name": plant.name}

@router.delete("/{plant_id}")
def delete_plant(plant_id: int, db: Session = Depends(get_db), _=Depends(require_admin)):
    plant = db.query(models.Plant).filter(models.Plant.id == plant_id).first()
    if not plant:
        raise HTTPException(404, "Augalas nerastas")
    db.delete(plant)
    db.commit()
    return {}

@router.put("/location/{location_id}")
def set_location_plants(location_id: int, body: dict, db: Session = Depends(get_db), _=Depends(require_admin)):
    location = db.query(models.Location).filter(models.Location.id == location_id).first()
    if not location:
        raise HTTPException(404, "Vieta nerasta")
    plant_ids = body.get("plant_ids", [])
    plants = db.query(models.Plant).filter(models.Plant.id.in_(plant_ids)).all()
    location.plants = plants
    db.commit()
    return {"ok": True}
