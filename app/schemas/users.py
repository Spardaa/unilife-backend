"""
User Schemas - Request and Response models for users API
"""
from typing import Dict, Any, Optional
from datetime import datetime
from pydantic import BaseModel, Field


class UserPreferences(BaseModel):
    """User preferences"""
    notification_enabled: bool = True
    auto_schedule_enabled: bool = True
    energy_based_scheduling: bool = True
    working_hours_start: int = 9
    working_hours_end: int = 18


class EnergyProfile(BaseModel):
    """Energy profile for user"""
    # Default energy curve (hourly baseline)
    hourly_baseline: Dict[int, int] = Field(
        default_factory=lambda: {
            6: 40, 7: 50, 8: 70, 9: 80, 10: 90, 11: 85,
            12: 70, 13: 65, 14: 60, 15: 70, 16: 75, 17: 65,
            18: 60, 19: 55, 20: 50, 21: 40, 22: 30, 23: 20
        },
        description="Hourly baseline energy values"
    )

    # Task energy cost/recovery
    task_energy_cost: Dict[str, int] = Field(
        default_factory=lambda: {
            "deep_work": -20,
            "meeting": -10,
            "study": -15,
            "break": +15,
            "coffee": +10,
            "sleep": +100
        },
        description="Energy impact of different task types"
    )

    # Learned adjustments
    learned_adjustments: Dict[str, Any] = Field(
        default_factory=dict,
        description="Personalized adjustments learned from behavior"
    )


class UserBase(BaseModel):
    """Base user model"""
    nickname: str = Field(..., description="User nickname")
    timezone: str = Field(default="Asia/Shanghai", description="User timezone")


class UserCreate(UserBase):
    """Create user model"""
    email: Optional[str] = Field(None, description="User email")
    phone: Optional[str] = Field(None, description="User phone")
    wechat_id: Optional[str] = Field(None, description="WeChat ID")


class UserUpdate(BaseModel):
    """Update user model - all fields optional"""
    nickname: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    wechat_id: Optional[str] = None
    avatar_url: Optional[str] = None
    timezone: Optional[str] = None
    preferences: Optional[UserPreferences] = None


class EnergyProfileUpdate(BaseModel):
    """Update energy profile model"""
    hourly_baseline: Optional[Dict[int, int]] = None
    task_energy_cost: Optional[Dict[str, int]] = None
    learned_adjustments: Optional[Dict[str, Any]] = None


class UserResponse(UserBase):
    """User response model"""
    id: str = Field(..., description="User ID")
    email: Optional[str] = None
    phone: Optional[str] = None
    wechat_id: Optional[str] = None
    avatar_url: Optional[str] = None
    energy_profile: EnergyProfile = Field(..., description="User energy profile")
    current_energy: int = Field(default=100, ge=0, le=100, description="Current energy value")
    preferences: UserPreferences = Field(..., description="User preferences")
    created_at: datetime = Field(..., description="Creation timestamp")
    last_active_at: datetime = Field(..., description="Last activity timestamp")

    class Config:
        from_attributes = True
