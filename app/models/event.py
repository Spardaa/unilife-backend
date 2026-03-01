"""
Event Model - Database model for schedule events
"""
from typing import List, Optional, Dict, Any
from datetime import datetime
from pydantic import BaseModel, Field
from enum import Enum
import uuid


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


# ==================== New Models for Enhanced Features ====================

class TimePeriod(str, Enum):
    """Time period for events without specific start time"""
    ANYTIME = "ANYTIME"
    MORNING = "MORNING"
    AFTERNOON = "AFTERNOON"
    NIGHT = "NIGHT"


class EnergyDimension(BaseModel):
    """Single dimension of energy consumption"""
    level: str = Field(..., description="Energy level: low, medium, high")
    score: int = Field(..., ge=0, le=100, description="Energy score 0-100 (60 = 30min high intensity task)")
    description: str = Field(..., description="Natural language description")
    factors: List[str] = Field(default_factory=list, description="Specific factors contributing to energy consumption")

    class Config:
        json_schema_extra = {
            "example": {
                "level": "high",
                "score": 75,
                "description": "需要连续站立3小时，涉及搬运物品 (30分钟高强度)",
                "factors": ["站立", "搬运", "移动"]
            }
        }


class EnergyConsumption(BaseModel):
    """Energy consumption evaluation for an event"""
    physical: EnergyDimension = Field(..., description="Physical energy consumption")
    mental: EnergyDimension = Field(..., description="Mental energy consumption")
    evaluated_at: datetime = Field(default_factory=datetime.utcnow, description="Evaluation timestamp")
    evaluated_by: str = Field(default="energy_evaluator_agent", description="Agent that performed evaluation")

    class Config:
        json_schema_extra = {
            "example": {
                "physical": {
                    "level": "high",
                    "score": 75,
                    "description": "需要上下楼梯搬运重物 (30分钟高强度)",
                    "factors": ["爬楼梯", "搬运重物"]
                },
                "mental": {
                    "level": "low",
                    "score": 30,
                    "description": "简单的体力劳动",
                    "factors": ["机械操作"]
                },
                "evaluated_at": "2026-01-21T10:00:00",
                "evaluated_by": "energy_evaluator_agent"
            }
        }


class RepeatPattern(BaseModel):
    """Repeat pattern for recurring events"""
    type: str = Field(..., description="daily/weekly/monthly/custom")
    weekdays: Optional[List[int]] = Field(None, description="Days of week (0=Sunday, 6=Saturday) for custom type")
    time: Optional[str] = Field(None, description="Time in HH:MM format (optional)")
    end_date: Optional[str] = Field(None, description="End date in YYYY-MM-DD format (optional)")

    class Config:
        json_schema_extra = {
            "example": {
                "type": "weekly",
                "weekdays": [1, 2, 3, 4, 5],
                "time": "18:00",
                "end_date": "2026-12-31"
            }
        }


class ExtractedPoint(BaseModel):
    """User profile point extracted from event"""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()), description="Point ID")
    type: str = Field(..., description="Point type: relationship, identity, preference, habit")
    content: str = Field(..., description="Extracted content")
    confidence: float = Field(..., ge=0, le=1, description="Confidence 0.0-1.0")
    evidence: List[str] = Field(default_factory=list, description="Evidence sources")
    created_at: datetime = Field(default_factory=datetime.utcnow, description="Creation timestamp")
    validated: bool = Field(default=False, description="Whether user has validated this")
    validation_count: int = Field(default=0, description="Number of validations (increases weight)")

    class Config:
        json_schema_extra = {
            "example": {
                "type": "relationship",
                "content": "用户可能正在约会或有恋人",
                "confidence": 0.75,
                "evidence": ["关键词'约会'", "周五晚上时段"],
                "validated": False,
                "validation_count": 0
            }
        }


# ==================== Event Model ====================

class Event(BaseModel):
    """Unified event model for all schedule types"""

    # Primary key
    id: str = Field(default_factory=lambda: str(uuid.uuid4()), description="Event UUID")

    # User reference
    user_id: str = Field(..., description="User ID")

    # Basic information
    title: str = Field(..., description="Event title")
    description: Optional[str] = Field(None, description="Detailed description")
    notes: Optional[str] = Field(None, description="Additional notes for the event")

    # Time information (all optional to support different event types)
    time_period: Optional[TimePeriod] = Field(None, description="Time period (ANYTIME/MORNING/AFTERNOON/NIGHT) - primary field for time-based events")
    start_time: Optional[datetime] = Field(None, description="Start time - optional, only set when user specifies exact time")
    end_time: Optional[datetime] = Field(None, description="End time or deadline")
    duration: Optional[int] = Field(None, description="Duration in minutes")

    # Scheduling attributes
    # energy_required: DEPRECATED - Use energy_consumption instead
    energy_required: Optional[EnergyLevel] = Field(None, deprecated="Use energy_consumption.physical/mental.score instead")
    urgency: int = Field(default=3, ge=1, le=5, description="Urgency level 1-5")
    importance: int = Field(default=3, ge=1, le=5, description="Importance level 1-5")
    is_deep_work: bool = Field(default=False, description="Whether this is deep work")

    # Classification
    event_type: EventType = Field(default=EventType.FLOATING, description="Event type")
    category: Category = Field(default=Category.WORK, description="Event category")
    tags: List[str] = Field(default_factory=list, description="Custom tags")

    # Repeat pattern
    repeat_pattern: Optional[RepeatPattern] = Field(None, description="Repeat pattern for recurring events")
    routine_batch_id: Optional[str] = Field(None, description="Batch ID for AI-created recurring event instances")

    # Routine/Habit fields
    is_template: Optional[bool] = Field(None, description="True = Routine template (not displayed in calendar)")
    habit_interval: Optional[int] = Field(None, description="Habit interval in days (1=daily, 2=every 2 days, etc.)")
    parent_event_id: Optional[str] = Field(None, description="Parent event ID (for Routine instances)")

    # Location and participants
    location: Optional[str] = Field(None, description="Event location")
    participants: List[str] = Field(default_factory=list, description="Participant list")

    # Status management
    status: EventStatus = Field(default=EventStatus.PENDING, description="Event status")

    # Completion tracking
    completed_at: Optional[datetime] = Field(None, description="When the event was marked as completed")
    started_at: Optional[datetime] = Field(None, description="When the event was started (for IN_PROGRESS tracking)")

    # Metadata
    created_at: datetime = Field(default_factory=datetime.utcnow, description="Creation timestamp")
    updated_at: datetime = Field(default_factory=datetime.utcnow, description="Last update timestamp")
    created_by: str = Field(default="user", description="Created by: 'user' or 'agent'")

    # AI reasoning fields
    ai_confidence: float = Field(default=0.5, ge=0, le=1, description="AI creation confidence")
    ai_reasoning: Optional[str] = Field(None, description="AI decision reasoning")

    # ==================== Enhanced Features Fields ====================
    # Energy consumption evaluation (体力 + 精神)
    energy_consumption: Optional[EnergyConsumption] = Field(None, description="Detailed energy consumption evaluation")

    # AI-generated description (separate from user-provided description)
    ai_description: Optional[str] = Field(None, description="AI-generated description explaining the event context and purpose")

    # Extracted user profile points
    extracted_points: List[ExtractedPoint] = Field(default_factory=list, description="User profile insights extracted from this event")

    # Project association (Life Project system)
    project_id: Optional[str] = Field(None, description="Associated project ID")

    class Config:
        json_schema_extra = {
            "example": {
                "id": "550e8400-e29b-41d4-a716-446655440000",
                "user_id": "user-123",
                "title": "团队周会",
                "description": "讨论本周项目进度",
                "notes": "带笔记本",
                "time_period": "AFTERNOON",
                "start_time": None,
                "end_time": None,
                "duration": 60,
                "urgency": 4,
                "importance": 4,
                "is_deep_work": False,
                "event_type": "schedule",
                "category": "WORK",
                "tags": ["weekly", "meeting"],
                "location": "会议室A",
                "participants": ["user-123", "user-456"],
                "status": "PENDING",
                "repeat_pattern": {
                    "type": "weekly",
                    "weekdays": [1, 2, 3, 4, 5],
                    "time": "14:00"
                },
                "created_at": "2026-01-20T10:00:00",
                "updated_at": "2026-01-20T10:00:00",
                "created_by": "user",
                "ai_confidence": 0.8,
                "ai_reasoning": "Scheduled based on user preference for Tuesday afternoons",
                "energy_consumption": {
                    "physical": {"level": "low", "score": 20, "description": "Sedentary meeting", "factors": ["sitting"]},
                    "mental": {"level": "high", "score": 70, "description": "Active discussion and planning", "factors": ["focus", "communication"]}
                }
            }
        }

    def to_dict(self) -> dict:
        """Convert model to dictionary for database storage"""
        return self.model_dump(mode='json')

    @classmethod
    def from_dict(cls, data: dict) -> "Event":
        """Create Event from dictionary (from database)"""
        return cls(**data)


# Helper functions for event classification
def is_schedule_event(event: Event) -> bool:
    """Check if event is a fixed schedule (has both start and end time)"""
    return event.start_time is not None and event.end_time is not None


def is_deadline_event(event: Event) -> bool:
    """Check if event is a deadline (has end time but no start time)"""
    return event.start_time is None and event.end_time is not None


def is_start_time_event(event: Event) -> bool:
    """Check if event has start time but no end time"""
    return event.start_time is not None and event.end_time is None


def is_floating_event(event: Event) -> bool:
    """Check if event is floating (no time constraints)"""
    return event.start_time is None and event.end_time is None
