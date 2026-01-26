"""
Device Model - User device registration for push notifications
"""
from typing import Optional, Dict, Any
from datetime import datetime
from pydantic import BaseModel, Field
import uuid


class DevicePlatform(str):
    """Supported device platforms"""
    IOS = "ios"
    ANDROID = "android"
    WEB = "web"


class Device(BaseModel):
    """
    User device registration model

    Used for push notifications and device management.
    """
    # Primary key
    id: str = Field(default_factory=lambda: str(uuid.uuid4()), description="Device ID")

    # User reference
    user_id: str = Field(..., description="User ID who owns this device")

    # Device identification
    platform: str = Field(..., description="Platform: ios, android, web")
    token: str = Field(..., description="Push notification token")
    device_id: Optional[str] = Field(None, description="Unique device identifier (e.g., UDID, device_id)")

    # Device metadata
    device_name: Optional[str] = Field(None, description="Human-readable device name")
    device_model: Optional[str] = Field(None, description="Device model (e.g., iPhone 14, Pixel 7)")
    os_version: Optional[str] = Field(None, description="Operating system version")
    app_version: Optional[str] = Field(None, description="App version")

    # Additional metadata (for flexibility)
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional device information")

    # Status
    is_active: bool = Field(default=True, description="Whether device is active")
    last_used_at: Optional[datetime] = Field(None, description="Last time this device was used")

    # Timestamps
    created_at: datetime = Field(default_factory=datetime.utcnow, description="Registration time")
    updated_at: datetime = Field(default_factory=datetime.utcnow, description="Last update time")

    class Config:
        json_schema_extra = {
            "example": {
                "user_id": "user-123",
                "platform": "ios",
                "token": "device_push_token_from_apns",
                "device_id": "unique_device_id",
                "device_name": "iPhone 14 Pro",
                "device_model": "iPhone15,3",
                "os_version": "17.2",
                "app_version": "1.0.0",
                "metadata": {
                    "locale": "en_US",
                    "timezone": "America/New_York"
                },
                "is_active": True
            }
        }

    def to_dict(self) -> dict:
        """Convert to dictionary for database storage"""
        return self.model_dump(mode='json')

    @classmethod
    def from_dict(cls, data: dict) -> "Device":
        """Create from dictionary"""
        return cls(**data)


# SQLAlchemy database model
from sqlalchemy import Column, String, DateTime, Boolean, JSON, Integer
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()


class DeviceDB(Base):
    """Device database table"""
    __tablename__ = "devices"

    id = Column(String, primary_key=True)
    user_id = Column(String, nullable=False, index=True)

    # Device identification
    platform = Column(String, nullable=False)
    token = Column(String, nullable=False)
    device_id = Column(String, nullable=True, index=True)

    # Device metadata
    device_name = Column(String, nullable=True)
    device_model = Column(String, nullable=True)
    os_version = Column(String, nullable=True)
    app_version = Column(String, nullable=True)

    # Additional metadata (renamed to avoid SQLAlchemy reserved word)
    device_metadata = Column("metadata", JSON, nullable=True)

    # Status
    is_active = Column(Boolean, default=True)
    last_used_at = Column(DateTime, nullable=True)

    # Timestamps
    created_at = Column(DateTime, nullable=False)
    updated_at = Column(DateTime, nullable=False)

    def to_device(self) -> Device:
        """Convert to Pydantic model"""
        return Device(
            id=self.id,
            user_id=self.user_id,
            platform=self.platform,
            token=self.token,
            device_id=self.device_id,
            device_name=self.device_name,
            device_model=self.device_model,
            os_version=self.os_version,
            app_version=self.app_version,
            metadata=self.device_metadata or {},
            is_active=self.is_active,
            last_used_at=self.last_used_at,
            created_at=self.created_at,
            updated_at=self.updated_at
        )

    @classmethod
    def from_device(cls, device: Device) -> "DeviceDB":
        """Create from Pydantic model"""
        return cls(
            id=device.id,
            user_id=device.user_id,
            platform=device.platform,
            token=device.token,
            device_id=device.device_id,
            device_name=device.device_name,
            device_model=device.device_model,
            os_version=device.os_version,
            app_version=device.app_version,
            device_metadata=device.metadata,
            is_active=device.is_active,
            last_used_at=device.last_used_at,
            created_at=device.created_at,
            updated_at=device.updated_at
        )
