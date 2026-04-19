from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from database import get_db
from auth import verify_password, create_access_token, get_current_user, seed_admin
from schemas import Token, LoginRequest, UserOut
import models

router = APIRouter()

@router.post("/login", response_model=Token)
def login(data: LoginRequest, db: Session = Depends(get_db)):
    seed_admin(db)
    user = db.query(models.User).filter(models.User.username == data.username).first()
    if not user or not verify_password(data.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Neteisingas vardas arba slaptažodis")
    if not user.is_active:
        raise HTTPException(status_code=403, detail="Paskyra išjungta")
    token = create_access_token({"sub": user.username})
    return {"access_token": token, "token_type": "bearer"}

@router.get("/me", response_model=UserOut)
def me(current_user: models.User = Depends(get_current_user)):
    return current_user
