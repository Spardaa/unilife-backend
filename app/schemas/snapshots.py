"""
Snapshot Schemas - Request and Response models for snapshots API
"""
from typing import List, Optional, Dict, Any
from datetime import datetime
from pydantic import BaseModel, Field


class EventChange(BaseModel):
    """Individual event change within a snapshot"""
    event_id: str = Field(..., description="Event ID")
    action: str = Field(..., description="Action type: create/update/delete")
    before: Optional[Dict[str, Any]] = Field(None, description="Event state before change")
    after: Optional[Dict[str, Any]] = Field(None, description="Event state after change")


class SnapshotResponse(BaseModel):
    """Snapshot response model"""
    id: str = Field(..., description="Snapshot ID")
    user_id: str = Field(..., description="User ID")
    trigger_message: str = Field(..., description="Message that triggered this change")
    trigger_time: datetime = Field(..., description="Time when change was triggered")
    changes: List[EventChange] = Field(..., description="List of event changes")
    is_reverted: bool = Field(default=False, description="Whether snapshot has been reverted")
    reverted_at: Optional[datetime] = Field(None, description="Time when snapshot was reverted")
    created_at: datetime = Field(..., description="Snapshot creation time")
    expires_at: datetime = Field(..., description="Snapshot expiration time")

    class Config:
        from_attributes = True


class SnapshotRevertResponse(BaseModel):
    """Response model for snapshot revert"""
    snapshot_id: str = Field(..., description="Reverted snapshot ID")
    message: str = Field(..., description="Revert confirmation message")
    reverted_events: List[str] = Field(..., description="List of reverted event IDs")
    reverted_at: datetime = Field(..., description="Revert timestamp")
