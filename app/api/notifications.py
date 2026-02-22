"""
Notifications API - Push notification management

Endpoints for:
- Sending notifications
- Managing notification templates
- Viewing notification history
"""
from typing import List, Optional
from datetime import datetime
from fastapi import APIRouter, HTTPException, Query, Depends, Body

from app.models.notification import (
    NotificationRecord,
    NotificationPayload,
    NotificationType,
    NotificationPlatform,
    NotificationPriority,
    NotificationTemplate
)
from app.services.notification_service import notification_service
from app.middleware.auth import get_current_user

router = APIRouter()


# ==================== Send Notifications ====================

@router.post("/notifications/send", response_model=NotificationRecord)
async def send_notification(
    payload: NotificationPayload,
    user_id: str = Depends(get_current_user),
    notification_type: NotificationType = NotificationType.CUSTOM,
    device_id: Optional[str] = Query(None, description="Target specific device"),
    platform: Optional[NotificationPlatform] = Query(None, description="Target platform"),
    priority: NotificationPriority = NotificationPriority.NORMAL,
    scheduled_for: Optional[datetime] = Query(None, description="Schedule for later (ISO 8601)")
):
    """
    Send a push notification

    Sends a notification to the user's registered devices.

    **Examples:**

    Send immediate notification:
    ```json
    {
        "title": "会议提醒",
        "body": "团队周会在15分钟后开始",
        "badge": 1,
        "sound": "default",
        "data": {"event_id": "uuid"}
    }
    ```

    Send scheduled notification:
    ```
    POST /api/v1/notifications/send?scheduled_for=2026-01-24T14:45:00Z
    ```

    **iOS Integration:**
    1. Register device token via POST /api/v1/devices
    2. Handle incoming notifications in AppDelegate
    3. Use NotificationCategory for actionable buttons
    """
    return await notification_service.send_notification(
        user_id=user_id,
        payload=payload,
        notification_type=notification_type,
        device_id=device_id,
        platform=platform,
        priority=priority,
        scheduled_for=scheduled_for
    )


@router.post("/notifications/send/template/{template_name}", response_model=NotificationRecord)
async def send_template_notification(
    template_name: str,
    user_id: str = Depends(get_current_user),
    variables: dict = Body({}, description="Template variables")
):
    """
    Send a notification using a predefined template

    **Available Templates:**

    - `event_reminder`: Event reminder (variables: title, minutes)
    - `event_starting`: Event starting now (variables: title)
    - `event_modified`: Event was modified (variables: title, new_time)
    - `routine_reminder`: Routine reminder (variables: routine_name)
    - `daily_summary`: Daily schedule summary (variables: event_count)
    - `energy_alert`: Low energy warning (no variables)

    **Example:**

    Send event reminder:
    ```json
    {
        "title": "团队周会",
        "minutes": "15"
    }
    ```
    """
    return await notification_service.send_template(
        template_name=template_name,
        user_id=user_id,
        **variables
    )


# ==================== Event-specific Notifications ====================

@router.post("/notifications/events/{event_id}/remind")
async def send_event_reminder(
    event_id: str,
    minutes_before: int = Query(..., ge=0, description="Minutes before event to remind"),
    user_id: str = Depends(get_current_user)
):
    """
    Send a reminder notification for an event

    Schedules a reminder notification to be sent before the event starts.

    **Example:**
    ```
    POST /api/v1/notifications/events/abc-123/remind?minutes_before=15
    ```

    This will send a notification 15 minutes before the event starts.
    """
    from app.services.db import db_service

    # Get event details
    event = await db_service.get_event(event_id=event_id, user_id=user_id)
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")

    start_time = event.get("start_time")
    if not start_time:
        raise HTTPException(status_code=400, detail="Event has no start time")

    # Calculate reminder time
    if isinstance(start_time, str):
        from datetime import datetime
        start_time = datetime.fromisoformat(start_time.replace('Z', '+00:00'))

    reminder_time = datetime.fromtimestamp(start_time.timestamp() - (minutes_before * 60))

    # Send scheduled notification
    return await notification_service.send_template(
        template_name="event_reminder",
        user_id=user_id,
        title=event.get("title", "日程"),
        minutes=str(minutes_before)
    )


@router.post("/notifications/events/{event_id}/starting")
async def send_event_starting(
    event_id: str,
    user_id: str = Depends(get_current_user)
):
    """
    Send a notification that an event is starting now

    Use this to notify the user that an event is starting immediately.

    **Example:**
    ```
    POST /api/v1/notifications/events/abc-123/starting
    ```
    """
    from app.services.db import db_service

    event = await db_service.get_event(event_id=event_id, user_id=user_id)
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")

    return await notification_service.send_template(
        template_name="event_starting",
        user_id=user_id,
        title=event.get("title", "日程")
    )


# ==================== Template Management ====================

@router.get("/notifications/templates", response_model=List[dict])
async def list_templates():
    """
    List all available notification templates

    Returns both built-in and custom templates with their variable requirements.
    """
    templates = notification_service.templates.values()
    return [
        {
            "name": t.name,
            "type": t.type.value,
            "title_template": t.template_title,
            "body_template": t.template_body,
            "variables": t.variables,
            "default_priority": t.default_priority.value
        }
        for t in templates
    ]


@router.post("/notifications/templates", response_model=dict)
async def create_template(
    template: NotificationTemplate,
    user_id: str = Depends(get_current_user)
):
    """
    Register a custom notification template

    Create a reusable notification template with variable substitution.

    **Example:**
    ```json
    {
        "name": "meeting_custom",
        "type": "event_reminder",
        "template_title": "{title}",
        "template_body": "将在{location}的{room}开始",
        "variables": ["title", "location", "room"],
        "default_priority": "high"
    }
    ```
    """
    notification_service.register_template(template)
    return {
        "name": template.name,
        "message": "Template registered successfully"
    }


# ==================== Notification History ====================

@router.get("/notifications/history", response_model=List[NotificationRecord])
async def get_notification_history(
    user_id: str = Depends(get_current_user),
    limit: int = Query(50, ge=1, le=200, description="Number of records to return")
):
    """
    Get notification history for the current user

    Returns past notifications with their delivery status.
    """
    return notification_service.get_notification_history(user_id=user_id, limit=limit)


# ==================== Test Endpoint ====================

@router.post("/notifications/test")
async def test_notification(
    user_id: str = Depends(get_current_user)
):
    """
    Send a test push notification AND inject into chat.
    
    Bypasses all LLM generation and notification type logic.
    Directly tests the push + chat injection pipeline.
    """
    from app.agents.notification_agent import notification_agent
    from app.models.notification import NotificationType, NotificationPriority
    
    import pytz
    from datetime import datetime
    user_tz = pytz.timezone("Asia/Shanghai")
    now_str = datetime.now(user_tz).strftime("%H:%M")
    
    body = f"🔔 这是一条测试推送（{now_str}）。如果你在聊天中也看到了这条消息，说明推送和聊天注入都正常工作！"
    
    await notification_agent._send_and_inject(
        user_id=user_id,
        title="UniLife 测试",
        body=body,
        notification_type=NotificationType.CUSTOM,
        category="TEST_NOTIFICATION",
        data={
            "type": "test",
            "source": "debug",
            "action": "open_chat"
        }
    )
    
    return {
        "triggered": True,
        "message": "推送已发送，请检查通知和聊天记录"
    }


# ==================== Debug Endpoints ====================

@router.post("/notifications/debug/trigger/{type}")
async def trigger_daily_notification(
    type: str,
    user_id: str = Depends(get_current_user),
    force: bool = Query(True, description="Force send, bypass time/condition checks")
):
    """
    Trigger a specific daily notification for debugging (Morning, Afternoon, Evening, Closing)
    
    Valid types:
    - morning_briefing
    - afternoon_checkin
    - evening_switch
    - closing_ritual
    
    Set force=true to bypass awake-window and event-empty checks.
    """
    from app.scheduler.daily_notifications import daily_notification_scheduler
    
    result = False
    
    if type == "morning_briefing":
        result = await daily_notification_scheduler.send_morning_briefing(user_id, force=force)
    elif type == "afternoon_checkin":
        result = await daily_notification_scheduler.send_afternoon_checkin(user_id, force=force)
    elif type == "evening_switch":
        result = await daily_notification_scheduler.send_evening_switch(user_id, force=force)
    elif type == "closing_ritual":
        result = await daily_notification_scheduler.send_closing_ritual(user_id, force=force)
    else:
        raise HTTPException(status_code=400, detail="Invalid notification type")
        
    return {
        "type": type,
        "triggered": result,
        "message": "Notification triggered successfully" if result else "Conditions not met or disabled"
    }


@router.post("/notifications/debug/last_device")
async def trigger_test_to_last_device():
    """
    Debug: Send test notification to the most recently active device (ignores auth)
    
    Useful for testing when you don't know the exact user ID of the device.
    """
    from app.api.devices import device_service
    from sqlalchemy import text
    
    # Direct DB query to find latest device
    db = device_service.get_session()
    try:
        # Get latest device
        row = db.execute(text(
            "SELECT user_id, token, platform FROM devices ORDER BY updated_at DESC LIMIT 1"
        )).fetchone()
        
        if not row:
            raise HTTPException(status_code=404, detail="No devices found in database")
            
        user_id = row[0]
        token = row[1]
        platform_str = row[2]
        
        print(f"[Debug] Found latest device for user {user_id}, token={token[:10]}...")
        
        # Send test notification
        payload = NotificationPayload(
            title="Debug Test",
            body=f"This is a debug message for user {user_id}",
            sound="default"
        )
        
        # Manually construct record and send
        # We use standard send_notification but specify user_id
        return await notification_service.send_notification(
            user_id=user_id,
            payload=payload,
            notification_type=NotificationType.CUSTOM
        )
        
    finally:
        db.close()


@router.post("/notifications/debug/schedule-last-device")
async def schedule_test_last_device(minutes: int = 1):
    """
    Debug: Schedule a test notification for the most recently active device (ignores auth)
    
    Verifies the background poller.
    """
    from app.api.devices import device_service
    from sqlalchemy import text
    from datetime import datetime, timedelta
    
    db = device_service.get_session()
    try:
        row = db.execute(text(
            "SELECT user_id FROM devices ORDER BY updated_at DESC LIMIT 1"
        )).fetchone()
        
        if not row:
            raise HTTPException(status_code=404, detail="No devices found")
            
        user_id = row[0]
        scheduled_for = datetime.utcnow() + timedelta(minutes=minutes)
        
        print(f"[Debug] Scheduling test for {user_id} at {scheduled_for} (in {minutes} min)")
        
        payload = NotificationPayload(
            title="Scheduled Test", 
            body=f"This notification was scheduled {minutes} min ago.",
            sound="default"
        )
        
        return await notification_service.send_notification(
            user_id=user_id,
            payload=payload,
            notification_type=NotificationType.CUSTOM,
            scheduled_for=scheduled_for
        )
    finally:
        db.close()


@router.post("/notifications/debug/trigger-last-device/{type}")
async def trigger_daily_notification_last_device(type: str):
    """
    Debug: Trigger daily notification for the most recently active device (ignores auth)
    
    Valid types: morning_briefing, afternoon_checkin, evening_switch, closing_ritual
    """
    from app.api.devices import device_service
    from sqlalchemy import text
    from app.scheduler.daily_notifications import daily_notification_scheduler
    
    # Direct DB query to find latest device
    db = device_service.get_session()
    try:
        # Get latest device
        row = db.execute(text(
            "SELECT user_id FROM devices ORDER BY updated_at DESC LIMIT 1"
        )).fetchone()
        
        if not row:
            raise HTTPException(status_code=404, detail="No devices found in database")
            
        user_id = row[0]
        print(f"[Debug] Triggering {type} for user {user_id}...")
        
        result = False
        if type == "morning_briefing":
            result = await daily_notification_scheduler.send_morning_briefing(user_id, force=True)
        elif type == "afternoon_checkin":
            result = await daily_notification_scheduler.send_afternoon_checkin(user_id, force=True)
        elif type == "evening_switch":
            result = await daily_notification_scheduler.send_evening_switch(user_id, force=True)
        elif type == "closing_ritual":
            result = await daily_notification_scheduler.send_closing_ritual(user_id, force=True)
        else:
            raise HTTPException(status_code=400, detail="Invalid notification type")
            
        return {
            "type": type,
            "user_id": user_id,
            "triggered": result,
            "message": "Notification triggered successfully" if result else "Conditions not met or disabled (check server logs)"
        }
        
    finally:
        db.close()
