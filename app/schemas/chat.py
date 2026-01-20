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
    context: Optional[ChatContext] = Field(None, description="Optional context")


class ActionResult(BaseModel):
    """Result of an action taken by the agent"""
    type: str = Field(..., description="Action type: create_event, update_event, etc.")
    event_id: Optional[str] = Field(None, description="Event ID if applicable")
    event: Optional[Dict[str, Any]] = Field(None, description="Event data if applicable")


class ChatResponse(BaseModel):
    """Response model for chat endpoint"""
    reply: str = Field(..., description="Agent's natural language response")
    actions: List[ActionResult] = Field(default_factory=list, description="Actions taken by agent")
    snapshot_id: Optional[str] = Field(None, description="Snapshot ID if changes were made")


class ChatFeedbackRequest(BaseModel):
    """Request model for feedback endpoint"""
    user_id: str
    message_id: str
    rating: int = Field(..., ge=1, le=5, description="Rating from 1 to 5")
    comment: Optional[str] = None
