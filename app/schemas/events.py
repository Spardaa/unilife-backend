"""
Event Schemas - Request and Response models for events API
"""
from typing import List, Optional, Dict, Any
from datetime import datetime
from pydantic import BaseModel, Field
from enum import Enum


class TimePeriod(str, Enum):
    """Time period for events without specific start time"""
    ANYTIME = "ANYTIME"
    MORNING = "MORNING"
    AFTERNOON = "AFTERNOON"
    NIGHT = "NIGHT"


class EnergyLevel(str, Enum):
    """Energy level required for tasks - DEPRECATED, use energy_consumption instead"""
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


class EventType(str, Enum):
    """Types of events"""
    SCHEDULE = "schedule"      # Fixed schedule
    DEADLINE = "deadline"      # Deadline task
    FLOATING = "floating"      # Floating task (no time constraint)
    HABIT = "habit"            # Habit/recurring task
    REMINDER = "reminder"      # Reminder event


class Category(str, Enum):
    """Event categories"""
    STUDY = "STUDY"
    WORK = "WORK"
    SOCIAL = "SOCIAL"
    LIFE = "LIFE"
    HEALTH = "HEALTH"


class EventStatus(str, Enum):
    """Event status"""
    PENDING = "PENDING"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"


class EnergyDimension(BaseModel):
    """Single dimension of energy consumption (0-100)"""
    level: str = Field(..., description="Energy level: low, medium, high")
    score: int = Field(..., ge=0, le=100, description="Energy score 0-100 (60 = 30min high intensity)")
    description: str = Field(..., description="Natural language description")
    factors: List[str] = Field(default_factory=list, description="Specific factors")


class EnergyConsumption(BaseModel):
    """Energy consumption evaluation"""
    physical: EnergyDimension = Field(..., description="Physical energy consumption")
    mental: EnergyDimension = Field(..., description="Mental energy consumption")
    evaluated_at: datetime = Field(default_factory=datetime.utcnow, description="Evaluation timestamp")
    evaluated_by: str = Field(default="ai_agent", description="Evaluator")


class RepeatPattern(BaseModel):
    """Repeat pattern for recurring events"""
    type: str = Field(..., description="daily/weekly/monthly/custom")
    weekdays: Optional[List[int]] = Field(None, description="Days of week (0=Sunday, 6=Saturday) for custom")
    time: Optional[str] = Field(None, description="Time in HH:MM format (optional)")
    end_date: Optional[str] = Field(None, description="End date YYYY-MM-DD (optional)")


class EventBase(BaseModel):
    """Base event model"""
    title: str = Field(..., description="Event title")
    description: Optional[str] = Field(None, description="Event description")
    notes: Optional[str] = Field(None, description="Additional notes")

    # Time information - event_date is the date the event belongs to
    # For floating events: use event_date + time_period
    # For scheduled events: use start_time (and optionally set event_date separately)
    event_date: Optional[datetime] = Field(None, description="Event's assigned date (independent of start_time)")
    time_period: Optional[TimePeriod] = Field(None, description="Time period (ANYTIME/MORNING/AFTERNOON/NIGHT)")
    start_time: Optional[datetime] = Field(None, description="Specific start time (e.g., 10:30 AM)")
    end_time: Optional[datetime] = Field(None, description="End time or deadline")
    duration: Optional[int] = Field(None, description="Estimated duration in minutes")

    # Scheduling
    energy_required: Optional[EnergyLevel] = Field(None, deprecated="Use energy_consumption instead")
    urgency: int = Field(default=3, ge=1, le=5, description="Urgency level 1-5")
    importance: int = Field(default=3, ge=1, le=5, description="Importance level 1-5")
    is_deep_work: bool = Field(default=False, description="Whether this is deep work")

    # Classification
    event_type: EventType = Field(default=EventType.FLOATING, description="Event type")
    category: Category = Field(default=Category.WORK, description="Event category")
    tags: List[str] = Field(default_factory=list, description="Custom tags")

    # Location and participants
    location: Optional[str] = Field(None, description="Event location")
    participants: List[str] = Field(default_factory=list, description="Participant list")

    # Repeat pattern
    repeat_pattern: Optional[RepeatPattern] = Field(None, description="Repeat pattern for recurring events")
    routine_batch_id: Optional[str] = Field(None, description="Batch ID for AI-created recurring instances")

    # Routine/Habit fields
    is_template: Optional[bool] = Field(None, description="True = Routine template (not displayed in calendar)")
    habit_interval: Optional[int] = Field(None, description="Habit interval in days (1=daily, 2=every 2 days, etc.)")
    parent_event_id: Optional[str] = Field(None, description="Parent event ID (for Routine instances)")

    # Energy consumption (new system)
    energy_consumption: Optional[EnergyConsumption] = Field(None, description="Physical/mental energy consumption (0-100 each)")

    # User-set effort indicators
    is_physically_demanding: bool = Field(default=False, description="User-set physical effort indicator")
    is_mentally_demanding: bool = Field(default=False, description="User-set mental effort indicator")


class EventCreate(EventBase):
    """Create event model"""
    pass


class CreateInstanceRequest(BaseModel):
    """Request to create an instance from a template"""
    target_date: str = Field(..., description="Target date in YYYY-MM-DD format")


class EventUpdate(BaseModel):
    """Update event model - all fields optional"""
    title: Optional[str] = None
    description: Optional[str] = None
    notes: Optional[str] = None

    # Time information fields (matching EventBase)
    event_date: Optional[datetime] = None
    time_period: Optional[TimePeriod] = None
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    duration: Optional[int] = None
    energy_required: Optional[EnergyLevel] = None
    urgency: Optional[int] = None
    importance: Optional[int] = None
    is_deep_work: Optional[bool] = None
    event_type: Optional[EventType] = None
    category: Optional[Category] = None
    tags: Optional[List[str]] = None
    location: Optional[str] = None
    participants: Optional[List[str]] = None
    status: Optional[EventStatus] = None

    # Status timestamp fields
    completed_at: Optional[datetime] = None
    started_at: Optional[datetime] = None

    repeat_pattern: Optional[RepeatPattern] = None
    energy_consumption: Optional[EnergyConsumption] = None
    is_physically_demanding: Optional[bool] = None
    is_mentally_demanding: Optional[bool] = None
    is_template: Optional[bool] = None
    habit_interval: Optional[int] = None
    parent_event_id: Optional[str] = None
    routine_batch_id: Optional[str] = None

    class Config:
        extra = "ignore"  # Ignore extra fields from iOS (id, user_id, created_at, updated_at)


class EventResponse(EventBase):
    """Event response model"""
    id: str = Field(..., description="Event ID")
    user_id: str = Field(..., description="User ID")
    status: EventStatus = Field(..., description="Event status")
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")
    completed_at: Optional[datetime] = Field(None, description="Completion timestamp")
    started_at: Optional[datetime] = Field(None, description="Start timestamp")
    created_by: str = Field(..., description="Created by: 'user' or 'agent'")
    ai_confidence: float = Field(..., ge=0, le=1, description="AI confidence score")
    ai_reasoning: Optional[str] = Field(None, description="AI decision reasoning")
    is_physically_demanding: bool = Field(default=False, description="User-set physical effort indicator")
    is_mentally_demanding: bool = Field(default=False, description="User-set mental effort indicator")
    is_template: Optional[bool] = Field(None, description="Routine template marker")
    parent_event_id: Optional[str] = Field(None, description="Parent event ID (for Routine instances)")
    habit_completed_count: Optional[int] = Field(None, description="Number of completed habit instances")
    habit_total_count: int = Field(default=21, description="Total habit instances (default 21)")

    class Config:
        from_attributes = True


class EventsResponse(BaseModel):
    """Response for events query with both instances and templates"""
    instances: List[EventResponse] = Field(..., description="Real event instances (created/interacted with)")
    templates: List[EventResponse] = Field(..., description="Template events for virtual expansion")
