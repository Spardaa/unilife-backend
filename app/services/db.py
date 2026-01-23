"""
Database Service - SQLite with SQLAlchemy
"""
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
from sqlalchemy import create_engine, Column, String, Integer, DateTime, Boolean, JSON, Numeric, Float
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
import uuid

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
    wechat_id = Column(String, nullable=True, unique=True)
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
            "wechat_id": self.wechat_id,
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

    # Time information (all optional to support different event types)
    start_time = Column(DateTime, nullable=True)
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

    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow)
    created_by = Column(String, default="user")

    # AI reasoning fields
    ai_confidence = Column(Numeric(3, 2), default=0.5)
    ai_reasoning = Column(String, nullable=True)

    # Routine/Habit specific fields (for long-term recurring events)
    repeat_rule = Column(JSON, nullable=True)  # {"frequency": "weekly", "days": [1,2,3,4,5], "end_date": "2026-06-30"}
    is_flexible = Column(Boolean, default=False)  # Whether time is flexible (decide each day)
    preferred_time_slots = Column(JSON, nullable=True)  # Preferred time slots: [{"start": "18:00", "end": "20:00", "priority": 1}]
    makeup_strategy = Column(String, nullable=True)  # Strategy when missed: "ask_user", "auto_next_day", "auto_same_day_next_week"
    parent_routine_id = Column(String, nullable=True)  # For routine instances: which routine they belong to
    routine_completed_dates = Column(JSON, nullable=True)  # Track which dates the routine was completed: ["2026-01-20", "2026-01-21"]

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "id": self.id,
            "user_id": self.user_id,
            "title": self.title,
            "description": self.description,
            "start_time": self.start_time.isoformat() if self.start_time else None,
            "end_time": self.end_time.isoformat() if self.end_time else None,
            "duration": self.duration,
            "energy_required": self.energy_required,
            "urgency": self.urgency,
            "importance": self.importance,
            "is_deep_work": self.is_deep_work,
            "event_type": self.event_type,
            "category": self.category,
            "tags": self.tags or [],
            "location": self.location,
            "participants": self.participants or [],
            "status": self.status,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "created_by": self.created_by,
            "ai_confidence": float(self.ai_confidence) if self.ai_confidence else 0.5,
            "ai_reasoning": self.ai_reasoning,
            # Routine fields
            "repeat_rule": self.repeat_rule,
            "is_flexible": self.is_flexible,
            "preferred_time_slots": self.preferred_time_slots,
            "makeup_strategy": self.makeup_strategy,
            "parent_routine_id": self.parent_routine_id,
            "routine_completed_dates": self.routine_completed_dates or [],
        }


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

    # ============ Event Operations ============

    async def create_event(self, event_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new event in database"""
        self._ensure_initialized()
        with self.get_session() as session:
            # Generate ID before creating model
            event_data["id"] = str(uuid.uuid4())

            # Filter out fields that don't exist in the database model
            # These fields are in the Pydantic Event model but not yet in the database table
            unsupported_fields = {
                "duration_source", "duration_confidence", "duration_actual",
                "ai_original_estimate", "display_mode", "energy_consumption",
                "ai_description", "extracted_points"
            }
            filtered_data = {k: v for k, v in event_data.items() if k not in unsupported_fields}

            event = EventModel(**filtered_data)
            session.add(event)
            session.commit()
            session.refresh(event)

            # Merge with the original data (including unsupported fields) for return
            result = event.to_dict()
            for key in unsupported_fields:
                if key in event_data:
                    result[key] = event_data[key]

            return result

    async def get_events(
        self,
        user_id: str,
        filters: Optional[Dict[str, Any]] = None,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """Get events for a user"""
        self._ensure_initialized()
        with self.get_session() as session:
            query = session.query(EventModel).filter(EventModel.user_id == user_id)

            # Apply filters
            if filters:
                for key, value in filters.items():
                    if hasattr(EventModel, key):
                        query = query.filter(getattr(EventModel, key) == value)

            results = query.order_by(EventModel.start_time).limit(limit).all()
            return [event.to_dict() for event in results]

    async def get_event(self, event_id: str, user_id: str) -> Optional[Dict[str, Any]]:
        """Get a specific event by ID"""
        self._ensure_initialized()
        with self.get_session() as session:
            event = session.query(EventModel).filter(
                EventModel.id == event_id,
                EventModel.user_id == user_id
            ).first()
            return event.to_dict() if event else None

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

            # Update fields
            for key, value in update_data.items():
                if hasattr(event, key) and value is not None:
                    setattr(event, key, value)

            event.updated_at = datetime.utcnow()
            session.commit()
            session.refresh(event)
            return event.to_dict()

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
                # Check for overlap (handle naive datetimes)
                event_start = event.start_time
                event_end = event.end_time

                # Strip timezone info if present for comparison
                if event_start and hasattr(event_start, 'tzinfo') and event_start.tzinfo is not None:
                    event_start = event_start.replace(tzinfo=None)
                if event_end and hasattr(event_end, 'tzinfo') and event_end.tzinfo is not None:
                    event_end = event_end.replace(tzinfo=None)
                if start_time and hasattr(start_time, 'tzinfo') and start_time.tzinfo is not None:
                    start_time = start_time.replace(tzinfo=None)
                if end_time and hasattr(end_time, 'tzinfo') and end_time.tzinfo is not None:
                    end_time = end_time.replace(tzinfo=None)

                # Check for overlap
                if start_time and end_time and event_start and event_end:
                    if (start_time < event_end) and (end_time > event_start):
                        conflicts.append(event.to_dict())

            return conflicts

    # ============ User Operations ============

    async def get_user(self, user_id: str) -> Optional[Dict[str, Any]]:
        """Get user by ID"""
        self._ensure_initialized()
        with self.get_session() as session:
            user = session.query(UserModel).filter(UserModel.id == user_id).first()
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
                event_type="HABIT",
                category=category,
                repeat_rule=repeat_rule,
                is_flexible=is_flexible,
                preferred_time_slots=preferred_time_slots or [],
                makeup_strategy=makeup_strategy,
                duration=duration,
                routine_completed_dates=[],
                status="PENDING",
                **kwargs
            )
            session.add(routine)
            session.commit()
            session.refresh(routine)
            return routine.to_dict()

    async def get_routines(self, user_id: str, active_only: bool = True) -> List[Dict[str, Any]]:
        """Get all routines for a user"""
        self._ensure_initialized()
        with self.get_session() as session:
            query = session.query(EventModel).filter(
                EventModel.user_id == user_id,
                EventModel.event_type == "HABIT",
                EventModel.parent_routine_id.is_(None)  # Only parent routines, not instances
            )

            if active_only:
                # Filter out routines with end_date in the past
                # (We'll need to parse repeat_rule to check end_date)
                pass

            routines = query.order_by(EventModel.created_at.desc()).all()
            return [r.to_dict() for r in routines]

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
                EventModel.event_type == "HABIT",
                EventModel.parent_routine_id.is_(None)
            ).all()

            active_routines = []
            target_weekday = target_date.weekday()  # 0=Monday, 6=Sunday
            target_date_str = target_date.strftime("%Y-%m-%d")

            for routine in routines:
                routine_dict = routine.to_dict()
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
            if date_str not in routine.routine_completed_dates:
                routine.routine_completed_dates.append(date_str)

            routine.updated_at = datetime.utcnow()
            session.commit()
            session.refresh(routine)

            return routine.to_dict()

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


# Import uuid at module level
import uuid


# Global database service instance
db_service = DatabaseService()
