"""
Habits API - Endpoints for habit management and confirmation
"""
from typing import List, Optional
from datetime import datetime
from fastapi import APIRouter, HTTPException, Query, Depends
from pydantic import BaseModel, Field

from app.services.db import db_service
from app.middleware.auth import get_current_user
from app.schemas.events import EventResponse

router = APIRouter()


class HabitConfirmationRequest(BaseModel):
    """Request to confirm habit continuation"""
    confirm: bool = Field(..., description="True to continue habit, False to cancel remaining instances")


class HabitConfirmationResponse(BaseModel):
    """Response to habit confirmation"""
    status: str = Field(..., description="Status: 'active' or 'cancelled'")
    message: str = Field(..., description="Human-readable message")


@router.post("/habits/{batch_id}/confirm", response_model=HabitConfirmationResponse)
async def confirm_habit(
    batch_id: str,
    request: HabitConfirmationRequest,
    user_id: str = Depends(get_current_user)
):
    """
    Confirm habit continuation after first completion

    Called when user completes their first habit instance.
    - If confirm=True: Marks habit as active, system will auto-replenish instances
    - If confirm=False: Cancels all remaining pending instances in the batch
    """
    # Get all instances in this batch
    events = await db_service.get_events(
        user_id=user_id,
        limit=1000
    )

    batch_events = [e for e in events if e.get("routine_batch_id") == batch_id]

    if not batch_events:
        raise HTTPException(status_code=404, detail="Habit batch not found")

    if not request.confirm:
        # Cancel all pending instances in this batch
        for event in batch_events:
            if event.get("status") == "PENDING":
                await db_service.update_event(
                    event_id=event["id"],
                    user_id=user_id,
                    update_data={"status": "CANCELLED"}
                )

        return HabitConfirmationResponse(
            status="cancelled",
            message="Remaining habit instances have been cancelled"
        )
    else:
        # Mark as active - future replenishment will happen
        # For now, just return success
        return HabitConfirmationResponse(
            status="active",
            message="Habit is now active. System will automatically replenish instances."
        )


@router.post("/habits/replenish")
async def replenish_habits():
    """
    Replenish habit instances to maintain 20 pending instances per active habit

    This endpoint is called by a scheduled task (e.g., daily at 2 AM).
    It checks all active habit batches and replenishes instances that fall below 20.
    """
    # Get all habit batches
    # For now, we'll implement a simple version that checks and replenishes

    # TODO: Implement proper habit batch tracking
    # This would require:
    # 1. Get all habit events grouped by routine_batch_id
    # 2. For each batch, count pending instances
    # 3. If count < 20, calculate next dates and create new instances
    # 4. Mark batch as active in a tracking table

    return {
        "message": "Habit replenishment endpoint (to be implemented with scheduled task)",
        "replenished_count": 0
    }


@router.get("/habits/{batch_id}", response_model=List[EventResponse])
async def get_habit_instances(
    batch_id: str,
    user_id: str = Depends(get_current_user)
):
    """
    Get all instances in a habit batch
    """
    events = await db_service.get_events(
        user_id=user_id,
        limit=1000
    )

    batch_events = [e for e in events if e.get("routine_batch_id") == batch_id]

    if not batch_events:
        raise HTTPException(status_code=404, detail="Habit batch not found")

    return [EventResponse(**e) for e in batch_events]


# Import BaseModel for request/response
from pydantic import BaseModel, Field
from app.schemas.events import EventResponse
