"""
Memory Model - Database model for user memory and learning
"""
from typing import Dict, Any, Optional, List
from datetime import datetime
from pydantic import BaseModel, Field
from app.models.user import SocialProfile


class ContactInfo(BaseModel):
    """Contact information"""
    name: str
    user_id: Optional[str] = None
    contact_user_id: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None


class UserMemory(BaseModel):
    """User memory model for habit learning and personalization"""

    # User reference
    user_id: str = Field(..., description="User ID")

    # Time preference learning
    time_preferences: Dict[str, Any] = Field(
        default_factory=dict,
        description="Learned time preferences"
    )

    # Social profile
    social_profile: SocialProfile = Field(
        default_factory=SocialProfile,
        description="Social contacts and relationships"
    )

    # Behavior statistics
    behavior_stats: Dict[str, Any] = Field(
        default_factory=dict,
        description="User behavior statistics"
    )

    # Conversation summary
    conversation_summary: str = Field(
        default="",
        description="Summary of recent conversations"
    )

    # Metadata
    updated_at: datetime = Field(
        default_factory=datetime.utcnow,
        description="Last update timestamp"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "user_id": "user-123",
                "time_preferences": {
                    "deep_work_preferred_hours": [9, 10, 11],
                    "meeting_preferred_hours": [14, 15],
                    "break_preferred_intervals": [12, 18]
                },
                "social_profile": {
                    "contacts": {
                        "friend-1": {"name": "张三", "contact_user_id": "user_123"}
                    },
                    "relationships": {"friend-1": "friend"},
                    "intimacy_scores": {"friend-1": 0.8}
                },
                "behavior_stats": {
                    "avg_task_overrun_ratio": 1.2,
                    "common_locations": ["图书馆", "咖啡厅"],
                    "preferred_break_duration": 15,
                    "max_continuous_work_duration": 180
                },
                "conversation_summary": "用户喜欢在上午处理深度工作...",
                "updated_at": "2026-01-20T10:00:00"
            }
        }

    def to_dict(self) -> dict:
        """Convert model to dictionary for database storage"""
        return self.model_dump(mode='json')

    @classmethod
    def from_dict(cls, data: dict) -> "UserMemory":
        """Create UserMemory from dictionary (from database)"""
        return cls(**data)

    def update_time_preference(self, key: str, value: Any):
        """Update a time preference"""
        if key not in self.time_preferences:
            self.time_preferences[key] = []
        if isinstance(self.time_preferences[key], list):
            if value not in self.time_preferences[key]:
                self.time_preferences[key].append(value)
        else:
            self.time_preferences[key] = value
        self.updated_at = datetime.utcnow()

    def add_contact(self, contact_id: str, name: str, relationship: str = "other"):
        """Add a contact to social profile"""
        contact = ContactInfo(name=name)
        self.social_profile.contacts[contact_id] = contact
        self.social_profile.relationships[contact_id] = relationship
        self.social_profile.intimacy_scores[contact_id] = 0.5  # Default intimacy
        self.updated_at = datetime.utcnow()

    def update_behavior_stat(self, key: str, value: Any):
        """Update a behavior statistic"""
        self.behavior_stats[key] = value
        self.updated_at = datetime.utcnow()
