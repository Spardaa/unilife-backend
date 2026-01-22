"""
Event Model - Database model for schedule events
"""
from typing import List, Optional, Dict, Any, Literal
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

class EnergyDimension(BaseModel):
    """Single dimension of energy consumption"""
    level: str = Field(..., description="Energy level: low, medium, high")
    score: int = Field(..., ge=0, le=10, description="Energy score 0-10")
    description: str = Field(..., description="Natural language description")
    factors: List[str] = Field(default_factory=list, description="Specific factors contributing to energy consumption")

    class Config:
        json_schema_extra = {
            "example": {
                "level": "high",
                "score": 8,
                "description": "需要连续站立3小时，涉及搬运物品",
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
                    "score": 8,
                    "description": "需要上下楼梯搬运重物",
                    "factors": ["爬楼梯", "搬运重物"]
                },
                "mental": {
                    "level": "low",
                    "score": 3,
                    "description": "简单的体力劳动",
                    "factors": ["机械操作"]
                },
                "evaluated_at": "2026-01-21T10:00:00",
                "evaluated_by": "energy_evaluator_agent"
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

    # Time information (all optional to support different event types)
    start_time: Optional[datetime] = Field(None, description="Start time")
    end_time: Optional[datetime] = Field(None, description="End time or deadline")
    duration: Optional[int] = Field(None, description="Duration in minutes")

    # ==================== Dual Time Architecture Fields ====================
    # Duration source tracking
    duration_source: Literal["user_exact", "ai_estimate", "default", "user_adjusted"] = Field(
        default="default",
        description="Source of duration: user_exact (explicit), ai_estimate (AI learned), default (fallback), user_adjusted (modified from AI)"
    )
    duration_confidence: float = Field(
        default=1.0,
        ge=0.0,
        le=1.0,
        description="Confidence of duration estimate (0.0-1.0). <0.7 shows 'AI estimate' label"
    )
    duration_actual: Optional[int] = Field(
        None,
        description="Actual duration after completion (minutes), recorded for AI learning"
    )
    ai_original_estimate: Optional[int] = Field(
        None,
        description="Original AI estimate before user adjustment (only set when duration_source='user_adjusted')"
    )

    # Display preference
    display_mode: Literal["flexible", "rigid"] = Field(
        default="flexible",
        description="Display mode: flexible (show as '10:00 Event (~1 hour)') or rigid (show as '10:00-11:00 Event')"
    )

    # Scheduling attributes
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

    # Status management
    status: EventStatus = Field(default=EventStatus.PENDING, description="Event status")

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

    class Config:
        json_schema_extra = {
            "example": {
                "id": "550e8400-e29b-41d4-a716-446655440000",
                "user_id": "user-123",
                "title": "团队周会",
                "description": "讨论本周项目进度",
                "start_time": "2026-01-21T14:00:00",
                "end_time": "2026-01-21T15:00:00",
                "duration": 60,
                "energy_required": "MEDIUM",
                "urgency": 4,
                "importance": 4,
                "is_deep_work": False,
                "event_type": "schedule",
                "category": "WORK",
                "tags": ["weekly", "meeting"],
                "location": "会议室A",
                "participants": ["user-123", "user-456"],
                "status": "PENDING",
                "created_at": "2026-01-20T10:00:00",
                "updated_at": "2026-01-20T10:00:00",
                "created_by": "user",
                "ai_confidence": 0.8,
                "ai_reasoning": "Scheduled based on user preference for Tuesday afternoons"
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
