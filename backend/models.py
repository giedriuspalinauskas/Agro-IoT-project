from sqlalchemy import Column, Integer, String, Boolean, ForeignKey, Table, Text, Float, DateTime, UniqueConstraint
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from database import Base

user_location = Table(
    "user_location",
    Base.metadata,
    Column("user_id", Integer, ForeignKey("users.id")),
    Column("location_id", Integer, ForeignKey("locations.id")),
)

location_plant = Table(
    "location_plant",
    Base.metadata,
    Column("location_id", Integer, ForeignKey("locations.id")),
    Column("plant_id", Integer, ForeignKey("plants.id")),
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

class Plant(Base):
    __tablename__ = "plants"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False, unique=True)
    locations = relationship("Location", secondary="location_plant", back_populates="plants")

class Location(Base):
    __tablename__ = "locations"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    address = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    latitude = Column(Float, nullable=True)
    longitude = Column(Float, nullable=True)
    location_type = Column(String, nullable=True, default='laukas')
    users = relationship("User", secondary=user_location, back_populates="locations")
    devices = relationship("Device", back_populates="location", cascade="all, delete-orphan")
    plants = relationship("Plant", secondary="location_plant", back_populates="locations")
    recommendations = relationship("Recommendation", back_populates="location", cascade="all, delete-orphan", order_by="Recommendation.created_at.desc()")

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
    field_mappings = relationship("DeviceFieldMapping", back_populates="device", cascade="all, delete-orphan")
    events = relationship("DeviceEvent", back_populates="device", cascade="all, delete-orphan")
    measurement_values = relationship("MeasurementValue", back_populates="device", cascade="all, delete-orphan")

class DeviceFieldMapping(Base):
    __tablename__ = "device_field_mapping"
    id = Column(Integer, primary_key=True, index=True)
    device_id = Column(Integer, ForeignKey("devices.id"), nullable=False)
    source_field = Column(String, nullable=False)
    display_name = Column(String, nullable=False)
    unit = Column(String, nullable=True)
    sensor_type = Column(String, nullable=False)
    device = relationship("Device", back_populates="field_mappings")
    __table_args__ = (UniqueConstraint("device_id", "source_field"),)

class DeviceEvent(Base):
    __tablename__ = "device_events"
    id = Column(Integer, primary_key=True, index=True)
    device_id = Column(Integer, ForeignKey("devices.id"), nullable=False)
    event_type = Column(String, nullable=False)
    battery_level = Column(Float, nullable=True)
    raw_data = Column(Text, nullable=True)
    received_at = Column(DateTime(timezone=True), server_default=func.now())
    device = relationship("Device", back_populates="events")

class Recommendation(Base):
    __tablename__ = "recommendations"
    id = Column(Integer, primary_key=True, index=True)
    location_id = Column(Integer, ForeignKey("locations.id"), nullable=False)
    content = Column(Text, nullable=False)
    weather_summary = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    location = relationship("Location", back_populates="recommendations")

class MeasurementValue(Base):
    __tablename__ = "measurement_values"
    id = Column(Integer, primary_key=True, index=True)
    device_id = Column(Integer, ForeignKey("devices.id"), nullable=False)
    field_key = Column(String, nullable=False)
    field_value = Column(Float, nullable=False)
    received_at = Column(DateTime(timezone=True), server_default=func.now())
    device = relationship("Device", back_populates="measurement_values")
