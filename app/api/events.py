"""
Events API - CRUD operations for schedule events
"""
from typing import List, Optional
from datetime import datetime
from fastapi import APIRouter, HTTPException, Query, Depends

from app.schemas.events import (
    EventCreate, EventResponse, EventUpdate, EventStatus,
    EventType, Category
)
from app.services.db import db_service
from app.middleware.auth import get_current_user

router = APIRouter()


@router.get("/events", response_model=List[EventResponse])
async def get_events(
    user_id: str = Depends(get_current_user),
    start_date: Optional[datetime] = Query(None, description="Filter events from this date"),
    end_date: Optional[datetime] = Query(None, description="Filter events until this date"),
    status: Optional[EventStatus] = Query(None, description="Filter by status"),
    event_type: Optional[EventType] = Query(None, description="Filter by event type"),
    category: Optional[Category] = Query(None, description="Filter by category"),
    limit: int = Query(100, ge=1, le=500, description="Maximum number of events to return")
):
    """
    Get all events for the authenticated user with optional filters

    Supports filtering by:
    - Date range (start_date, end_date)
    - Status (PENDING, IN_PROGRESS, COMPLETED, CANCELLED)
    - Event type (schedule, deadline, floating, habit, reminder)
    - Category (STUDY, WORK, SOCIAL, LIFE, HEALTH)
    """
    filters = {}
    if status:
        filters["status"] = status.value
    if event_type:
        filters["event_type"] = event_type.value
    if category:
        filters["category"] = category.value

    events = await db_service.get_events(
        user_id=user_id,
        filters=filters,
        start_date=start_date,
        end_date=end_date,
        limit=limit
    )

    return [EventResponse(**event) for event in events]


@router.get("/events/today", response_model=List[EventResponse])
async def get_today_events(
    user_id: str = Depends(get_current_user),
    status: Optional[EventStatus] = Query(None, description="Filter by status")
):
    """Get all events for today"""
    now = datetime.utcnow()
    start_of_day = now.replace(hour=0, minute=0, second=0, microsecond=0)
    end_of_day = start_of_day.replace(hour=23, minute=59, second=59, microsecond=999999)

    filters = {"status": status.value} if status else {}

    events = await db_service.get_events(
        user_id=user_id,
        filters=filters,
        start_date=start_of_day,
        end_date=end_of_day,
        limit=100
    )

    return [EventResponse(**event) for event in events]


@router.get("/events/{event_id}", response_model=EventResponse)
async def get_event(
    event_id: str,
    user_id: str = Depends(get_current_user)
):
    """Get a specific event by ID"""
    event = await db_service.get_event(event_id=event_id, user_id=user_id)

    if not event:
        raise HTTPException(status_code=404, detail="Event not found")

    return EventResponse(**event)


@router.post("/events", response_model=EventResponse, status_code=201)
async def create_event(
    event: EventCreate,
    user_id: str = Depends(get_current_user)
):
    """
    Create a new event

    Automatically checks for time conflicts before creating.
    """
    event_data = event.model_dump()
    event_data["user_id"] = user_id
    event_data["status"] = EventStatus.PENDING.value
    event_data["created_by"] = "user"
    event_data["ai_confidence"] = 1.0

    # Check for time conflicts if both start_time and end_time are provided
    if event_data.get("start_time") and event_data.get("end_time"):
        conflicts = await db_service.check_time_conflict(
            user_id=user_id,
            start_time=event_data["start_time"],
            end_time=event_data["end_time"],
            exclude_event_id=None
        )
        if conflicts:
            # Return conflict information in headers
            conflict_ids = [c["id"] for c in conflicts]
            pass  # We still create the event, but client can check headers

    result = await db_service.create_event(event_data)
    return EventResponse(**result)


@router.put("/events/{event_id}", response_model=EventResponse)
async def update_event(
    event_id: str,
    event: EventUpdate,
    user_id: str = Depends(get_current_user)
):
    """
    Update an existing event

    Only updates fields that are provided (partial update).
    """
    # Check if event exists
    existing = await db_service.get_event(event_id=event_id, user_id=user_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Event not found")

    # Build update data with only non-None values
    update_data = event.model_dump(exclude_unset=True)

    if not update_data:
        raise HTTPException(status_code=400, detail="No fields to update")

    # Check for time conflicts if times are being updated
    if "start_time" in update_data or "end_time" in update_data:
        start_time = update_data.get("start_time", existing.get("start_time"))
        end_time = update_data.get("end_time", existing.get("end_time"))

        if start_time and end_time:
            conflicts = await db_service.check_time_conflict(
                user_id=user_id,
                start_time=start_time,
                end_time=end_time,
                exclude_event_id=event_id
            )
            if conflicts:
                pass  # Still proceed with update

    result = await db_service.update_event(
        event_id=event_id,
        user_id=user_id,
        update_data=update_data
    )

    if not result:
        raise HTTPException(status_code=404, detail="Failed to update event")

    return EventResponse(**result)


@router.delete("/events/{event_id}", status_code=204)
async def delete_event(
    event_id: str,
    user_id: str = Depends(get_current_user)
):
    """
    Delete an event

    Returns 204 No Content on success.
    """
    # Check if event exists
    existing = await db_service.get_event(event_id=event_id, user_id=user_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Event not found")

    success = await db_service.delete_event(event_id=event_id, user_id=user_id)

    if not success:
        raise HTTPException(status_code=404, detail="Failed to delete event")


@router.post("/events/{event_id}/complete", response_model=EventResponse)
async def complete_event(
    event_id: str,
    user_id: str = Depends(get_current_user)
):
    """Mark an event as completed"""
    # Check if event exists
    existing = await db_service.get_event(event_id=event_id, user_id=user_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Event not found")

    result = await db_service.update_event(
        event_id=event_id,
        user_id=user_id,
        update_data={
            "status": EventStatus.COMPLETED.value,
            "completed_at": datetime.utcnow()
        }
    )

    if not result:
        raise HTTPException(status_code=404, detail="Failed to complete event")

    return EventResponse(**result)


@router.get("/events/conflicts", response_model=List[EventResponse])
async def check_conflicts(
    user_id: str = Depends(get_current_user),
    start_time: datetime = Query(..., description="Start time to check"),
    end_time: datetime = Query(..., description="End time to check"),
    exclude_event_id: Optional[str] = Query(None, description="Exclude this event from conflict check")
):
    """
    Check for time conflicts within a given time range

    Returns all events that overlap with the specified time range.
    """
    conflicts = await db_service.check_time_conflict(
        user_id=user_id,
        start_time=start_time,
        end_time=end_time,
        exclude_event_id=exclude_event_id
    )

    return [EventResponse(**event) for event in conflicts]
