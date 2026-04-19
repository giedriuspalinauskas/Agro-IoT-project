from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from datetime import datetime

class Token(BaseModel):
    access_token: str
    token_type: str

class LoginRequest(BaseModel):
    username: str
    password: str

class UserBase(BaseModel):
    username: str
    email: str

class UserCreate(UserBase):
    password: str
    is_admin: bool = False

class UserUpdate(BaseModel):
    email: Optional[str] = None
    password: Optional[str] = None
    is_admin: Optional[bool] = None
    is_active: Optional[bool] = None

class UserOut(UserBase):
    id: int
    is_admin: bool
    is_active: bool
    class Config:
        from_attributes = True

class FieldMappingIn(BaseModel):
    source_field: str
    display_name: str
    unit: Optional[str] = None
    sensor_type: str

class FieldMappingOut(FieldMappingIn):
    id: int
    device_id: int
    class Config:
        from_attributes = True

class MeasurementValueOut(BaseModel):
    field_key: str
    field_value: float
    class Config:
        from_attributes = True

class MeasurementOut(BaseModel):
    id: int
    temperature: Optional[float] = None
    humidity: Optional[float] = None
    received_at: datetime
    values: List[MeasurementValueOut] = []
    class Config:
        from_attributes = True

class DeviceBase(BaseModel):
    name: str
    device_type: str
    unique_id: str
    chirpstack_dev_eui: Optional[str] = None
    temperature_field: Optional[str] = None
    humidity_field: Optional[str] = None

class DeviceCreate(DeviceBase):
    location_id: int

class DeviceUpdate(BaseModel):
    name: Optional[str] = None
    device_type: Optional[str] = None
    unique_id: Optional[str] = None
    chirpstack_dev_eui: Optional[str] = None
    location_id: Optional[int] = None
    temperature_field: Optional[str] = None
    humidity_field: Optional[str] = None

class DeviceOut(DeviceBase):
    id: int
    location_id: int
    measurements: List[MeasurementOut] = []
    field_mappings: List[FieldMappingOut] = []
    class Config:
        from_attributes = True

class LocationBase(BaseModel):
    name: str
    address: str
    description: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None

class LocationCreate(LocationBase):
    pass

class LocationUpdate(BaseModel):
    name: Optional[str] = None
    address: Optional[str] = None
    description: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None

class LocationOut(LocationBase):
    id: int
    devices: List[DeviceOut] = []
    class Config:
        from_attributes = True
