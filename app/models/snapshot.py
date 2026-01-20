"""
Snapshot Model - Database model for schedule snapshots
"""
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
from pydantic import BaseModel, Field
import uuid


class EventChange(BaseModel):
    """Individual event change within a snapshot"""
    event_id: str = Field(..., description="Event ID")
    action: str = Field(..., description="Action type: create/update/delete")
    before: Optional[Dict[str, Any]] = Field(None, description="Event state before change")
    after: Optional[Dict[str, Any]] = Field(None, description="Event state after change")

    class Config:
        json_schema_extra = {
            "example": {
                "event_id": "event-123",
                "action": "update",
                "before": {"title": "旧标题", "start_time": "2026-01-20T10:00:00"},
                "after": {"title": "新标题", "start_time": "2026-01-20T14:00:00"}
            }
        }


class Snapshot(BaseModel):
    """Snapshot model for schedule changes"""

    # Primary key
    id: str = Field(default_factory=lambda: str(uuid.uuid4()), description="Snapshot UUID")

    # User reference
    user_id: str = Field(..., description="User ID")

    # Trigger information
    trigger_message: str = Field(..., description="Message that triggered this change")
    trigger_time: datetime = Field(default_factory=datetime.utcnow, description="Time when change was triggered")

    # Changes
    changes: List[EventChange] = Field(..., description="List of event changes")

    # Revert information
    is_reverted: bool = Field(default=False, description="Whether snapshot has been reverted")
    reverted_at: Optional[datetime] = Field(None, description="Time when snapshot was reverted")

    # Metadata
    created_at: datetime = Field(default_factory=datetime.utcnow, description="Snapshot creation time")
    expires_at: datetime = Field(
        default_factory=lambda: datetime.utcnow() + timedelta(days=30),
        description="Snapshot expiration time (30 days)"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "id": "550e8400-e29b-41d4-a716-446655440000",
                "user_id": "user-123",
                "trigger_message": "把会议改到下午3点",
                "trigger_time": "2026-01-20T10:00:00",
                "changes": [
                    {
                        "event_id": "event-456",
                        "action": "update",
                        "before": {"start_time": "2026-01-20T10:00:00"},
                        "after": {"start_time": "2026-01-20T15:00:00"}
                    }
                ],
                "is_reverted": False,
                "reverted_at": None,
                "created_at": "2026-01-20T10:00:00",
                "expires_at": "2026-02-19T10:00:00"
            }
        }

    def to_dict(self) -> dict:
        """Convert model to dictionary for database storage"""
        return self.model_dump(mode='json')

    @classmethod
    def from_dict(cls, data: dict) -> "Snapshot":
        """Create Snapshot from dictionary (from database)"""
        return cls(**data)

    def mark_reverted(self):
        """Mark this snapshot as reverted"""
        self.is_reverted = True
        self.reverted_at = datetime.utcnow()
