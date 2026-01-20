"""
Events API - CRUD operations for schedule events
"""
from typing import List
from fastapi import APIRouter, HTTPException

from app.schemas.events import EventCreate, EventResponse, EventUpdate

router = APIRouter()


@router.get("/events", response_model=List[EventResponse])
async def get_events():
    """Get all events for the authenticated user"""
    raise HTTPException(status_code=501, detail="Not implemented yet")


@router.post("/events", response_model=EventResponse)
async def create_event(event: EventCreate):
    """Create a new event"""
    raise HTTPException(status_code=501, detail="Not implemented yet")


@router.get("/events/{event_id}", response_model=EventResponse)
async def get_event(event_id: str):
    """Get a specific event by ID"""
    raise HTTPException(status_code=501, detail="Not implemented yet")


@router.put("/events/{event_id}", response_model=EventResponse)
async def update_event(event_id: str, event: EventUpdate):
    """Update an existing event"""
    raise HTTPException(status_code=501, detail="Not implemented yet")


@router.delete("/events/{event_id}")
async def delete_event(event_id: str):
    """Delete an event"""
    raise HTTPException(status_code=501, detail="Not implemented yet")
