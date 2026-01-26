"""
User Model - Database model for users
"""
from typing import Dict, Any, Optional
from datetime import datetime
from pydantic import BaseModel, Field
import uuid


class UserPreferences(BaseModel):
    """User preferences"""
    notification_enabled: bool = True
    auto_schedule_enabled: bool = True
    energy_based_scheduling: bool = True
    working_hours_start: int = 9
    working_hours_end: int = 18

    class Config:
        json_schema_extra = {
            "example": {
                "notification_enabled": True,
                "auto_schedule_enabled": True,
                "energy_based_scheduling": True,
                "working_hours_start": 9,
                "working_hours_end": 18
            }
        }


class EnergyProfile(BaseModel):
    """Energy profile for user"""

    # Default energy curve (hourly baseline)
    hourly_baseline: Dict[int, int] = Field(
        default_factory=lambda: {
            6: 40, 7: 50, 8: 70, 9: 80, 10: 90, 11: 85,
            12: 70, 13: 65, 14: 60, 15: 70, 16: 75, 17: 65,
            18: 60, 19: 55, 20: 50, 21: 40, 22: 30, 23: 20
        },
        description="Hourly baseline energy values (0-100)"
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

    class Config:
        json_schema_extra = {
            "example": {
                "hourly_baseline": {
                    "9": 80, "10": 90, "11": 85, "14": 60, "15": 70
                },
                "task_energy_cost": {
                    "deep_work": -20,
                    "meeting": -10,
                    "break": +15
                },
                "learned_adjustments": {
                    "deep_work_preferred_hours": [9, 10, 11]
                }
            }
        }

    def get_energy_at_hour(self, hour: int) -> int:
        """Get baseline energy at specific hour"""
        return self.hourly_baseline.get(hour, 50)

    def get_task_cost(self, task_type: str) -> int:
        """Get energy cost for task type"""
        return self.task_energy_cost.get(task_type, 0)


class ContactInfo(BaseModel):
    """Contact information for social profile"""
    name: str
    user_id: Optional[str] = None
    contact_user_id: Optional[str] = None
    email: Optional[str] = None


class SocialProfile(BaseModel):
    """Social profile for user memory"""
    contacts: Dict[str, ContactInfo] = Field(default_factory=dict, description="Contact information")
    relationships: Dict[str, str] = Field(default_factory=dict, description="Relationship types")
    intimacy_scores: Dict[str, float] = Field(default_factory=dict, description="Intimacy scores")

    class Config:
        json_schema_extra = {
            "example": {
                "contacts": {
                    "friend-1": {"name": "张三", "contact_user_id": "user_123"}
                },
                "relationships": {"friend-1": "friend"},
                "intimacy_scores": {"friend-1": 0.8}
            }
        }


class User(BaseModel):
    """User model"""

    # Primary key
    id: str = Field(default_factory=lambda: str(uuid.uuid4()), description="User UUID")

    # Authentication (unified account system)
    email: Optional[str] = Field(None, description="User email")
    phone: Optional[str] = Field(None, description="User phone")
    user_id: Optional[str] = Field(None, description="User ID")

    # Personal info
    nickname: str = Field(..., description="User nickname")
    avatar_url: Optional[str] = Field(None, description="Avatar URL")
    timezone: str = Field(default="Asia/Shanghai", description="User timezone")

    # Energy management
    energy_profile: EnergyProfile = Field(default_factory=EnergyProfile, description="Energy template")
    current_energy: int = Field(default=100, ge=0, le=100, description="Current energy value")

    # Preferences
    preferences: UserPreferences = Field(default_factory=UserPreferences, description="User preferences")

    # Metadata
    created_at: datetime = Field(default_factory=datetime.utcnow, description="Creation timestamp")
    last_active_at: datetime = Field(default_factory=datetime.utcnow, description="Last activity timestamp")

    class Config:
        json_schema_extra = {
            "example": {
                "id": "550e8400-e29b-41d4-a716-446655440000",
                "email": "user@example.com",
                "user_id": "user_abc123",
                "nickname": "Alex",
                "avatar_url": "https://example.com/avatar.jpg",
                "timezone": "Asia/Shanghai",
                "energy_profile": {
                    "hourly_baseline": {"9": 80, "10": 90, "11": 85},
                    "task_energy_cost": {"deep_work": -20, "meeting": -10}
                },
                "current_energy": 85,
                "preferences": {
                    "notification_enabled": True,
                    "auto_schedule_enabled": True
                },
                "created_at": "2026-01-01T00:00:00",
                "last_active_at": "2026-01-20T10:00:00"
            }
        }

    def to_dict(self) -> dict:
        """Convert model to dictionary for database storage"""
        return self.model_dump(mode='json')

    @classmethod
    def from_dict(cls, data: dict) -> "User":
        """Create User from dictionary (from database)"""
        return cls(**data)
