"""
Event Schemas - Request and Response models for events API
"""
from typing import List, Optional
from datetime import datetime
from pydantic import BaseModel, Field
from enum import Enum


class EnergyLevel(str, Enum):
    """Energy level required for tasks"""
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


class EventBase(BaseModel):
    """Base event model"""
    title: str = Field(..., description="Event title")
    description: Optional[str] = Field(None, description="Event description")

    # Time information
    start_time: Optional[datetime] = Field(None, description="Start time")
    end_time: Optional[datetime] = Field(None, description="End time or deadline")
    duration: Optional[int] = Field(None, description="Estimated duration in minutes")

    # Scheduling
    energy_required: EnergyLevel = Field(default=EnergyLevel.MEDIUM, description="Required energy level")
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


class EventCreate(EventBase):
    """Create event model"""
    pass


class EventUpdate(BaseModel):
    """Update event model - all fields optional"""
    title: Optional[str] = None
    description: Optional[str] = None
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


class EventResponse(EventBase):
    """Event response model"""
    id: str = Field(..., description="Event ID")
    user_id: str = Field(..., description="User ID")
    status: EventStatus = Field(..., description="Event status")
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")
    created_by: str = Field(..., description="Created by: 'user' or 'agent'")
    ai_confidence: float = Field(..., ge=0, le=1, description="AI confidence score")
    ai_reasoning: Optional[str] = Field(None, description="AI decision reasoning")

    class Config:
        from_attributes = True
