"""
Sync Schemas - Request and Response models for incremental sync API
"""
from typing import Dict, Any, List, Optional
from datetime import datetime
from pydantic import BaseModel, Field


class ChangeSet(BaseModel):
    """Set of changes for a specific entity type"""
    created: List[Dict[str, Any]] = Field(default_factory=list, description="Newly created items")
    updated: List[Dict[str, Any]] = Field(default_factory=list, description="Updated items")
    deleted: List[str] = Field(default_factory=list, description="IDs of deleted items")


class SyncChanges(BaseModel):
    """All changes across all entity types"""
    events: ChangeSet = Field(default_factory=ChangeSet)
    routines: ChangeSet = Field(default_factory=ChangeSet)


class SyncResponse(BaseModel):
    """
    Incremental sync response

    Returns all changes that occurred since the given timestamp.
    """
    since: datetime = Field(..., description="Start of sync window")
    until: datetime = Field(..., description="End of sync window (current time)")
    has_more: bool = Field(default=False, description="Whether there are more changes to fetch")
    changes: SyncChanges = Field(..., description="All changes grouped by entity type")


class SyncRequest(BaseModel):
    """Sync request parameters"""
    since: Optional[datetime] = Field(None, description="Sync changes since this time (ISO 8601)")
    limit: int = Field(default=1000, ge=1, le=10000, description="Maximum changes to return")
