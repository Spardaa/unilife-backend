"""
Notification Model - Push notification records
"""
from typing import List, Optional, Dict, Any, Literal
from datetime import datetime
from pydantic import BaseModel, Field
from enum import Enum
import uuid


class NotificationPlatform(str, Enum):
    """Supported push notification platforms"""
    APNS = "apns"       # Apple Push Notification Service (iOS)
    FCM = "fcm"         # Firebase Cloud Messaging (Android)
    WEB = "web"         # Web Push (Web Push API)
    UNKNOWN = "unknown" # Unknown or no specific platform


class NotificationType(str, Enum):
    """Types of notifications"""
    EVENT_REMINDER = "event_reminder"         # Event reminder before start
    EVENT_STARTING = "event_starting"         # Event is starting now
    EVENT_MODIFIED = "event_modified"         # Event was modified
    EVENT_DELETED = "event_deleted"           # Event was deleted
    ROUTINE_REMINDER = "routine_reminder"     # Routine/habit reminder
    SUGGESTION = "suggestion"                 # AI suggestion
    ENERGY_ALERT = "energy_alert"             # Low energy warning
    DAILY_SUMMARY = "daily_summary"           # Daily schedule summary
    GREETING = "greeting"                     # Morning/evening greeting
    PROACTIVE_CHECK = "proactive_check"       # AI autonomous proactive message
    CUSTOM = "custom"                         # Custom notification


class NotificationStatus(str, Enum):
    """Notification delivery status"""
    PENDING = "pending"
    SENT = "sent"
    FAILED = "failed"
    DELIVERED = "delivered"  # Confirmed delivery (platform-reported)


class NotificationPriority(str, Enum):
    """Notification priority levels"""
    LOW = "low"
    NORMAL = "normal"
    MEDIUM = "medium"
    HIGH = "high"


# ==================== Notification Models ====================

class NotificationPayload(BaseModel):
    """Push notification payload"""
    title: str = Field(..., description="Notification title (shown in bold)")
    body: str = Field(..., description="Notification body text")
    badge: Optional[int] = Field(None, description="Badge count to display on app icon")
    sound: Optional[str] = Field(default="default", description="Sound to play (default='default', 'none' for silent)")
    category: Optional[str] = Field(None, description="Notification category for actionable notifications")
    thread_id: Optional[str] = Field(None, description="Thread identifier for grouping notifications")
    mutable_content: bool = Field(default=True, description="Whether the notification can be modified by service extension")
    content_available: bool = Field(default=False, description="Whether to wake up app in background (silent notification)")

    # Custom data payload (sent to app but not displayed)
    data: Dict[str, Any] = Field(default_factory=dict, description="Custom data payload")

    class Config:
        json_schema_extra = {
            "example": {
                "title": "会议提醒",
                "body": "团队周会在15分钟后开始",
                "badge": 1,
                "sound": "default",
                "category": "EVENT_REMINDER",
                "data": {
                    "event_id": "uuid",
                    "action": "view_event"
                }
            }
        }


class NotificationRecord(BaseModel):
    """Notification record for tracking"""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    user_id: str = Field(..., description="User to receive notification")
    device_id: Optional[str] = Field(None, description="Target device (None for all user devices)")
    platform: NotificationPlatform = Field(..., description="Target platform")

    # Notification content
    type: NotificationType = Field(..., description="Notification type")
    priority: NotificationPriority = Field(default=NotificationPriority.NORMAL)
    payload: NotificationPayload = Field(..., description="Notification payload")

    # Delivery tracking
    status: NotificationStatus = Field(default=NotificationStatus.PENDING)
    scheduled_for: Optional[datetime] = Field(None, description="Scheduled send time (None=immediate)")
    sent_at: Optional[datetime] = Field(None, description="When notification was sent")
    delivered_at: Optional[datetime] = Field(None, description="When delivery was confirmed")
    error_message: Optional[str] = Field(None, description="Error if delivery failed")

    # Metadata
    created_at: datetime = Field(default_factory=datetime.utcnow)
    retry_count: int = Field(default=0, description="Number of retry attempts")

    class Config:
        json_schema_extra = {
            "example": {
                "id": "550e8400-e29b-41d4-a716-446655440000",
                "user_id": "user-123",
                "device_id": "device-uuid",
                "platform": "apns",
                "type": "event_reminder",
                "priority": "normal",
                "payload": {
                    "title": "会议提醒",
                    "body": "团队周会在15分钟后开始"
                },
                "status": "pending",
                "scheduled_for": "2026-01-24T14:45:00"
            }
        }


# ==================== Notification Templates ====================

class NotificationTemplate(BaseModel):
    """Reusable notification template"""
    name: str = Field(..., description="Template name")
    type: NotificationType = Field(..., description="Notification type")
    template_title: str = Field(..., description="Title template with {variables}")
    template_body: str = Field(..., description="Body template with {variables}")
    default_sound: str = Field(default="default")
    default_category: Optional[str] = Field(None)

    # Template configuration
    variables: List[str] = Field(default_factory=list, description="Variables used in template")
    default_priority: NotificationPriority = Field(default=NotificationPriority.NORMAL)

    class Config:
        json_schema_extra = {
            "example": {
                "name": "event_reminder_15min",
                "type": "event_reminder",
                "template_title": "{event_title}",
                "template_body": "将在{minutes}分钟后开始",
                "variables": ["event_title", "minutes"],
                "default_priority": "normal"
            }
        }

    def render(self, **kwargs) -> NotificationPayload:
        """Render template with provided variables"""
        title = self.template_title
        body = self.template_body

        for key, value in kwargs.items():
            placeholder = f"{{{key}}}"
            title = title.replace(placeholder, str(value))
            body = body.replace(placeholder, str(value))

        return NotificationPayload(
            title=title,
            body=body,
            sound=self.default_sound,
            category=self.default_category
        )


# ==================== Built-in Templates ====================

BUILTIN_TEMPLATES: Dict[str, NotificationTemplate] = {
    "event_reminder": NotificationTemplate(
        name="event_reminder",
        type=NotificationType.EVENT_REMINDER,
        template_title="{title}",
        template_body="将在{minutes}分钟后开始",
        variables=["title", "minutes"],
        default_category="EVENT_REMINDER"
    ),
    "event_starting": NotificationTemplate(
        name="event_starting",
        type=NotificationType.EVENT_STARTING,
        template_title="{title}",
        template_body="现在开始了",
        variables=["title"],
        default_category="EVENT_STARTING",
        default_priority=NotificationPriority.HIGH
    ),
    "event_modified": NotificationTemplate(
        name="event_modified",
        type=NotificationType.EVENT_MODIFIED,
        template_title="日程已修改",
        template_body="{title}已重新安排到{new_time}",
        variables=["title", "new_time"],
        default_category="EVENT_MODIFIED"
    ),
    "routine_reminder": NotificationTemplate(
        name="routine_reminder",
        type=NotificationType.ROUTINE_REMINDER,
        template_title="{routine_name}",
        template_body="今天的{routine_name}时间到了",
        variables=["routine_name"],
        default_category="ROUTINE_REMINDER"
    ),
    "daily_summary": NotificationTemplate(
        name="daily_summary_morning",
        type=NotificationType.DAILY_SUMMARY,
        template_title="早上好！",
        template_body="今天有{event_count}个日程安排",
        variables=["event_count"],
        default_category="DAILY_SUMMARY"
    ),
    "energy_alert": NotificationTemplate(
        name="energy_alert_low",
        type=NotificationType.ENERGY_ALERT,
        template_title="精力提醒",
        template_body="您当前精力较低，建议安排轻松任务",
        variables=[],
        default_category="ENERGY_ALERT",
        default_sound="default"
    ),
}
