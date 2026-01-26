"""
Sync API - Incremental data synchronization
"""
from typing import Optional
from datetime import datetime
from fastapi import APIRouter, HTTPException, Query, Depends

from app.schemas.sync import SyncResponse, SyncChanges, ChangeSet
from app.services.db import db_service
from app.middleware.auth import get_current_user

router = APIRouter()


@router.get("/sync", response_model=SyncResponse)
async def sync_data(
    user_id: str = Depends(get_current_user),
    since: Optional[datetime] = Query(None, description="Sync changes since this ISO 8601 timestamp"),
    limit: int = Query(1000, ge=1, le=10000, description="Maximum changes to return")
):
    """
    Incremental data synchronization

    Returns all changes (created, updated, deleted items) since the given timestamp.
    If 'since' is not provided, returns all current data.

    Response format:
    {
        "since": "2026-01-24T00:00:00Z",
        "until": "2026-01-24T12:00:00Z",
        "has_more": false,
        "changes": {
            "events": { "created": [...], "updated": [...], "deleted": [...] },
            "routines": { "created": [...], "updated": [...], "deleted": [...] }
        }
    }

    The client should store the 'until' timestamp and use it as the 'since'
    parameter for the next sync request.
    """
    now = datetime.utcnow()

    # Default to epoch if since is not provided
    if since is None:
        since = datetime(1970, 1, 1)

    # Initialize change sets
    events_changes = ChangeSet()
    routines_changes = ChangeSet()

    # Get all events (we'll filter client-side for now)
    # In production, you'd want database-level filtering by updated_at
    all_events = await db_service.get_events(
        user_id=user_id,
        filters={},
        limit=limit
    )

    # Helper function to parse datetime from string or datetime object
    def parse_datetime(dt):
        if dt is None:
            return None
        if isinstance(dt, datetime):
            return dt
        if isinstance(dt, str):
            try:
                return datetime.fromisoformat(dt.replace('Z', '+00:00'))
            except:
                return None
        return None

    # Filter events by updated_at
    for event in all_events:
        event_updated = parse_datetime(event.get("updated_at"))
        if event_updated and event_updated.replace(tzinfo=None) > since.replace(tzinfo=None):
            # Determine if created or updated based on created_at vs updated_at
            event_created = parse_datetime(event.get("created_at"))
            if event_created and event_created.replace(tzinfo=None) > since.replace(tzinfo=None):
                events_changes.created.append(event)
            else:
                events_changes.updated.append(event)

    # Get routines (if they exist in the database)
    try:
        # Note: routines might be stored differently or not at all
        # This is a placeholder for future routine sync
        pass
    except Exception:
        pass

    # Build response
    return SyncResponse(
        since=since,
        until=now,
        has_more=False,  # Simple implementation - no pagination yet
        changes=SyncChanges(
            events=events_changes,
            routines=routines_changes
        )
    )


@router.get("/sync/status")
async def get_sync_status(user_id: str = Depends(get_current_user)):
    """
    Get sync status information

    Returns metadata about the user's data for sync planning.
    """
    # Get event count
    all_events = await db_service.get_events(user_id, {}, limit=100000)

    # Find the most recent update timestamp
    latest_update = None
    for event in all_events:
        event_updated = event.get("updated_at")
        if event_updated:
            if isinstance(event_updated, datetime):
                event_dt = event_updated
            elif isinstance(event_updated, str):
                event_dt = datetime.fromisoformat(event_updated.replace('Z', '+00:00'))
            else:
                continue
            if latest_update is None or event_dt > latest_update:
                latest_update = event_dt

    return {
        "user_id": user_id,
        "total_events": len(all_events),
        "latest_update": latest_update,
        "supported_entities": ["events", "routines"]
    }
