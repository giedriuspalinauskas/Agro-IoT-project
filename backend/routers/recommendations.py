from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session, joinedload
from database import get_db
from auth import get_current_user
import models

router = APIRouter()

def _rec_out(r):
    return {
        "id": r.id,
        "location_id": r.location_id,
        "location_name": r.location.name if r.location else "—",
        "content": r.content,
        "weather_summary": r.weather_summary,
        "created_at": r.received_at.isoformat() if hasattr(r, "received_at") else r.created_at.isoformat(),
    }

@router.get("")
def get_all_recommendations(db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    q = db.query(models.Recommendation).options(joinedload(models.Recommendation.location))
    if not current_user.is_admin:
        user_loc_ids = [l.id for l in current_user.locations]
        q = q.filter(models.Recommendation.location_id.in_(user_loc_ids))
    recs = q.order_by(models.Recommendation.created_at.desc()).limit(100).all()
    return [_rec_out(r) for r in recs]

@router.get("/location/{location_id}")
def get_recommendations(location_id: int, db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    recs = db.query(models.Recommendation)\
        .options(joinedload(models.Recommendation.location))\
        .filter(models.Recommendation.location_id == location_id)\
        .order_by(models.Recommendation.created_at.desc())\
        .limit(10).all()
    return [_rec_out(r) for r in recs]

@router.post("")
async def save_recommendations(body: dict, db: Session = Depends(get_db), _=Depends(get_current_user)):
    location_id = body.get("location_id")
    content = body.get("content", "").strip()
    weather_summary = body.get("weather_summary")
    if not location_id or not content:
        raise HTTPException(400, "location_id ir content privalomi")
    rec = models.Recommendation(location_id=location_id, content=content, weather_summary=weather_summary)
    db.add(rec)
    db.commit()
    db.refresh(rec)
    return {"id": rec.id, "created_at": rec.created_at.isoformat()}

@router.delete("/{rec_id}")
def delete_recommendation(rec_id: int, db: Session = Depends(get_db), _=Depends(get_current_user)):
    rec = db.query(models.Recommendation).filter(models.Recommendation.id == rec_id).first()
    if not rec:
        raise HTTPException(404, "Nerasta")
    db.delete(rec)
    db.commit()
    return {}
