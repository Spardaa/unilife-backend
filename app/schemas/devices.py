"""
Device Schemas - Request and Response models for device management
"""
from typing import Dict, Any, Optional
from datetime import datetime
from pydantic import BaseModel, Field


class DeviceMetadata(BaseModel):
    """Additional device metadata"""
    locale: Optional[str] = Field(None, description="Device locale (e.g., en_US)")
    timezone: Optional[str] = Field(None, description="Device timezone")
    carrier: Optional[str] = Field(None, description="Mobile carrier (if applicable)")
    #[Additional platform-specific fields can be added here]


class DeviceRegisterRequest(BaseModel):
    """Request to register a new device"""
    platform: str = Field(..., description="Platform: ios, android, web")
    token: str = Field(..., description="Push notification token")
    device_id: Optional[str] = Field(None, description="Unique device identifier")
    device_name: Optional[str] = Field(None, description="Human-readable device name")
    device_model: Optional[str] = Field(None, description="Device model")
    os_version: Optional[str] = Field(None, description="OS version")
    app_version: Optional[str] = Field(None, description="App version")
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Additional metadata")


class DeviceUpdateRequest(BaseModel):
    """Request to update device information"""
    device_name: Optional[str] = None
    is_active: Optional[bool] = None
    metadata: Optional[Dict[str, Any]] = None


class DeviceResponse(BaseModel):
    """Device response"""
    id: str = Field(..., description="Device ID")
    user_id: str = Field(..., description="User ID")
    platform: str = Field(..., description="Platform")
    token: str = Field(..., description="Push token (masked)")
    device_id: Optional[str] = None
    device_name: Optional[str] = None
    device_model: Optional[str] = None
    os_version: Optional[str] = None
    app_version: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)
    is_active: bool = Field(..., description="Active status")
    last_used_at: Optional[datetime] = None
    created_at: datetime = Field(..., description="Registration time")
    updated_at: datetime = Field(..., description="Last update time")

    class Config:
        from_attributes = True


class DeviceListResponse(BaseModel):
    """Response for device list endpoint"""
    devices: list[DeviceResponse] = Field(..., description="List of devices")
    total: int = Field(..., description="Total number of devices")
