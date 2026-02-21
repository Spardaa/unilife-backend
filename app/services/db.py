"""
Database Service - SQLite with SQLAlchemy
"""
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta, date, timezone
from sqlalchemy import create_engine, Column, String, Integer, DateTime, Boolean, JSON, Numeric, Float, func
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
import uuid
try:
    from zoneinfo import ZoneInfo
except ImportError:
    from backports.zoneinfo import ZoneInfo

from app.config import settings
from app.models.user import UserPreferences, EnergyProfile
from app.models.event import EventStatus, EventType, Category, EnergyLevel


# Create base class for models
Base = declarative_base()


# ============ Default Values ============

DEFAULT_ENERGY_PROFILE = {
    "hourly_baseline": {
        "6": 40, "7": 50, "8": 70, "9": 80, "10": 90, "11": 85,
        "12": 70, "13": 65, "14": 60, "15": 70, "16": 75, "17": 65,
        "18": 60, "19": 55, "20": 50, "21": 40, "22": 30, "23": 20
    },
    "task_energy_cost": {
        "deep_work": -20,
        "meeting": -10,
        "study": -15,
        "break": 15,
        "coffee": 10,
        "sleep": 100
    },
    "learned_adjustments": {}
}

DEFAULT_USER_PREFERENCES = {
    "notification_enabled": True,
    "auto_schedule_enabled": True,
    "energy_based_scheduling": True,
    "working_hours_start": 9,
    "working_hours_end": 18
}

DEFAULT_SOCIAL_PROFILE = {
    "contacts": {},
    "relationships": {},
    "intimacy_scores": {}
}


# ============ Database Models ============

class UserModel(Base):
    """User table model"""
    __tablename__ = "users"

    id = Column(String, primary_key=True)
    email = Column(String, nullable=True)
    phone = Column(String, nullable=True)
    user_id = Column(String, nullable=True, unique=True)
    nickname = Column(String, nullable=False)
    avatar_url = Column(String, nullable=True)
    timezone = Column(String, default="Asia/Shanghai")

    # Energy management
    energy_profile = Column(JSON, nullable=False, default=DEFAULT_ENERGY_PROFILE)
    current_energy = Column(Integer, default=100)

    # Preferences
    preferences = Column(JSON, nullable=False, default=DEFAULT_USER_PREFERENCES)

    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow)
    last_active_at = Column(DateTime, default=datetime.utcnow)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "id": self.id,
            "email": self.email,
            "phone": self.phone,
            "user_id": self.user_id,
            "nickname": self.nickname,
            "avatar_url": self.avatar_url,
            "timezone": self.timezone,
            "energy_profile": self.energy_profile,
            "current_energy": self.current_energy,
            "preferences": self.preferences,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "last_active_at": self.last_active_at.isoformat() if self.last_active_at else None,
        }


class EventModel(Base):
    """Event table model"""
    __tablename__ = "events"

    id = Column(String, primary_key=True)
    user_id = Column(String, nullable=False)

    # Basic information
    title = Column(String, nullable=False)
    description = Column(String, nullable=True)
    notes = Column(String, nullable=True)  # Additional notes for the event

    # Time information - time_period is primary, start_time is optional
    # event_date: the date this event belongs to (independent of start_time)
    # - For floating events: set to user-selected date
    # - For scheduled events: can be derived from start_time, but can also be set separately
    event_date = Column(DateTime, nullable=True)  # Event's assigned date
    time_period = Column(String, nullable=True)  # ANYTIME/MORNING/AFTERNOON/NIGHT
    start_time = Column(DateTime, nullable=True)  # Specific time (if user sets exact time)
    end_time = Column(DateTime, nullable=True)
    duration = Column(Integer, nullable=True)

    # Scheduling attributes
    energy_required = Column(String, nullable=False, default=EnergyLevel.MEDIUM.value)
    urgency = Column(Integer, default=3)
    importance = Column(Integer, default=3)
    is_deep_work = Column(Boolean, default=False)

    # Classification
    event_type = Column(String, nullable=False, default=EventType.FLOATING.value)
    category = Column(String, nullable=False, default=Category.WORK.value)
    tags = Column(JSON, nullable=False, default=list)

    # Location and participants
    location = Column(String, nullable=True)
    participants = Column(JSON, nullable=False, default=list)

    # Status management
    status = Column(String, nullable=False, default=EventStatus.PENDING.value)

    # Completion tracking
    completed_at = Column(DateTime, nullable=True)
    started_at = Column(DateTime, nullable=True)

    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow)
    created_by = Column(String, default="user")

    # AI reasoning fields
    ai_confidence = Column(Numeric(3, 2), default=0.5)
    ai_reasoning = Column(String, nullable=True)

    # Routine/Habit specific fields (for long-term recurring events)
    repeat_rule = Column(JSON, nullable=True)  # DEPRECATED - Use repeat_pattern instead
    repeat_pattern = Column(JSON, nullable=True)  # {"type": "weekly", "weekdays": [1,2,3,4,5], "time": "18:00", "end_date": "2026-06-30"}
    routine_batch_id = Column(String, nullable=True)  # Batch ID for AI-created recurring event instances
    is_flexible = Column(Boolean, default=False)  # Whether time is flexible (decide each day)
    preferred_time_slots = Column(JSON, nullable=True)  # Preferred time slots: [{"start": "18:00", "end": "20:00", "priority": 1}]
    makeup_strategy = Column(String, nullable=True)  # Strategy when missed: "ask_user", "auto_next_day", "auto_same_day_next_week"
    parent_routine_id = Column(String, nullable=True)  # For routine instances: which routine they belong to
    routine_completed_dates = Column(JSON, nullable=True)  # Track which dates the routine was completed: ["2026-01-20", "2026-01-21"]
    
    # Habit counting (Phased System)
    habit_completed_count = Column(Integer, default=0)
    habit_total_count = Column(Integer, default=21)

    # Energy consumption (new system)
    energy_consumption = Column(JSON, nullable=True)  # {"physical": {...}, "mental": {...}, "evaluated_at": "...", "evaluated_by": "..."}

    # User-set effort indicators (for user input)
    is_physically_demanding = Column(Boolean, default=False)  # User-set indicator
    is_mentally_demanding = Column(Boolean, default=False)  # User-set indicator

    # Routine template marker
    is_template = Column(Boolean, default=False)  # True = Routine template (not displayed in calendar)

    # Project association (Life Project system)
    project_id = Column(String, nullable=True)  # FK to projects table
    anchor_time = Column(DateTime, nullable=True)  # Hard deadline time
    energy_cost = Column(String, nullable=True)  # HIGH/NORMAL/LOW for AI scheduling

    def to_dict(self, tz=None) -> Dict[str, Any]:
        """Convert to dictionary with optional timezone conversion"""
        def convert_dt(dt):
            if dt is None:
                return None
            if tz:
                # If naive, assume it's ALREADY in user's local timezone
                # (not UTC - this matches how data is stored via parse_time_with_timezone)
                if dt.tzinfo is None:
                    import pytz
                    local_tz = pytz.timezone("Asia/Shanghai")
                    dt = local_tz.localize(dt)
                return dt.astimezone(tz).isoformat()
            return dt.isoformat()

        return {
            "id": self.id,
            "user_id": self.user_id,
            "title": self.title,
            "description": self.description,
            "notes": self.notes,
            "event_date": convert_dt(self.event_date),
            "time_period": self.time_period,
            "start_time": convert_dt(self.start_time),
            "end_time": convert_dt(self.end_time),
            "duration": self.duration,
            "energy_required": self.energy_required,  # DEPRECATED
            "urgency": self.urgency,
            "importance": self.importance,
            "is_deep_work": self.is_deep_work,
            "event_type": self.event_type,
            "category": self.category,
            "tags": self.tags or [],
            "location": self.location,
            "participants": self.participants or [],
            "status": self.status,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "created_by": self.created_by,
            "ai_confidence": float(self.ai_confidence) if self.ai_confidence else 0.5,
            "ai_reasoning": self.ai_reasoning,
            # Routine fields
            "repeat_rule": self.repeat_rule,  # DEPRECATED
            "repeat_pattern": self.repeat_pattern,
            "routine_batch_id": self.routine_batch_id,
            "is_flexible": self.is_flexible,
            "preferred_time_slots": self.preferred_time_slots,
            "makeup_strategy": self.makeup_strategy,
            "parent_event_id": self.parent_routine_id,  # Map parent_routine_id to parent_event_id for API
            "parent_routine_id": self.parent_routine_id,
            "routine_completed_dates": self.routine_completed_dates or [],
            # Energy consumption
            "energy_consumption": self.energy_consumption,
            "is_physically_demanding": self.is_physically_demanding,
            "is_mentally_demanding": self.is_mentally_demanding,
            "is_template": self.is_template,
            "habit_completed_count": self.habit_completed_count,
            "habit_total_count": self.habit_total_count,
            # Project association
            "project_id": self.project_id,
            "anchor_time": convert_dt(self.anchor_time),
            "energy_cost": self.energy_cost,
        }


class ProjectModel(Base):
    """Project table model - Life Projects (人生项目)"""
    __tablename__ = "projects"

    id = Column(String, primary_key=True)
    user_id = Column(String, nullable=False)

    # Basic information
    title = Column(String, nullable=False)
    description = Column(String, nullable=True)

    # Project classification
    type = Column(String, default="FINITE")  # FINITE or INFINITE
    base_tier = Column(Integer, default=1)  # 0=核心, 1=成长, 2=兴趣
    current_mode = Column(String, default="NORMAL")  # NORMAL or SPRINT
    energy_type = Column(String, default="BALANCED")  # MENTAL, PHYSICAL, BALANCED

    # Target KPIs
    target_kpi = Column(JSON, nullable=True)

    # Status
    is_active = Column(Boolean, default=True)

    # Statistics
    total_tasks = Column(Integer, default=0)
    completed_tasks = Column(Integer, default=0)
    total_focus_minutes = Column(Integer, default=0)

    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "id": self.id,
            "user_id": self.user_id,
            "title": self.title,
            "description": self.description,
            "type": self.type,
            "base_tier": self.base_tier,
            "current_mode": self.current_mode,
            "energy_type": self.energy_type,
            "target_kpi": self.target_kpi,
            "is_active": self.is_active,
            "total_tasks": self.total_tasks,
            "completed_tasks": self.completed_tasks,
            "total_focus_minutes": self.total_focus_minutes,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }

    def compute_quest_type(self) -> str:
        """Compute the quest type for tasks in this project"""
        if self.base_tier == 0 or self.current_mode == "SPRINT":
            return "MAIN"
        else:
            return "SIDE"



class SnapshotModel(Base):
    """Snapshot table model"""
    __tablename__ = "snapshots"

    id = Column(String, primary_key=True)
    user_id = Column(String, nullable=False)

    # Trigger information
    trigger_message = Column(String, nullable=False)
    trigger_time = Column(DateTime, default=datetime.utcnow)

    # Changes (stored as JSON)
    changes = Column(JSON, nullable=False, default=list)

    # Revert information
    is_reverted = Column(Boolean, default=False)
    reverted_at = Column(DateTime, nullable=True)

    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow)
    expires_at = Column(DateTime, default=datetime.utcnow)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "id": self.id,
            "user_id": self.user_id,
            "trigger_message": self.trigger_message,
            "trigger_time": self.trigger_time.isoformat() if self.trigger_time else None,
            "changes": self.changes or [],
            "is_reverted": self.is_reverted,
            "reverted_at": self.reverted_at.isoformat() if self.reverted_at else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
        }


class UserMemoryModel(Base):
    """User memory table model"""
    __tablename__ = "user_memory"

    user_id = Column(String, primary_key=True)

    # Time preference learning
    time_preferences = Column(JSON, default=dict)

    # Social profile
    social_profile = Column(JSON, default=DEFAULT_SOCIAL_PROFILE)

    # Behavior statistics
    behavior_stats = Column(JSON, default=dict)

    # Conversation summary
    conversation_summary = Column(String, default="")

    # Metadata
    updated_at = Column(DateTime, default=datetime.utcnow)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "user_id": self.user_id,
            "time_preferences": self.time_preferences or {},
            "social_profile": self.social_profile or DEFAULT_SOCIAL_PROFILE,
            "behavior_stats": self.behavior_stats or {},
            "conversation_summary": self.conversation_summary,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


class UserPreferenceModel(Base):
    """User preference learning table model"""
    __tablename__ = "user_preferences"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String, index=True, nullable=False)

    # Scenario information
    scenario_type = Column(String, nullable=False)  # 场景类型：time_conflict, event_cancellation, etc.
    context = Column(JSON)  # 上下文信息（事件类型、时间段等）

    # User decision
    decision = Column(String, nullable=False)  # 用户做出的选择
    decision_type = Column(String)  # 决策类型：merge, cancel, reschedule, etc.

    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow)
    weight = Column(Float, default=1.0)  # 权重（可以随时间衰减）

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "user_id": self.user_id,
            "scenario_type": self.scenario_type,
            "context": self.context,
            "decision": self.decision,
            "decision_type": self.decision_type,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "weight": self.weight
        }


# ============ Database Service ============

class DatabaseService:
    """Service for database operations using SQLAlchemy"""

    def __init__(self):
        self.engine = None
        self.SessionLocal = None
        self._initialized = False

    def initialize(self):
        """Initialize database connection and create tables"""
        if not self._initialized:
            # Create engine
            self.engine = create_engine(
                settings.database_url,
                connect_args={"check_same_thread": False}  # SQLite specific
            )

            # Create session factory
            self.SessionLocal = sessionmaker(
                autocommit=False,
                autoflush=False,
                bind=self.engine
            )

            # Create all tables
            Base.metadata.create_all(bind=self.engine)

            self._initialized = True
            print(f"Database initialized: {settings.database_url}")

    def get_session(self) -> Session:
        """Get database session"""
        self._ensure_initialized()
        return self.SessionLocal()

    def _ensure_initialized(self):
        """Ensure database service is initialized"""
        if not self._initialized:
            self.initialize()

    def _get_user_tz(self, session: Session, user_id: str):
        """Get user timezone object"""
        if not user_id:
            return None
        try:
            user = session.query(UserModel).filter(UserModel.id == user_id).first()
            if user and user.timezone:
                return ZoneInfo(user.timezone)
        except Exception as e:
            print(f"Error getting timezone for user {user_id}: {e}")
        return None

    def _get_utc_timezone(self):
        """Get UTC timezone"""
        return timezone.utc

    def _convert_to_local_naive(self, dt, default_tz: str = "Asia/Shanghai"):
        """
        Convert datetime to local naive datetime for storage.
        
        This ensures all stored datetimes are in local timezone (naive),
        which matches the 'naive=local' assumption in to_dict().
        
        - If dt is None, returns None
        - If dt is already naive, assumes it's local and returns as-is
        - If dt is timezone-aware (e.g., UTC from frontend), converts to local and strips tz
        """
        if dt is None:
            return None
        
        if dt.tzinfo is not None:
            # Has timezone info - convert to local timezone
            import pytz
            local_tz = pytz.timezone(default_tz)
            local_dt = dt.astimezone(local_tz)
            # Return as naive datetime (strip timezone)
            return local_dt.replace(tzinfo=None)
        else:
            # Already naive - assume it's already local
            return dt

    # ============ Event Operations ============

    async def create_event(self, event_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new event in database"""
        self._ensure_initialized()
        with self.get_session() as session:
            # Use client-provided ID if available, otherwise generate new one
            event_data = event_data.copy()
            if not event_data.get("id"):
                event_data["id"] = str(uuid.uuid4())

            # Convert enums and datetime objects to strings for database storage
            if "time_period" in event_data and event_data["time_period"] is not None:
                if hasattr(event_data["time_period"], "value"):
                    event_data["time_period"] = event_data["time_period"].value
                else:
                    event_data["time_period"] = str(event_data["time_period"])

            # Keep event_date as datetime object for SQLAlchemy
            # Do NOT convert to string - SQLAlchemy DateTime columns need datetime objects
            if "event_date" in event_data and event_data["event_date"] is not None:
                if isinstance(event_data["event_date"], str):
                    # Parse ISO format string to datetime
                    from datetime import datetime
                    event_data["event_date"] = datetime.fromisoformat(event_data["event_date"].replace('Z', '+00:00'))

            # Convert UTC timestamps to local naive datetime for consistent storage
            # This ensures 'naive=local' assumption in to_dict() works correctly
            event_data["start_time"] = self._convert_to_local_naive(event_data.get("start_time"))
            event_data["end_time"] = self._convert_to_local_naive(event_data.get("end_time"))
            event_data["event_date"] = self._convert_to_local_naive(event_data.get("event_date"))

            # Convert datetime objects to ISO format strings in energy_consumption
            if "energy_consumption" in event_data and event_data["energy_consumption"] is not None:
                ec = event_data["energy_consumption"]
                if isinstance(ec, dict):
                    if "evaluated_at" in ec and ec["evaluated_at"] is not None:
                        if hasattr(ec["evaluated_at"], "isoformat"):
                            ec["evaluated_at"] = ec["evaluated_at"].isoformat()
                        else:
                            ec["evaluated_at"] = str(ec["evaluated_at"])

            # Debug: Print event_date and start_time
            print(f"📝 DB: Creating event with event_date: {event_data.get('event_date')}, start_time: {event_data.get('start_time')}")

            # Filter out fields that don't exist in the database model
            # These fields are in the Pydantic Event model but not yet in the database table
            unsupported_fields = {
                "duration_source", "duration_confidence", "duration_actual",
                "ai_original_estimate", "display_mode",
                "ai_description", "extracted_points",
                "parent_event_id",      # Schema uses parent_event_id but DB uses parent_routine_id
                "habit_interval",        # Not yet implemented in database
            }
            filtered_data = {k: v for k, v in event_data.items() if k not in unsupported_fields}
            
            # Map parent_event_id to parent_routine_id manually
            if "parent_event_id" in event_data and event_data["parent_event_id"]:
                filtered_data["parent_routine_id"] = event_data["parent_event_id"]

            event = EventModel(**filtered_data)
            session.add(event)
            session.commit()
            session.refresh(event)

            # Merge with the original data (including unsupported fields) for return
            tz = self._get_user_tz(session, event_data.get("user_id"))
            result = event.to_dict(tz=tz)
            for key in unsupported_fields:
                if key in event_data:
                    result[key] = event_data[key]

            return result

    async def get_events(
        self,
        user_id: str,
        filters: Optional[Dict[str, Any]] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """Get events for a user with optional date range filter.

        Uses event_date as the primary field for date filtering, since recurring event
        instances use event_date to indicate which day they belong to. Falls back to
        start_time for legacy events that don't have event_date set.
        """
        self._ensure_initialized()
        with self.get_session() as session:
            from sqlalchemy import or_, and_, nullslast
            query = session.query(EventModel).filter(EventModel.user_id == user_id)

            # Apply date range filter using event_date (primary) or start_time (fallback)
            # event_date is the primary field for determining which day an event belongs to
            if start_date:
                query = query.filter(
                    or_(
                        # Events with event_date in range (recurring event instances)
                        EventModel.event_date >= start_date,
                        # Events without event_date but with start_time in range (legacy/fallback)
                        and_(
                            EventModel.event_date.is_(None),
                            EventModel.start_time >= start_date
                        )
                    )
                )
            if end_date:
                query = query.filter(
                    or_(
                        # Events with event_date in range (recurring event instances)
                        EventModel.event_date <= end_date,
                        # Events without event_date but with start_time in range (legacy/fallback)
                        and_(
                            EventModel.event_date.is_(None),
                            EventModel.start_time <= end_date
                        )
                    )
                )

            # Apply other filters
            if filters:
                for key, value in filters.items():
                    if hasattr(EventModel, key):
                        query = query.filter(getattr(EventModel, key) == value)

            # Order by event_date first (NULLS LAST), then start_time
            # Compatible with older SQLite (pre-3.30.0) where NULLS LAST is not supported
            from sqlalchemy import case
            results = query.order_by(
                case((EventModel.event_date.is_(None), 1), else_=0),
                EventModel.event_date,
                case((EventModel.start_time.is_(None), 1), else_=0),
                EventModel.start_time
            ).limit(limit).all()
            tz = self._get_user_tz(session, user_id)
            return [event.to_dict(tz=tz) for event in results]

    async def get_events_for_date(self, user_id: str, target_date: date) -> List[Dict[str, Any]]:
        """Get events for a specific date"""
        from datetime import datetime
        start_dt = datetime.combine(target_date, datetime.min.time())
        end_dt = datetime.combine(target_date, datetime.max.time())
        
        return await self.get_events(
            user_id=user_id,
            start_date=start_dt,
            end_date=end_dt,
            limit=100
        )

    async def get_event(self, event_id: str, user_id: str) -> Optional[Dict[str, Any]]:
        """Get a specific event by ID"""
        self._ensure_initialized()
        with self.get_session() as session:
            event = session.query(EventModel).filter(
                EventModel.id == event_id,
                EventModel.user_id == user_id
            ).first()
            tz = self._get_user_tz(session, user_id)
            return event.to_dict(tz=tz) if event else None

    async def get_event_instance(self, parent_id: str, event_date: date) -> Optional[Dict[str, Any]]:
        """
        Get a specific event instance by parent ID and date.

        This is used to check if an instance already exists for a given date
        before creating a new one (for on-demand instance creation).

        Args:
            parent_id: The template event ID (parent_event_id)
            event_date: The target date to check for an instance

        Returns:
            The instance event dict if found, None otherwise
        """
        self._ensure_initialized()
        with self.get_session() as session:
            event = session.query(EventModel).filter(
                EventModel.parent_routine_id == parent_id,
                func.date(EventModel.event_date) == event_date
            ).first()
            # Note: We need user_id to get timezone, but parent_id doesn't give it directly.
            # However, event has user_id.
            tz = None
            if event:
                tz = self._get_user_tz(session, event.user_id)
            return event.to_dict(tz=tz) if event else None

    async def get_recurring_templates(self, user_id: str) -> List[Dict[str, Any]]:
        """
        Get all recurring event templates for a user.

        Templates are events with is_template=True that define repeat patterns.
        These are used for client-side virtual expansion of recurring events.

        Args:
            user_id: The user ID to get templates for

        Returns:
            List of template event dictionaries
        """
        self._ensure_initialized()
        with self.get_session() as session:
            events = session.query(EventModel).filter(
                EventModel.user_id == user_id,
                EventModel.is_template == True
            ).all()
            tz = self._get_user_tz(session, user_id)
            return [event.to_dict(tz=tz) for event in events]

    async def update_event(
        self,
        event_id: str,
        user_id: str,
        update_data: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """Update an existing event"""
        self._ensure_initialized()
        with self.get_session() as session:
            event = session.query(EventModel).filter(
                EventModel.id == event_id,
                EventModel.user_id == user_id
            ).first()

            if not event:
                return None

            # Convert datetime objects to ISO format strings in energy_consumption
            if "energy_consumption" in update_data and update_data["energy_consumption"] is not None:
                ec = update_data["energy_consumption"]
                if isinstance(ec, dict):
                    if "evaluated_at" in ec and ec["evaluated_at"] is not None:
                        if hasattr(ec["evaluated_at"], "isoformat"):
                            ec["evaluated_at"] = ec["evaluated_at"].isoformat()
                        else:
                            ec["evaluated_at"] = str(ec["evaluated_at"])

            # Capture old status before update
            old_status = event.status

            # Convert UTC timestamps to local naive datetime for consistent storage
            if "start_time" in update_data:
                update_data["start_time"] = self._convert_to_local_naive(update_data["start_time"])
            if "end_time" in update_data:
                update_data["end_time"] = self._convert_to_local_naive(update_data["end_time"])
            if "event_date" in update_data:
                update_data["event_date"] = self._convert_to_local_naive(update_data["event_date"])

            # Fields that can be explicitly set to None (cleared by user)
            nullable_fields = {
                "notes", "description", "location", "start_time", "end_time",
                "event_date", "time_period", "energy_required", "energy_consumption",
                "repeat_pattern", "project_id", "parent_event_id", "routine_batch_id",
                "completed_at", "started_at"
            }

            # Update fields
            for key, value in update_data.items():
                if hasattr(event, key):
                    if value is not None or key in nullable_fields:
                        setattr(event, key, value)
            
            # Habit Tracking Trigger: If status changed to COMPLETED
            if update_data.get("status") == "COMPLETED":
                # Check if this is a Habit Instance (has parent_routine_id)
                if event.parent_routine_id:
                    # Determine completion date (use event_date or today)
                    completion_date = event.event_date or datetime.utcnow()
                    
                    # Update the Parent Routine's counts
                    # (Logic encapsulated in mark_routine_completed_for_date)
                    # We can't await here directly if this method is called within another transaction?
                    # No, this method manages its own session. But we are inside `with self.get_session() as session`.
                    # mark_routine_completed_for_date also opens a session. 
                    # To avoid nested session issues, we should implement the logic directly here or use a helper that takes a session.
                    
                    parent_routine = session.query(EventModel).filter(
                        EventModel.id == event.parent_routine_id,
                        EventModel.user_id == user_id
                    ).first()
                    
                    if parent_routine:
                        # Add completion date
                        if parent_routine.routine_completed_dates is None:
                            parent_routine.routine_completed_dates = []

                        date_str = completion_date.strftime("%Y-%m-%d")
                        # Create new list for change detection
                        current_dates = list(parent_routine.routine_completed_dates)
                        if date_str not in current_dates:
                            current_dates.append(date_str)
                            parent_routine.routine_completed_dates = current_dates
                        
                        # Update counts
                        parent_routine.habit_completed_count = len(current_dates)
                        if parent_routine.habit_total_count is None or parent_routine.habit_total_count == 0:
                            parent_routine.habit_total_count = 21
                            
                        # Sync counts to the current event instance so frontend updates immediately
                        event.habit_completed_count = parent_routine.habit_completed_count
                        event.habit_total_count = parent_routine.habit_total_count

                        event.habit_completed_count = parent_routine.habit_completed_count
                        event.habit_total_count = parent_routine.habit_total_count

            # Habit Tracking Trigger: If status changed FROM COMPLETED (Un-completion)
            if old_status == "COMPLETED" and event.status != "COMPLETED":
                if event.parent_routine_id:
                    # Determine completion date (use event_date or today)
                    completion_date = event.event_date or datetime.utcnow()
                    
                    parent_routine = session.query(EventModel).filter(
                        EventModel.id == event.parent_routine_id,
                        EventModel.user_id == user_id
                    ).first()
                    
                    if parent_routine and parent_routine.routine_completed_dates:
                        # Remove completion date
                        date_str = completion_date.strftime("%Y-%m-%d")
                        current_dates = list(parent_routine.routine_completed_dates)
                        
                        if date_str in current_dates:
                            current_dates.remove(date_str)
                            parent_routine.routine_completed_dates = current_dates
                            
                            # Update counts
                            parent_routine.habit_completed_count = len(current_dates)
                            # Update instance to reflect valid count (or 0 if user wants strict reset, but correct series count is better)
                            event.habit_completed_count = parent_routine.habit_completed_count
                            event.habit_total_count = parent_routine.habit_total_count

            event.updated_at = datetime.utcnow()
            session.commit()
            session.refresh(event)
            tz = self._get_user_tz(session, user_id)
            return event.to_dict(tz=tz)

    async def delete_event(self, event_id: str, user_id: str) -> bool:
        """Delete an event"""
        self._ensure_initialized()
        with self.get_session() as session:
            event = session.query(EventModel).filter(
                EventModel.id == event_id,
                EventModel.user_id == user_id
            ).first()

            if not event:
                return False

            session.delete(event)
            session.commit()
            return True

    async def check_time_conflict(
        self,
        user_id: str,
        start_time: datetime,
        end_time: datetime,
        exclude_event_id: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Check for time conflicts"""
        self._ensure_initialized()
        with self.get_session() as session:
            query = session.query(EventModel).filter(
                EventModel.user_id == user_id,
                EventModel.start_time.isnot(None),
                EventModel.end_time.isnot(None)
            )

            # Exclude specific event if provided
            if exclude_event_id:
                query = query.filter(EventModel.id != exclude_event_id)

            # Get all events and check overlaps manually (simpler than raw SQL)
            events = query.all()
            conflicts = []

            for event in events:
                # Check for overlap (timezone-aware comparison)
                event_start = event.start_time
                event_end = event.end_time

                # Convert all times to UTC for comparison
                def to_utc(dt):
                    """Convert datetime to UTC, preserving timezone info if present"""
                    if dt is None:
                        return None
                    if hasattr(dt, 'tzinfo') and dt.tzinfo is not None:
                        return dt.astimezone(self._get_utc_timezone())
                    # If naive datetime, assume it's already UTC and make it aware
                    return dt.replace(tzinfo=self._get_utc_timezone())

                event_start_utc = to_utc(event_start)
                event_end_utc = to_utc(event_end)
                start_time_utc = to_utc(start_time)
                end_time_utc = to_utc(end_time)

                # Check for overlap
                if start_time_utc and end_time_utc and event_start_utc and event_end_utc:
                    if (start_time_utc < event_end_utc) and (end_time_utc > event_start_utc):
                        # Use local timezone for return if possible
                        tz = self._get_user_tz(session, user_id)
                        conflicts.append(event.to_dict(tz=tz))

            return conflicts

    # ============ User Operations ============

    async def get_user(self, user_id: str) -> Optional[Dict[str, Any]]:
        """Get user by ID"""
        self._ensure_initialized()
        with self.get_session() as session:
            user = session.query(UserModel).filter(UserModel.id == user_id).first()
            return user.to_dict() if user else None

    async def get_user_by_user_id(self, user_id: str) -> Optional[Dict[str, Any]]:
        """Get user by user_id"""
        self._ensure_initialized()
        with self.get_session() as session:
            user = session.query(UserModel).filter(UserModel.user_id == user_id).first()
            return user.to_dict() if user else None

    async def create_user(self, user_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new user"""
        self._ensure_initialized()
        with self.get_session() as session:
            # Generate ID before creating model
            user_data["id"] = str(uuid.uuid4())
            user = UserModel(**user_data)
            session.add(user)
            session.commit()
            session.refresh(user)
            return user.to_dict()

    async def update_user(self, user_id: str, update_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Update user data"""
        self._ensure_initialized()
        with self.get_session() as session:
            user = session.query(UserModel).filter(UserModel.id == user_id).first()

            if not user:
                return None

            for key, value in update_data.items():
                if hasattr(user, key) and value is not None:
                    setattr(user, key, value)

            session.commit()
            session.refresh(user)
            return user.to_dict()

    # ============ Snapshot Operations ============

    async def create_snapshot(self, snapshot_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new snapshot"""
        self._ensure_initialized()
        with self.get_session() as session:
            # Generate ID before creating model
            snapshot_data["id"] = str(uuid.uuid4())
            snapshot = SnapshotModel(**snapshot_data)
            session.add(snapshot)
            session.commit()
            session.refresh(snapshot)
            return snapshot.to_dict()

    async def get_snapshots(self, user_id: str, limit: int = 10) -> List[Dict[str, Any]]:
        """Get snapshots for a user"""
        self._ensure_initialized()
        with self.get_session() as session:
            snapshots = session.query(SnapshotModel).filter(
                SnapshotModel.user_id == user_id
            ).order_by(SnapshotModel.created_at.desc()).limit(limit).all()
            return [s.to_dict() for s in snapshots]

    async def get_snapshot(self, snapshot_id: str, user_id: str) -> Optional[Dict[str, Any]]:
        """Get a specific snapshot"""
        self._ensure_initialized()
        with self.get_session() as session:
            snapshot = session.query(SnapshotModel).filter(
                SnapshotModel.id == snapshot_id,
                SnapshotModel.user_id == user_id
            ).first()
            return snapshot.to_dict() if snapshot else None

    async def update_snapshot(self, snapshot_id: str, update_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Update a snapshot"""
        self._ensure_initialized()
        with self.get_session() as session:
            snapshot = session.query(SnapshotModel).filter(
                SnapshotModel.id == snapshot_id
            ).first()

            if not snapshot:
                return None

            for key, value in update_data.items():
                if hasattr(snapshot, key) and value is not None:
                    setattr(snapshot, key, value)

            session.commit()
            session.refresh(snapshot)
            return snapshot.to_dict()

    async def delete_old_snapshots(self, user_id: str, keep_count: int = 10) -> int:
        """Delete old snapshots, keeping only most recent ones"""
        self._ensure_initialized()
        with self.get_session() as session:
            # Get all snapshots sorted by created_at desc
            all_snapshots = session.query(SnapshotModel).filter(
                SnapshotModel.user_id == user_id
            ).order_by(SnapshotModel.created_at.desc()).all()

            if len(all_snapshots) <= keep_count:
                return 0

            # Delete excess snapshots
            to_delete = all_snapshots[keep_count:]
            deleted_count = 0

            for snapshot in to_delete:
                session.delete(snapshot)
                deleted_count += 1

            session.commit()
            return deleted_count

    # ============ User Memory Operations ============

    async def get_user_memory(self, user_id: str) -> Optional[Dict[str, Any]]:
        """Get user memory"""
        self._ensure_initialized()
        with self.get_session() as session:
            memory = session.query(UserMemoryModel).filter(
                UserMemoryModel.user_id == user_id
            ).first()
            return memory.to_dict() if memory else None

    async def upsert_user_memory(self, user_id: str, memory_data: Dict[str, Any]) -> Dict[str, Any]:
        """Insert or update user memory"""
        self._ensure_initialized()
        with self.get_session() as session:
            memory = session.query(UserMemoryModel).filter(
                UserMemoryModel.user_id == user_id
            ).first()

            if memory:
                # Update
                for key, value in memory_data.items():
                    if hasattr(memory, key) and value is not None:
                        setattr(memory, key, value)
                memory.updated_at = datetime.utcnow()
            else:
                # Create
                memory = UserMemoryModel(user_id=user_id, **memory_data)
                session.add(memory)

            session.commit()
            session.refresh(memory)
            return memory.to_dict()

    # ============ User Preference Learning ============

    async def record_user_preference(
        self,
        user_id: str,
        scenario_type: str,
        decision: str,
        decision_type: str,
        context: Optional[Dict[str, Any]] = None,
        weight: float = 1.0
    ) -> Dict[str, Any]:
        """Record user decision for preference learning"""
        self._ensure_initialized()
        with self.get_session() as session:
            preference = UserPreferenceModel(
                user_id=user_id,
                scenario_type=scenario_type,
                context=context or {},
                decision=decision,
                decision_type=decision_type,
                weight=weight
            )
            session.add(preference)
            session.commit()
            session.refresh(preference)
            return preference.to_dict()

    async def get_user_preferences(
        self,
        user_id: str,
        scenario_type: Optional[str] = None,
        days_back: int = 90
    ) -> List[Dict[str, Any]]:
        """Get user preference history"""
        self._ensure_initialized()
        with self.get_session() as session:
            query = session.query(UserPreferenceModel).filter(
                UserPreferenceModel.user_id == user_id
            )

            if scenario_type:
                query = query.filter(UserPreferenceModel.scenario_type == scenario_type)

            # Filter by date
            cutoff_date = datetime.utcnow() - timedelta(days=days_back)
            query = query.filter(UserPreferenceModel.created_at >= cutoff_date)

            preferences = query.order_by(UserPreferenceModel.created_at.desc()).all()
            return [p.to_dict() for p in preferences]

    async def analyze_user_preferences(
        self,
        user_id: str,
        scenario_type: str,
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Analyze user preferences for a specific scenario

        Returns:
            {
                "predictions": [
                    {"option": "merge", "probability": 75, "confidence": "high"},
                    ...
                ],
                "recommended_action": "merge",  # if probability > 50%
                "confidence": 75,
                "sample_size": 12
            }
        """
        preferences = await self.get_user_preferences(user_id, scenario_type)

        if not preferences:
            return {
                "predictions": [],
                "recommended_action": None,
                "confidence": 0,
                "sample_size": 0,
                "reason": "no_history"
            }

        # Calculate probabilities
        decision_counts = {}
        total_weight = 0

        for pref in preferences:
            decision = pref["decision"]
            weight = pref.get("weight", 1.0)
            decision_counts[decision] = decision_counts.get(decision, 0) + weight
            total_weight += weight

        # Calculate predictions
        predictions = []
        for decision, count in decision_counts.items():
            probability = (count / total_weight * 100) if total_weight > 0 else 0

            if probability >= 70:
                confidence = "high"
            elif probability >= 40:
                confidence = "medium"
            else:
                confidence = "low"

            predictions.append({
                "option": decision,
                "probability": round(probability, 1),
                "confidence": confidence
            })

        # Sort by probability
        predictions.sort(key=lambda x: x["probability"], reverse=True)

        # Recommended action (probability > 50%)
        recommended = None
        max_confidence = 0
        if predictions:
            top = predictions[0]
            if top["probability"] > 50:
                recommended = top["option"]
                max_confidence = top["probability"]

        return {
            "predictions": predictions,
            "recommended_action": recommended,
            "confidence": max_confidence,
            "sample_size": len(preferences)
        }

    # ============ Routine/Habit Management ============

    def _generate_routine_instances(
        self,
        template: Dict[str, Any],
        repeat_pattern: Dict[str, Any],
        days_ahead: int = 90
    ) -> List[Dict[str, Any]]:
        """
        Generate routine instances from template based on repeat pattern

        Args:
            template: Template event dict
            repeat_pattern: Repeat pattern dict with 'type', 'weekdays', 'time', 'end_date'
            days_ahead: Number of days to generate instances for

        Returns:
            List of instance event dicts
        """
        instances = []

        # Get base date from template
        base_date = template.get("start_time") or template.get("event_date")
        if not base_date:
            base_date = datetime.utcnow()
        elif isinstance(base_date, str):
            from datetime import datetime
            base_date = datetime.fromisoformat(base_date.replace('Z', '+00:00'))

        repeat_type = repeat_pattern.get("type", "daily")
        end_date_str = repeat_pattern.get("end_date")
        end_date = datetime.fromisoformat(end_date_str) if end_date_str else None

        if repeat_type == "daily":
            # Generate instances for each day
            current_date = base_date
            for i in range(days_ahead):
                if end_date and current_date > end_date:
                    break

                instance_data = {
                    "title": template.get("title"),
                    "description": template.get("description"),
                    "event_date": current_date,
                    "time_period": template.get("time_period"),
                    "start_time": self._parse_time(repeat_pattern.get("time"), current_date) if repeat_pattern.get("time") else None,
                    "duration": template.get("duration"),
                    "event_type": template.get("event_type"),
                    "category": template.get("category"),
                    "tags": template.get("tags", []),
                    "location": template.get("location"),
                    "participants": template.get("participants", []),
                    "energy_consumption": template.get("energy_consumption"),
                    "is_physically_demanding": template.get("is_physically_demanding", False),
                    "is_mentally_demanding": template.get("is_mentally_demanding", False),
                    "parent_event_id": template.get("id"),
                    "is_template": False,
                    "status": "PENDING"
                }
                instances.append(instance_data)
                current_date += timedelta(days=1)

        elif repeat_type == "weekly":
            # Generate instances for specified weekdays
            weekdays = repeat_pattern.get("weekdays", [])
            current_date = base_date

            for week in range((days_ahead // 7) + 2):
                for day in range(7):
                    current_date = base_date + timedelta(weeks=week, days=day)
                    if end_date and current_date > end_date:
                        break

                    weekday_num = current_date.weekday()  # 0=Monday, 6=Sunday
                    if weekday_num in weekdays:
                        instance_data = {
                            "title": template.get("title"),
                            "description": template.get("description"),
                            "event_date": current_date,
                            "time_period": template.get("time_period"),
                            "start_time": self._parse_time(repeat_pattern.get("time"), current_date) if repeat_pattern.get("time") else None,
                            "duration": template.get("duration"),
                            "event_type": template.get("event_type"),
                            "category": template.get("category"),
                            "tags": template.get("tags", []),
                            "location": template.get("location"),
                            "participants": template.get("participants", []),
                            "energy_consumption": template.get("energy_consumption"),
                            "is_physically_demanding": template.get("is_physically_demanding", False),
                            "is_mentally_demanding": template.get("is_mentally_demanding", False),
                            "parent_event_id": template.get("id"),
                            "is_template": False,
                            "status": "PENDING"
                        }
                        instances.append(instance_data)

                if end_date and current_date > end_date:
                    break

        elif repeat_type == "monthly":
            # Generate instances for same day of each month
            current_date = base_date
            for month in range(days_ahead // 30 + 2):
                # Calculate same day of next month
                month_offset = month + 1
                try:
                    next_date = base_date.replace(month=base_date.month + month_offset)
                except ValueError:
                    # Handle day overflow (e.g., Jan 31 -> Feb)
                    next_date = (base_date.replace(month=base_date.month + month_offset, day=28))

                if end_date and next_date > end_date:
                    break

                instance_data = {
                    "title": template.get("title"),
                    "description": template.get("description"),
                    "event_date": next_date,
                    "time_period": template.get("time_period"),
                    "start_time": self._parse_time(repeat_pattern.get("time"), next_date) if repeat_pattern.get("time") else None,
                    "duration": template.get("duration"),
                    "event_type": template.get("event_type"),
                    "category": template.get("category"),
                    "tags": template.get("tags", []),
                    "location": template.get("location"),
                    "participants": template.get("participants", []),
                    "energy_consumption": template.get("energy_consumption"),
                    "is_physically_demanding": template.get("is_physically_demanding", False),
                    "is_mentally_demanding": template.get("is_mentally_demanding", False),
                    "parent_event_id": template.get("id"),
                    "is_template": False,
                    "status": "PENDING"
                }
                instances.append(instance_data)

        return instances

    def _parse_time(self, time_str: str, date: datetime) -> datetime:
        """Parse time string (HH:MM) and combine with date"""
        try:
            hour, minute = map(int, time_str.split(":"))
            return date.replace(hour=hour, minute=minute, second=0, microsecond=0)
        except (ValueError, AttributeError):
            return date

    def _calculate_habit_dates(
        self,
        start_date: datetime,
        interval: int = 1,
        count: int = 21
    ) -> List[datetime]:
        """
        Calculate habit instance dates

        Args:
            start_date: Starting date
            interval: Days between instances (1=daily, 2=every 2 days, etc.)
            count: Number of dates to calculate (default 21)

        Returns:
            List of datetime objects for habit instances
        """
        dates = []
        current = start_date

        for _ in range(count):
            dates.append(current)
            current += timedelta(days=interval)

        return dates

    async def bulk_create_events(
        self,
        events_data: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Bulk create multiple events

        Args:
            events_data: List of event data dicts

        Returns:
            List of created event dicts
        """
        self._ensure_initialized()
        with self.get_session() as session:
            created_events = []

            for event_data in events_data:
                # Generate ID
                event_data = event_data.copy()
                event_data["id"] = str(uuid.uuid4())

                # Handle enums
                if "time_period" in event_data and event_data["time_period"] is not None:
                    if hasattr(event_data["time_period"], "value"):
                        event_data["time_period"] = event_data["time_period"].value
                    else:
                        event_data["time_period"] = str(event_data["time_period"])

                # Keep event_date as datetime object
                if "event_date" in event_data and isinstance(event_data["event_date"], str):
                    event_data["event_date"] = datetime.fromisoformat(event_data["event_date"].replace('Z', '+00:00'))

                # Convert start_time to datetime if needed
                if "start_time" in event_data and event_data["start_time"] is not None:
                    if isinstance(event_data["start_time"], str):
                        event_data["start_time"] = datetime.fromisoformat(event_data["start_time"].replace('Z', '+00:00'))
                    elif isinstance(event_data["start_time"], datetime):
                        pass  # Already datetime
                    else:
                        event_data["start_time"] = datetime.combine(event_data["start_time"], datetime.min.time())

                # Filter unsupported fields (schema uses parent_event_id but DB uses parent_routine_id)
                unsupported_fields = {
                    "duration_source", "duration_confidence", "duration_actual",
                    "ai_original_estimate", "display_mode",
                    "ai_description", "extracted_points",
                    "parent_event_id",  # Map to parent_routine_id below
                }
                filtered_data = {k: v for k, v in event_data.items() if k not in unsupported_fields}

                # Map parent_event_id to parent_routine_id for DB column
                if event_data.get("parent_event_id"):
                    filtered_data["parent_routine_id"] = event_data["parent_event_id"]

                event = EventModel(**filtered_data)
                session.add(event)
                created_events.append(event)

            session.commit()

            # Refresh all events and return as dicts
            results = []
            # Get timezone from first event's user_id
            tz = None
            if created_events:
                user_id = created_events[0].user_id
                if user_id:
                    tz = self._get_user_tz(session, user_id)
            for event in created_events:
                session.refresh(event)
                results.append(event.to_dict(tz=tz))

            return results

    async def create_habit_instances(
        self,
        batch_id: str,
        dates: List[datetime],
        user_id: str,
        template_event: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """
        Batch create habit instances from a template

        Args:
            batch_id: Routine batch ID
            dates: List of datetime objects for instances
            user_id: User ID
            template_event: Template event data to copy

        Returns:
            List of created event dicts
        """
        instances_data = []

        for date in dates:
            instance = template_event.copy()
            instance["id"] = str(uuid.uuid4())  # New ID for each instance
            instance["user_id"] = user_id
            instance["routine_batch_id"] = batch_id
            instance["event_date"] = date
            instance["is_template"] = False
            instance["parent_event_id"] = None
            instance["status"] = "PENDING"
            instances_data.append(instance)

        return await self.bulk_create_events(instances_data)

    async def cancel_habit_instances(
        self,
        batch_id: str,
        user_id: str
    ) -> int:
        """
        Cancel all pending instances in a habit batch

        Args:
            batch_id: Routine batch ID
            user_id: User ID

        Returns:
            Number of instances cancelled
        """
        self._ensure_initialized()
        with self.get_session() as session:
            # Query pending instances in batch
            from sqlalchemy import and_
            events = session.query(EventModel).filter(
                and_(
                    EventModel.routine_batch_id == batch_id,
                    EventModel.user_id == user_id,
                    EventModel.status == "PENDING"
                )
            ).all()

            cancelled_count = 0
            for event in events:
                event.status = "CANCELLED"
                cancelled_count += 1

            session.commit()
            return cancelled_count

    async def get_habit_batches(
        self,
        user_id: str,
        active_only: bool = True
    ) -> List[Dict[str, Any]]:
        """
        Get all habit batches for a user

        Args:
            user_id: User ID
            active_only: If True, only return batches with pending instances

        Returns:
            List of batch dicts with batch_id, instance_count, completed_count
        """
        self._ensure_initialized()
        with self.get_session() as session:
            # Get all habit events
            events = session.query(EventModel).filter(
                EventModel.user_id == user_id,
                EventModel.event_type == "habit",
                EventModel.routine_batch_id.isnot(None)
            ).all()

            # Group by batch_id
            batches = {}
            for event in events:
                batch_id = event.routine_batch_id
                if batch_id not in batches:
                    batches[batch_id] = {
                        "batch_id": batch_id,
                        "total_instances": 0,
                        "completed_instances": 0,
                        "pending_instances": 0,
                        "cancelled_instances": 0,
                        "template": event.to_dict(tz=self._get_user_tz(session, user_id))
                    }

                batches[batch_id]["total_instances"] += 1
                status = event.status
                if status == "COMPLETED":
                    batches[batch_id]["completed_instances"] += 1
                elif status == "PENDING":
                    batches[batch_id]["pending_instances"] += 1
                elif status == "CANCELLED":
                    batches[batch_id]["cancelled_instances"] += 1

            # Filter to active batches if requested
            result = list(batches.values())
            if active_only:
                result = [b for b in result if b["pending_instances"] > 0]

            return result

    async def get_active_habit_batches(self) -> List[Dict[str, Any]]:
        """
        Get all active habit batches that need replenishment

        Returns:
            List of batch dicts with user_id, batch_id, pending_count
        """
        self._ensure_initialized()
        with self.get_session() as session:
            # Get all habit events grouped by batch_id
            from sqlalchemy import func
            results = session.query(
                EventModel.user_id,
                EventModel.routine_batch_id,
                func.count(EventModel.id).label('total')
            ).filter(
                EventModel.event_type == "habit",
                EventModel.routine_batch_id.isnot(None)
            ).group_by(
                EventModel.user_id,
                EventModel.routine_batch_id
            ).all()

            active_batches = []
            for user_id, batch_id, total in results:
                # Count pending instances for each batch
                pending = session.query(func.count(EventModel.id)).filter(
                    EventModel.user_id == user_id,
                    EventModel.routine_batch_id == batch_id,
                    EventModel.status == "PENDING"
                ).scalar() or 0

                if pending < 20:
                    active_batches.append({
                        "user_id": user_id,
                        "batch_id": batch_id,
                        "pending_count": pending
                    })

            return active_batches

    async def create_routine(
        self,
        user_id: str,
        title: str,
        description: Optional[str],
        repeat_rule: Dict[str, Any],
        is_flexible: bool = False,
        preferred_time_slots: Optional[List[Dict[str, Any]]] = None,
        makeup_strategy: str = "ask_user",
        category: str = "LIFE",
        duration: Optional[int] = None,
        # Explicit arguments to ensure persistence
        repeat_pattern: Optional[Dict[str, Any]] = None,
        event_date: Optional[datetime] = None,
        time_period: Optional[str] = "ANYTIME",
        is_template: bool = False,
        **kwargs
    ) -> Dict[str, Any]:
        """Create a new routine/habit"""
        self._ensure_initialized()
        with self.get_session() as session:
            routine = EventModel(
                id=str(uuid.uuid4()),
                user_id=user_id,
                title=title,
                description=description,
                event_type="habit",
                category=category,
                repeat_rule=repeat_rule,
                repeat_pattern=repeat_pattern,
                is_flexible=is_flexible,
                preferred_time_slots=preferred_time_slots or [],
                makeup_strategy=makeup_strategy,
                duration=duration,
                event_date=event_date,
                time_period=time_period,
                is_template=is_template,
                routine_completed_dates=[],
                status="PENDING",
                **kwargs
            )
            session.add(routine)
            session.commit()
            session.refresh(routine)
            tz = self._get_user_tz(session, user_id)
            return routine.to_dict(tz=tz)

    async def get_routines(self, user_id: str, active_only: bool = True) -> List[Dict[str, Any]]:
        """Get all routines for a user"""
        self._ensure_initialized()
        with self.get_session() as session:
            query = session.query(EventModel).filter(
                EventModel.user_id == user_id,
                EventModel.event_type == "habit",
                EventModel.parent_routine_id.is_(None)  # Only parent routines, not instances
            )

            if active_only:
                # Filter out routines with end_date in the past
                # (We'll need to parse repeat_rule to check end_date)
                pass

            routines = query.order_by(EventModel.created_at.desc()).all()
            tz = self._get_user_tz(session, user_id)
            return [r.to_dict(tz=tz) for r in routines]

    async def get_active_routines_for_date(
        self,
        user_id: str,
        target_date: datetime
    ) -> List[Dict[str, Any]]:
        """
        Get routines that should be active on a specific date

        Args:
            user_id: User ID
            target_date: Date to check

        Returns:
            List of routines that should be done on this date
        """
        self._ensure_initialized()
        with self.get_session() as session:
            routines = session.query(EventModel).filter(
                EventModel.user_id == user_id,
                EventModel.event_type == "habit",
                EventModel.parent_routine_id.is_(None)
            ).all()

            active_routines = []
            target_weekday = target_date.weekday()  # 0=Monday, 6=Sunday
            target_date_str = target_date.strftime("%Y-%m-%d")

            for routine in routines:
                # Use timezone for routine dict
                tz = self._get_user_tz(session, user_id)
                routine_dict = routine.to_dict(tz=tz)
                repeat_rule = routine_dict.get("repeat_rule", {})
                completed_dates = routine_dict.get("routine_completed_dates", [])

                # Skip if already completed on this date
                if target_date_str in completed_dates:
                    continue

                # Check if routine applies to this date
                frequency = repeat_rule.get("frequency")

                if frequency == "daily":
                    active_routines.append(routine_dict)

                elif frequency == "weekly":
                    days = repeat_rule.get("days", [])  # [0,1,2,3,4] for Mon-Fri
                    if target_weekday in days:
                        active_routines.append(routine_dict)

                elif frequency == "custom":
                    # Add more complex rules as needed
                    pass

            return active_routines

    async def mark_routine_completed_for_date(
        self,
        routine_id: str,
        user_id: str,
        completion_date: datetime
    ) -> Optional[Dict[str, Any]]:
        """
        Mark a routine as completed for a specific date

        Args:
            routine_id: Routine ID
            user_id: User ID
            completion_date: Date when routine was completed

        Returns:
            Updated routine dict or None if not found
        """
        self._ensure_initialized()
        with self.get_session() as session:
            routine = session.query(EventModel).filter(
                EventModel.id == routine_id,
                EventModel.user_id == user_id
            ).first()

            if not routine:
                return None

            # Add completion date
            if routine.routine_completed_dates is None:
                routine.routine_completed_dates = []

            date_str = completion_date.strftime("%Y-%m-%d")
            # Create a new list to ensure SQLAlchemy detects change
            current_dates = list(routine.routine_completed_dates)
            if date_str not in current_dates:
                current_dates.append(date_str)
                routine.routine_completed_dates = current_dates
            
            # Update counts for Habit Tracking
            routine.habit_completed_count = len(current_dates)
            if routine.habit_total_count is None or routine.habit_total_count == 0:
                routine.habit_total_count = 21

            routine.updated_at = datetime.utcnow()
            session.commit()
            session.refresh(routine)

            tz = self._get_user_tz(session, user_id)
            return routine.to_dict(tz=tz)

    async def get_routine_completion_stats(
        self,
        routine_id: str,
        user_id: str,
        days_back: int = 30
    ) -> Dict[str, Any]:
        """
        Get completion statistics for a routine

        Returns:
            {
                "total_days": 30,
                "completed_days": 25,
                "completion_rate": 83.3,
                "current_streak": 7,
                "longest_streak": 12
            }
        """
        self._ensure_initialized()
        with self.get_session() as session:
            routine = session.query(EventModel).filter(
                EventModel.id == routine_id,
                EventModel.user_id == user_id
            ).first()

            if not routine:
                return None

            completed_dates = routine.routine_completed_dates or []
            repeat_rule = routine.repeat_rule or {}

            # Calculate expected days based on repeat rule
            frequency = repeat_rule.get("frequency", "daily")

            if frequency == "daily":
                days_per_week = 7
            elif frequency == "weekly":
                days_per_week = len(repeat_rule.get("days", [0, 1, 2, 3, 4, 5, 6]))
            else:
                days_per_week = 7

            # Calculate total expected days in the period
            total_expected = (days_back / 7) * days_per_week
            completed_count = len([d for d in completed_dates if (datetime.now() - datetime.strptime(d, "%Y-%m-%d")).days <= days_back])

            completion_rate = (completed_count / total_expected * 100) if total_expected > 0 else 0

            return {
                "total_days": int(total_expected),
                "completed_days": completed_count,
                "completion_rate": round(completion_rate, 1),
                "completed_dates": completed_dates
            }

    # ============ Project Operations ============

    async def create_project(self, project_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new project"""
        self._ensure_initialized()
        with self.get_session() as session:
            # Generate ID if not provided
            if "id" not in project_data:
                project_data["id"] = str(uuid.uuid4())
            
            project = ProjectModel(**project_data)
            session.add(project)
            session.commit()
            session.refresh(project)
            return project.to_dict()

    async def get_projects(
        self,
        user_id: str,
        is_active: Optional[bool] = True,
        include_stats: bool = False
    ) -> List[Dict[str, Any]]:
        """Get all projects for a user"""
        self._ensure_initialized()
        with self.get_session() as session:
            query = session.query(ProjectModel).filter(ProjectModel.user_id == user_id)
            
            if is_active is not None:
                query = query.filter(ProjectModel.is_active == is_active)
            
            projects = query.order_by(ProjectModel.base_tier, ProjectModel.created_at).all()
            result = [p.to_dict() for p in projects]
            
            # Optionally include task statistics
            if include_stats:
                for proj in result:
                    # Count tasks (exclude templates AND routine/habit instances)
                    task_count = session.query(EventModel).filter(
                        EventModel.project_id == proj["id"],
                        EventModel.is_template == False,
                        EventModel.parent_routine_id.is_(None),
                        EventModel.routine_batch_id.is_(None)
                    ).count()
                    
                    completed_count = session.query(EventModel).filter(
                        EventModel.project_id == proj["id"],
                        EventModel.status == "COMPLETED",
                        EventModel.is_template == False,
                        EventModel.parent_routine_id.is_(None),
                        EventModel.routine_batch_id.is_(None)
                    ).count()
                    
                    proj["total_tasks"] = task_count
                    proj["completed_tasks"] = completed_count
                    
                    # Populate new fields
                    proj["one_off_tasks_total"] = task_count
                    proj["one_off_tasks_completed"] = completed_count
                    
                    # Calculate routine stats
                    routines = session.query(EventModel).filter(
                        EventModel.project_id == proj["id"],
                        EventModel.is_template == True
                    ).all()
                    
                    completed_executions = sum(r.habit_completed_count or 0 for r in routines)
                    total_executions = sum(r.habit_total_count or 0 for r in routines)
                    
                    proj["routine_stats"] = {
                        "total_executions": total_executions,
                        "completed_executions": completed_executions
                    }
            
            return result

    async def get_project(self, project_id: str, user_id: str) -> Optional[Dict[str, Any]]:
        """Get a specific project by ID"""
        self._ensure_initialized()
        with self.get_session() as session:
            project = session.query(ProjectModel).filter(
                ProjectModel.id == project_id,
                ProjectModel.user_id == user_id
            ).first()
            
            if not project:
                return None
                
            result = project.to_dict()
            
            # Calculate stats
            # Count tasks (exclude templates AND routine/habit instances)
            task_count = session.query(EventModel).filter(
                EventModel.project_id == project_id,
                EventModel.is_template == False,
                EventModel.parent_routine_id.is_(None),
                EventModel.routine_batch_id.is_(None)
            ).count()
            
            completed_count = session.query(EventModel).filter(
                EventModel.project_id == project_id,
                EventModel.status == "COMPLETED",
                EventModel.is_template == False,
                EventModel.parent_routine_id.is_(None),
                EventModel.routine_batch_id.is_(None)
            ).count()
            
            result["one_off_tasks_total"] = task_count
            result["one_off_tasks_completed"] = completed_count
            result["total_tasks"] = task_count
            result["completed_tasks"] = completed_count
            
            # Calculate routine stats
            routines = session.query(EventModel).filter(
                EventModel.project_id == project_id,
                EventModel.is_template == True
            ).all()
            
            completed_executions = sum(r.habit_completed_count or 0 for r in routines)
            total_executions = sum(r.habit_total_count or 0 for r in routines)
            
            result["routine_stats"] = {
                "total_executions": total_executions,
                "completed_executions": completed_executions
            }
            
            return result

    async def update_project(
        self,
        project_id: str,
        user_id: str,
        update_data: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """Update an existing project"""
        self._ensure_initialized()
        with self.get_session() as session:
            project = session.query(ProjectModel).filter(
                ProjectModel.id == project_id,
                ProjectModel.user_id == user_id
            ).first()

            if not project:
                return None

            for key, value in update_data.items():
                if hasattr(project, key) and value is not None:
                    setattr(project, key, value)

            project.updated_at = datetime.utcnow()
            session.commit()
            session.refresh(project)
            return project.to_dict()

    async def delete_project(self, project_id: str, user_id: str) -> bool:
        """Delete a project (soft delete by setting is_active=False)"""
        self._ensure_initialized()
        with self.get_session() as session:
            project = session.query(ProjectModel).filter(
                ProjectModel.id == project_id,
                ProjectModel.user_id == user_id
            ).first()

            if not project:
                return False

            # Soft delete
            project.is_active = False
            project.updated_at = datetime.utcnow()
            session.commit()
            return True

    async def set_project_mode(
        self,
        project_id: str,
        user_id: str,
        mode: str,
        warn_on_multiple_sprint: bool = True
    ) -> Dict[str, Any]:
        """
        Set project mode (NORMAL or SPRINT)
        
        If warn_on_multiple_sprint is True and user tries to set SPRINT
        when another project is already in SPRINT, return a warning.
        """
        self._ensure_initialized()
        with self.get_session() as session:
            project = session.query(ProjectModel).filter(
                ProjectModel.id == project_id,
                ProjectModel.user_id == user_id
            ).first()

            if not project:
                return {"success": False, "error": "Project not found"}

            # Check for existing SPRINT projects
            if mode == "SPRINT" and warn_on_multiple_sprint:
                existing_sprint = session.query(ProjectModel).filter(
                    ProjectModel.user_id == user_id,
                    ProjectModel.current_mode == "SPRINT",
                    ProjectModel.id != project_id,
                    ProjectModel.is_active == True
                ).first()
                
                if existing_sprint:
                    return {
                        "success": False,
                        "warning": True,
                        "message": f"Project '{existing_sprint.title}' is already in SPRINT mode. Consider completing it first.",
                        "existing_sprint_id": existing_sprint.id,
                        "existing_sprint_title": existing_sprint.title
                    }

            project.current_mode = mode
            project.updated_at = datetime.utcnow()
            session.commit()
            session.refresh(project)
            
            return {"success": True, "project": project.to_dict()}

    async def get_projects_by_ids(self, project_ids: List[str], user_id: str) -> Dict[str, Dict[str, Any]]:
        """Get multiple projects by IDs, returns a dict keyed by project_id"""
        self._ensure_initialized()
        with self.get_session() as session:
            projects = session.query(ProjectModel).filter(
                ProjectModel.id.in_(project_ids),
                ProjectModel.user_id == user_id
            ).all()
            
            return {p.id: p.to_dict() for p in projects}

    def compute_quest_type_for_event(
        self,
        event: Dict[str, Any],
        projects_cache: Dict[str, Dict[str, Any]]
    ) -> str:
        """
        Compute quest type for an event based on its project association
        
        Args:
            event: Event dictionary
            projects_cache: Dict mapping project_id to Project dict
            
        Returns:
            "MAIN", "SIDE", or "DAILY"
        """
        project_id = event.get("project_id")
        
        if project_id is None:
            return "DAILY"
        
        project = projects_cache.get(project_id)
        if project is None:
            return "DAILY"
        
        if project.get("base_tier") == 0 or project.get("current_mode") == "SPRINT":
            return "MAIN"
        else:
            return "SIDE"


# Import uuid at module level
import uuid


# Global database service instance
db_service = DatabaseService()

