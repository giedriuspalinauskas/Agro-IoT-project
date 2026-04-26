from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
from database import engine, Base
from routers import auth, users, locations, devices, measurements, plants, recommendations
import models

Base.metadata.create_all(bind=engine)

# Idempotent column migrations for schema additions
with engine.connect() as _conn:
    _conn.execute(text("ALTER TABLE locations ADD COLUMN IF NOT EXISTS location_type VARCHAR DEFAULT 'laukas'"))
    _conn.commit()

app = FastAPI(title="Agro IoT API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router, prefix="/api/auth", tags=["auth"])
app.include_router(users.router, prefix="/api/users", tags=["users"])
app.include_router(locations.router, prefix="/api/locations", tags=["locations"])
app.include_router(devices.router, prefix="/api/devices", tags=["devices"])
app.include_router(measurements.router, prefix="/api/measurements", tags=["measurements"])
app.include_router(plants.router, prefix="/api/plants", tags=["plants"])
app.include_router(recommendations.router, prefix="/api/recommendations", tags=["recommendations"])

@app.get("/api/health")
def health():
    return {"status": "ok"}
