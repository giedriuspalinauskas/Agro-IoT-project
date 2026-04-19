from sqlalchemy import Column, Integer, String, Boolean, ForeignKey, Table, Text, Float, DateTime
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from database import Base

user_location = Table(
    "user_location",
    Base.metadata,
    Column("user_id", Integer, ForeignKey("users.id")),
    Column("location_id", Integer, ForeignKey("locations.id")),
)

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True, nullable=False)
    email = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    is_admin = Column(Boolean, default=False)
    is_active = Column(Boolean, default=True)
    locations = relationship("Location", secondary=user_location, back_populates="users")

class Location(Base):
    __tablename__ = "locations"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    address = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    latitude = Column(Float, nullable=True)
    longitude = Column(Float, nullable=True)
    users = relationship("User", secondary=user_location, back_populates="locations")
    devices = relationship("Device", back_populates="location", cascade="all, delete-orphan")

class Device(Base):
    __tablename__ = "devices"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    device_type = Column(String, nullable=False)
    unique_id = Column(String, unique=True, nullable=False)
    location_id = Column(Integer, ForeignKey("locations.id"), nullable=False)
    chirpstack_dev_eui = Column(String, nullable=True)
    temperature_field = Column(String, nullable=True)
    humidity_field = Column(String, nullable=True)
    location = relationship("Location", back_populates="devices")
    measurements = relationship("Measurement", back_populates="device", cascade="all, delete-orphan")

class Measurement(Base):
    __tablename__ = "measurements"
    id = Column(Integer, primary_key=True, index=True)
    device_id = Column(Integer, ForeignKey("devices.id"), nullable=False)
    temperature = Column(Float, nullable=True)
    humidity = Column(Float, nullable=True)
    raw_data = Column(Text, nullable=True)
    received_at = Column(DateTime(timezone=True), server_default=func.now())
    device = relationship("Device", back_populates="measurements")
