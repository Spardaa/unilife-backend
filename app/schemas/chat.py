"""
Chat Schemas - Request and Response models for chat API
"""
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field


class ChatContext(BaseModel):
    """Context for chat requests"""
    channel: str = Field(..., description="Channel type: wechat, web, etc.")
    session_id: Optional[str] = Field(None, description="Optional session identifier")


class ChatRequest(BaseModel):
    """Request model for chat endpoint"""
    user_id: str = Field(..., description="User ID")
    message: str = Field(..., description="User's natural language message")
    conversation_id: Optional[str] = Field(None, description="Conversation ID (None will create a new conversation)")
    context: Optional[ChatContext] = Field(None, description="Optional context")
    current_time: Optional[str] = Field(None, description="Virtual current time for testing (format: YYYY-MM-DD HH:MM:SS)")


class ActionResult(BaseModel):
    """Result of an action taken by the agent"""
    type: str = Field(..., description="Action type: create_event, update_event, etc.")
    event_id: Optional[str] = Field(None, description="Event ID if applicable")
    event: Optional[Dict[str, Any]] = Field(None, description="Event data if applicable")


class Suggestion(BaseModel):
    """Interactive suggestion option for user to select"""
    label: str = Field(..., description="Display label shown to user")
    value: Optional[str] = Field(None, description="Actual value (None means user needs to input manually)")
    description: Optional[str] = Field(None, description="Optional detailed description")
    probability: Optional[int] = Field(None, description="AI predicted probability (0-100) that user will choose this option")


class InteractiveOption(BaseModel):
    """Option for interactive question"""
    label: str = Field(..., description="Display label shown to user")
    value: str = Field(..., description="Actual value")


class InteractiveQuestion(BaseModel):
    """Interactive question for user to answer (supports multi-question)"""
    id: str = Field(..., description="Question unique identifier")
    text: str = Field(..., description="Question text displayed to user")
    type: str = Field(..., description="Question type: single_choice, multiple_choice, text_input")
    options: Optional[List[InteractiveOption]] = Field(None, description="Options list (required for choice types)")
    placeholder: Optional[str] = Field(None, description="Input placeholder (for text_input type)")


class QueryStats(BaseModel):
    """Statistics from query results"""
    total: Optional[int] = Field(None, description="Total count")
    pending: Optional[int] = Field(None, description="Pending count")
    completed: Optional[int] = Field(None, description="Completed count")


class QueryResult(BaseModel):
    """Structured query result for frontend rendering"""
    type: str = Field(..., description="Result type: events, schedule_overview, statistics, routine")
    events: Optional[List[Dict[str, Any]]] = Field(None, description="List of events if type is 'events'")
    statistics: Optional[QueryStats] = Field(None, description="Statistics data")
    count: Optional[int] = Field(None, description="Total count of results")


class ChatResponse(BaseModel):
    """Response model for chat endpoint"""
    reply: str = Field(..., description="Agent's natural language response")
    actions: List[ActionResult] = Field(default_factory=list, description="Actions taken by agent")
    snapshot_id: Optional[str] = Field(None, description="Snapshot ID if changes were made")
    suggestions: Optional[List[Suggestion]] = Field(None, description="Interactive suggestions for user to select")
    questions: Optional[List[InteractiveQuestion]] = Field(None, description="Interactive questions for user to answer (multi-question support)")
    query_results: Optional[List[QueryResult]] = Field(None, description="Structured query results for UI rendering")
    conversation_id: Optional[str] = Field(None, description="Conversation ID for continuing this conversation")

    # Smart decision fields
    auto_action: Optional[Dict[str, Any]] = Field(None, description="Auto-executed action based on user preference (probability > 50%)")
    alternative_options: Optional[List[Dict[str, Any]]] = Field(None, description="Alternative options if user is not satisfied with auto_action")
    confidence: Optional[int] = Field(None, description="Confidence level of auto_action (0-100)")


class ChatFeedbackRequest(BaseModel):
    """Request model for feedback endpoint"""
    user_id: str
    message_id: str
    rating: int = Field(..., ge=1, le=5, description="Rating from 1 to 5")
    comment: Optional[str] = None


class CreateConversationRequest(BaseModel):
    """Request model for creating a conversation"""
    user_id: str = Field(..., description="User ID")
    title: Optional[str] = Field(None, description="Conversation title (optional)")


class ConversationResponse(BaseModel):
    """Response model for conversation"""
    id: str
    user_id: str
    title: Optional[str]
    created_at: str
    updated_at: str
    message_count: int


class MessageResponse(BaseModel):
    """Response model for message"""
    id: str
    conversation_id: str
    role: str
    content: Optional[str]
    created_at: str
