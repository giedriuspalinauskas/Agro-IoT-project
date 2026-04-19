from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from database import get_db
from auth import require_admin, hash_password
from schemas import UserOut, UserCreate, UserUpdate
import models

router = APIRouter()

@router.get("/", response_model=List[UserOut])
def list_users(db: Session = Depends(get_db), _=Depends(require_admin)):
    return db.query(models.User).all()

@router.post("/", response_model=UserOut)
def create_user(data: UserCreate, db: Session = Depends(get_db), _=Depends(require_admin)):
    if db.query(models.User).filter(models.User.username == data.username).first():
        raise HTTPException(status_code=400, detail="Vartotojas jau egzistuoja")
    if db.query(models.User).filter(models.User.email == data.email).first():
        raise HTTPException(status_code=400, detail="El. paštas jau naudojamas")
    user = models.User(
        username=data.username,
        email=data.email,
        hashed_password=hash_password(data.password),
        is_admin=data.is_admin,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user

@router.put("/{user_id}", response_model=UserOut)
def update_user(user_id: int, data: UserUpdate, db: Session = Depends(get_db), _=Depends(require_admin)):
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Vartotojas nerastas")
    if data.email: user.email = data.email
    if data.password: user.hashed_password = hash_password(data.password)
    if data.is_admin is not None: user.is_admin = data.is_admin
    if data.is_active is not None: user.is_active = data.is_active
    db.commit()
    db.refresh(user)
    return user

@router.delete("/{user_id}")
def delete_user(user_id: int, db: Session = Depends(get_db), _=Depends(require_admin)):
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Vartotojas nerastas")
    db.delete(user)
    db.commit()
    return {"ok": True}

@router.post("/{user_id}/locations/{location_id}")
def assign_location(user_id: int, location_id: int, db: Session = Depends(get_db), _=Depends(require_admin)):
    user = db.query(models.User).filter(models.User.id == user_id).first()
    loc = db.query(models.Location).filter(models.Location.id == location_id).first()
    if not user or not loc:
        raise HTTPException(status_code=404, detail="Vartotojas arba vieta nerasta")
    if loc not in user.locations:
        user.locations.append(loc)
        db.commit()
    return {"ok": True}

@router.delete("/{user_id}/locations/{location_id}")
def unassign_location(user_id: int, location_id: int, db: Session = Depends(get_db), _=Depends(require_admin)):
    user = db.query(models.User).filter(models.User.id == user_id).first()
    loc = db.query(models.Location).filter(models.Location.id == location_id).first()
    if not user or not loc:
        raise HTTPException(status_code=404, detail="Vartotojas arba vieta nerasta")
    if loc in user.locations:
        user.locations.remove(loc)
        db.commit()
    return {"ok": True}
