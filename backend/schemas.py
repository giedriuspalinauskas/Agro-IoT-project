from pydantic import BaseModel
from typing import Optional, List

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

class DeviceBase(BaseModel):
    name: str
    device_type: str
    unique_id: str

class DeviceCreate(DeviceBase):
    location_id: int

class DeviceOut(DeviceBase):
    id: int
    location_id: int
    class Config:
        from_attributes = True

class LocationBase(BaseModel):
    name: str
    address: str
    description: Optional[str] = None

class LocationCreate(LocationBase):
    pass

class LocationUpdate(BaseModel):
    name: Optional[str] = None
    address: Optional[str] = None
    description: Optional[str] = None

class LocationOut(LocationBase):
    id: int
    devices: List[DeviceOut] = []
    class Config:
        from_attributes = True
