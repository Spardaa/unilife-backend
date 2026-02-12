"""
Events API - CRUD operations for schedule events
"""
from typing import List, Optional
from datetime import datetime
from fastapi import APIRouter, HTTPException, Query, Depends

from app.schemas.events import (
    EventCreate, EventResponse, EventUpdate, EventStatus,
    EventType, Category, TimePeriod, CreateInstanceRequest, EventsResponse
)
from app.services.db import db_service
from app.services.virtual_expansion import virtual_expansion_service
from app.middleware.auth import get_current_user

router = APIRouter()


@router.get("/events", response_model=EventsResponse)
async def get_events(
    user_id: str = Depends(get_current_user),
    start_date: Optional[datetime] = Query(None, description="Filter events from this date"),
    end_date: Optional[datetime] = Query(None, description="Filter events until this date"),
    status: Optional[EventStatus] = Query(None, description="Filter by status"),
    event_type: Optional[EventType] = Query(None, description="Filter by event type"),
    category: Optional[Category] = Query(None, description="Filter by category"),
    time_period: Optional[TimePeriod] = Query(None, description="Filter by time period (ANYTIME/MORNING/AFTERNOON/NIGHT)"),
    project_id: Optional[str] = Query(None, description="Filter by project ID"),
    include_templates: bool = Query(False, description="Include template events in response (deprecated, kept for compatibility)"),
    expand_virtual: bool = Query(True, description="Expand recurring templates into virtual instances"),
    limit: int = Query(500, ge=1, le=1000, description="Maximum number of events to return")
):
    """
    Get all events for the authenticated user with optional filters.

    NEW: Returns virtual instances for recurring events by default.
    Virtual instances are computed on-demand and NOT persisted to database.

    Returns a structured response with:
    - instances: Real event instances + virtual instances (if expand_virtual=True)
    - templates: Template events (only if include_templates=True)

    Supports filtering by:
    - Date range (start_date, end_date)
    - Status (PENDING, IN_PROGRESS, COMPLETED, CANCELLED)
    - Event type (schedule, deadline, floating, habit, reminder)
    - Category (STUDY, WORK, SOCIAL, LIFE, HEALTH)
    - Time period (ANYTIME, MORNING, AFTERNOON, NIGHT)
    - Project ID
    """
    from datetime import timedelta

    filters = {}
    if status:
        filters["status"] = status.value
    if event_type:
        filters["event_type"] = event_type.value
    if category:
        filters["category"] = category.value
    if time_period:
        filters["time_period"] = time_period.value
    if project_id:
        filters["project_id"] = project_id

    # Determine date range for expansion
    # If no range specified, use current month
    if not start_date or not end_date:
        now = datetime.utcnow()
        if not start_date:
            start_date = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        if not end_date:
            # End of current month
            next_month = start_date.replace(day=28) + timedelta(days=4)
            end_date = next_month.replace(day=1) - timedelta(seconds=1)

    # Get real instances (exclude templates)
    instances = await db_service.get_events(
        user_id=user_id,
        filters=filters,
        start_date=start_date,
        end_date=end_date,
        limit=limit
    )

    # Filter out templates from instances
    real_instances = [evt for evt in instances if not evt.get("is_template")]

    # Validate real instances
    validated_instances = []
    for event in real_instances:
        try:
            validated_instances.append(EventResponse(**event))
        except Exception as e:
            print(f"⚠️ Failed to validate event {event.get('id')}: {e}")
            if "energy_consumption" in event:
                event_copy = event.copy()
                del event_copy["energy_consumption"]
                validated_instances.append(EventResponse(**event_copy))
            else:
                print(f"❌ Skipping invalid event {event.get('id')}")

    # Expand virtual instances if requested
    virtual_instances = []
    if expand_virtual:
        # Get all templates
        templates = await db_service.get_recurring_templates(user_id)

        # Expand within date range
        virtual_dicts = virtual_expansion_service.expand_templates(
            templates=templates,
            real_instances=real_instances,
            start_date=start_date,
            end_date=end_date
        )

        # Convert to EventResponse
        for v in virtual_dicts:
            try:
                virtual_instances.append(EventResponse(**v))
            except Exception as e:
                print(f"⚠️ Failed to validate virtual instance: {e}")

    all_instances = validated_instances + virtual_instances

    # For backward compatibility, include templates only if explicitly requested
    templates_response = []
    if include_templates:
        template_events = await db_service.get_recurring_templates(user_id)
        for event in template_events:
            try:
                templates_response.append(EventResponse(**event))
            except Exception as e:
                print(f"⚠️ Failed to validate template: {e}")

    return EventsResponse(
        instances=all_instances,
        templates=templates_response
    )


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

    validated_events = []
    for event in events:
        try:
            validated_events.append(EventResponse(**event))
        except Exception as e:
            # 记录错误，使用默认值或跳过
            print(f"⚠️ Failed to validate event {event.get('id')}: {e}")
            # 清理无效的 energy_consumption 字段
            if "energy_consumption" in event:
                event_copy = event.copy()
                del event_copy["energy_consumption"]
                validated_events.append(EventResponse(**event_copy))
            else:
                # 如果删除 energy_consumption 还是不行，记录事件ID并跳过
                print(f"❌ Skipping invalid event {event.get('id')}")

    return validated_events


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


@router.post("/events", response_model=dict, status_code=201)
async def create_event(
    event: EventCreate,
    user_id: str = Depends(get_current_user)
):
    """
    Create a new event

    Supports:
    - Regular events: Direct creation
    - Recurring events (with repeat_pattern or habit_interval): Creates template ONLY
      - Instances are created on-demand when user marks complete or edits
      - Client-side virtually expands templates for display

    New Architecture (Lazy Instance Creation):
    - Habit events: Convert habit_interval to repeat_pattern, create template only
    - Routine events: Create template only, no pre-generated instances
    """
    event_data = event.model_dump()
    event_data["user_id"] = user_id
    event_data["status"] = EventStatus.PENDING.value
    event_data["created_by"] = "user"
    event_data["ai_confidence"] = 1.0

    # Debug: Print received event_date
    print(f"📝 API: Received event_date: {event_data.get('event_date')}")

    # Auto-derive event_date from start_time if not provided
    if event_data.get("event_date") is None and event_data.get("start_time") is not None:
        start_time = event_data["start_time"]
        # Extract date part (start of day) from start_time
        from datetime import datetime, time
        event_data["event_date"] = datetime.combine(start_time.date(), time.min)
        print(f"📝 API: Derived event_date from start_time: {event_data['event_date']}")

    # Check if this is a Habit event
    if event_data.get("event_type") == "habit" or event_data.get("habit_interval") is not None:
        # Convert habit to template-based architecture
        import uuid

        # Get interval (default to 1 day)
        interval = event_data.get("habit_interval", 1)

        # Get start date
        start_date = event_data.get("event_date") or event_data.get("start_time")
        if start_date is None:
            from datetime import datetime
            start_date = datetime.utcnow()
        elif isinstance(start_date, str):
            from datetime import datetime
            start_date = datetime.fromisoformat(start_date.replace('Z', '+00:00'))

        # Convert habit_interval to repeat_pattern
        # If interval is 1, use "daily" type
        # If interval > 1, we'll need to handle this differently (custom pattern)
        if interval == 1:
            repeat_pattern = {
                "type": "daily"
            }
        else:
            # For intervals > 1 day, we use a custom pattern
            # This will need special handling in the client-side expansion
            repeat_pattern = {
                "type": "custom",
                "interval_days": interval  # Custom field for non-daily intervals
            }

        # Extract time from start_time if available
        if event_data.get("start_time"):
            from datetime import datetime
            start_time = event_data["start_time"]
            if isinstance(start_time, str):
                start_time = datetime.fromisoformat(start_time.replace('Z', '+00:00'))
            repeat_pattern["time"] = start_time.strftime("%H:%M")

        event_data["repeat_pattern"] = repeat_pattern
        event_data["is_template"] = True
        event_data["parent_event_id"] = None

        # Create the template only (NO instances generated upfront)
        template = await db_service.create_event(event_data)

        print(f"✅ Created habit template: {template['id']} with repeat_pattern: {repeat_pattern}")

        return {
            "type": "habit",
            "template": EventResponse(**template),
            "message": "Habit template created. Instances will be created on-demand."
        }

    # Check if this is a Routine event (has repeat_pattern)
    elif event_data.get("repeat_pattern") is not None:
        repeat_pattern = event_data["repeat_pattern"]

        # Create template event ONLY (no instances generated upfront)
        event_data["is_template"] = True
        event_data["parent_event_id"] = None
        template = await db_service.create_event(event_data)

        print(f"✅ Created routine template: {template['id']} with repeat_pattern: {repeat_pattern}")

        return {
            "type": "routine",
            "template": EventResponse(**template),
            "message": "Routine template created. Instances will be created on-demand."
        }

    # Regular event
    else:
        result = await db_service.create_event(event_data)
        return {
            "type": "event",
            "event": EventResponse(**result)
        }


@router.put("/events/{event_id}", response_model=dict)
async def update_event(
    event_id: str,
    event: EventUpdate,
    user_id: str = Depends(get_current_user)
):
    """
    Update an existing event

    Supports:
    - Regular events: Direct update
    - Routine templates: Update template and regenerate instances if repeat_pattern changes
    - Habit instances: Update single instance only
    """
    # Check if event exists
    existing = await db_service.get_event(event_id=event_id, user_id=user_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Event not found")

    # Build update data with only non-None values
    update_data = event.model_dump(exclude_unset=True)
    
    # Debug: Log what fields are being updated
    print(f"📝 UPDATE_EVENT: event_id={event_id}")
    print(f"📝 UPDATE_EVENT: update_data keys: {list(update_data.keys())}")
    print(f"📝 UPDATE_EVENT: event_date={update_data.get('event_date')}, project_id={update_data.get('project_id')}")

    if not update_data:
        raise HTTPException(status_code=400, detail="No fields to update")

    # Check if this is a Routine template update
    if existing.get("is_template") and "repeat_pattern" in update_data:
        # Update the template only - using lazy instance creation
        # Instances will be created on-demand when user interacts with them
        result = await db_service.update_event(
            event_id=event_id,
            user_id=user_id,
            update_data=update_data
        )

        # Delete old PENDING instances only (keep completed/cancelled ones)
        # This ensures future virtual instances will use the updated template
        old_instances = await db_service.get_events(
            user_id=user_id,
            limit=1000
        )
        for inst in old_instances:
            if inst.get("parent_event_id") == event_id and inst.get("status") == "PENDING":
                await db_service.delete_event(inst["id"], user_id)

        # Return updated template without generating new instances (lazy creation)
        return {
            "type": "routine",
            "template": EventResponse(**result),
            "instances": [],  # No instances generated - will be created lazily
            "message": "Routine template updated. Instances will be created on-demand."
        }

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

    return {
        "type": "event",
        "event": EventResponse(**result)
    }


@router.delete("/events/{event_id}", status_code=200)
async def delete_event(
    event_id: str,
    delete_series: bool = Query(False, description="Delete entire series (for Routine/Habit)"),
    user_id: str = Depends(get_current_user)
):
    """
    Delete an event

    For Routine/Habit events:
    - delete_series=False (default): Delete only this instance
    - delete_series=True: Delete entire series (template + all instances)

    Returns deletion result on success.
    """
    # Check if event exists
    existing = await db_service.get_event(event_id=event_id, user_id=user_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Event not found")

    # Handle series deletion for Routine instances
    if delete_series and existing.get("parent_event_id"):
        # Delete all instances with same parent_event_id
        all_events = await db_service.get_events(user_id=user_id, limit=1000)
        parent_id = existing["parent_event_id"]

        # Delete the template
        await db_service.delete_event(parent_id, user_id)

        # Delete all instances
        deleted_count = 0
        for event in all_events:
            if event.get("parent_event_id") == parent_id:
                await db_service.delete_event(event["id"], user_id)
                deleted_count += 1

        return {"deleted": "series", "count": deleted_count + 1}

    # Handle series deletion for Habit instances
    elif delete_series and existing.get("routine_batch_id"):
        # Cancel all pending instances in the batch
        batch_id = existing["routine_batch_id"]
        cancelled_count = await db_service.cancel_habit_instances(batch_id, user_id)

        return {"deleted": "batch", "count": cancelled_count}

    # Default: Delete single event
    else:
        success = await db_service.delete_event(event_id=event_id, user_id=user_id)

        if not success:
            raise HTTPException(status_code=404, detail="Failed to delete event")

        return {"deleted": "single", "id": event_id}


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


@router.post("/events/{event_id}/uncomplete", response_model=EventResponse)
async def uncomplete_event(
    event_id: str,
    user_id: str = Depends(get_current_user)
):
    """Mark a completed event as pending (undo complete)"""
    # Check if event exists
    existing = await db_service.get_event(event_id=event_id, user_id=user_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Event not found")

    result = await db_service.update_event(
        event_id=event_id,
        user_id=user_id,
        update_data={
            "status": EventStatus.PENDING.value,
            "completed_at": None
        }
    )

    if not result:
        raise HTTPException(status_code=404, detail="Failed to uncomplete event")

    return EventResponse(**result)

@router.post("/events/{event_id}/instances", response_model=EventResponse, status_code=201)
async def create_event_instance(
    event_id: str,
    request: CreateInstanceRequest,
    user_id: str = Depends(get_current_user)
):
    """
    Create an instance for a specific date from a recurring event template.

    This endpoint is called when:
    - User marks a virtual instance as complete
    - User edits a virtual instance

    Flow:
    1. Verify the template exists and is_template=True
    2. Check if an instance already exists for this date
    3. If exists, return it
    4. If not, create a new instance with:
       - All fields from template
       - parent_event_id = template.id
       - event_date = target_date
       - Calculated start_time/end_time from repeat_pattern

    Args:
        event_id: Template event ID
        request: {"target_date": "YYYY-MM-DD"}

    Returns:
        The created or existing event instance
    """
    from datetime import date, datetime, timedelta

    # Verify the template exists
    template = await db_service.get_event(event_id=event_id, user_id=user_id)
    if not template:
        raise HTTPException(status_code=404, detail="Template event not found")

    if not template.get("is_template"):
        raise HTTPException(
            status_code=400,
            detail="Event is not a template. Use this endpoint on template events only."
        )

    # Parse target_date
    try:
        target_date = datetime.strptime(request.target_date, "%Y-%m-%d").date()
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD")

    # Check if an instance already exists for this date
    existing_instance = await db_service.get_event_instance(
        parent_id=event_id,
        event_date=target_date
    )

    if existing_instance:
        print(f"✅ Instance already exists for {request.target_date}, returning existing")
        return EventResponse(**existing_instance)

    # Calculate start_time and end_time from repeat_pattern
    repeat_pattern = template.get("repeat_pattern")
    calculated_start_time = None
    calculated_end_time = None

    if repeat_pattern:
        # Extract time from pattern if available
        if repeat_pattern.get("time"):
            time_str = repeat_pattern["time"]
            hour, minute = map(int, time_str.split(":"))
            calculated_start_time = datetime.combine(target_date, datetime.min.time().replace(hour=hour, minute=minute))

        # Calculate end_time using duration if available
        duration = template.get("duration")
        if calculated_start_time and duration:
            calculated_end_time = calculated_start_time + timedelta(minutes=duration)
        elif calculated_start_time:
            # Default 1 hour duration if not specified
            calculated_end_time = calculated_start_time + timedelta(hours=1)
    else:
        # Use template's start_time as reference
        template_start = template.get("start_time")
        if template_start:
            if isinstance(template_start, str):
                template_start = datetime.fromisoformat(template_start.replace('Z', '+00:00'))
            # Use the time from template, but with target date
            calculated_start_time = datetime.combine(
                target_date,
                template_start.time()
            )
            template_end = template.get("end_time")
            if template_end:
                if isinstance(template_end, str):
                    template_end = datetime.fromisoformat(template_end.replace('Z', '+00:00'))
                calculated_end_time = datetime.combine(
                    target_date,
                    template_end.time()
                )

    # Create instance data
    instance_data = {
        "user_id": user_id,
        "title": template.get("title"),
        "description": template.get("description"),
        "notes": template.get("notes"),
        "event_date": datetime.combine(target_date, datetime.min.time()),
        "time_period": template.get("time_period"),
        "start_time": calculated_start_time,
        "end_time": calculated_end_time,
        "duration": template.get("duration"),
        "event_type": template.get("event_type"),
        "category": template.get("category"),
        "tags": template.get("tags", []),
        "location": template.get("location"),
        "participants": template.get("participants", []),
        "urgency": template.get("urgency", 3),
        "importance": template.get("importance", 3),
        "is_deep_work": template.get("is_deep_work", False),
        "energy_required": template.get("energy_required"),
        "repeat_pattern": None,  # Instances don't have repeat_pattern
        "is_template": False,  # This is an instance, not template
        "parent_event_id": event_id,  # Link to template
        "habit_interval": None,
        "habit_completed_count": template.get("habit_completed_count"),
        "habit_total_count": template.get("habit_total_count"),
        "is_physically_demanding": template.get("is_physically_demanding", False),
        "is_mentally_demanding": template.get("is_mentally_demanding", False),
        "energy_consumption": template.get("energy_consumption"),
        "project_id": template.get("project_id"),  # Inherit project from template
        "status": EventStatus.PENDING.value,
        "created_by": "system",
        "ai_confidence": 1.0
    }

    # Create the instance
    result = await db_service.create_event(instance_data)

    print(f"✅ Created instance for {request.target_date} from template {event_id}")

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
