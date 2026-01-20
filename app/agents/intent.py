"""
Intent Enums - Define all possible user intents
"""
from enum import Enum
from typing import Optional
from pydantic import BaseModel


class Intent(str, Enum):
    """User intent categories for RouterAgent"""

    # Event operations
    CREATE_EVENT = "create_event"
    QUERY_EVENT = "query_event"
    UPDATE_EVENT = "update_event"
    DELETE_EVENT = "delete_event"

    # Snapshot operations
    UNDO_CHANGE = "undo_change"
    RESTORE_SNAPSHOT = "restore_snapshot"

    # Energy related
    CHECK_ENERGY = "check_energy"
    SUGGEST_SCHEDULE = "suggest_schedule"

    # Query statistics
    GET_STATS = "get_stats"

    # User management
    UPDATE_PREFERENCES = "update_preferences"
    UPDATE_ENERGY_PROFILE = "update_energy_profile"

    # Small talk / general conversation
    CHITCHAT = "chitchat"
    GREETING = "greeting"
    THANKS = "thanks"
    GOODBYE = "goodbye"

    # Unknown / cannot understand
    UNKNOWN = "unknown"

    @classmethod
    def from_string(cls, value: str) -> "Intent":
        """Convert string to Intent enum"""
        try:
            return cls(value)
        except ValueError:
            return cls.UNKNOWN


class IntentConfidence(BaseModel):
    """Intent classification result with confidence score"""

    intent: Intent
    confidence: float  # 0.0 - 1.0
    reasoning: Optional[str] = None
