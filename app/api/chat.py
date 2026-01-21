"""
Chat API - Conversational interface for Jarvis (重构版)
使用新的 Jarvis Agent (LLM + Tools 架构)
"""
from typing import List, Dict, Any, Optional
from fastapi import APIRouter, HTTPException

from app.schemas.chat import ChatRequest, ChatResponse, ActionResult
from app.agents.jarvis import jarvis_agent
from app.services.snapshot import snapshot_manager

router = APIRouter()

# Store conversation history (in production, use Redis or database)
conversation_history: Dict[str, List[Dict[str, str]]] = {}


@router.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """
    Main conversational endpoint for Jarvis

    新架构说明：
    - 使用 Jarvis Agent（LLM + Tools）
    - 自动推理和工具调用
    - 支持多步对话和上下文理解
    """
    # Get conversation history for this user
    user_history = conversation_history.get(request.user_id, [])

    try:
        # Call Jarvis Agent
        result = await jarvis_agent.chat(
            user_message=request.message,
            user_id=request.user_id,
            conversation_history=user_history
        )

        reply = result["reply"]
        actions = result.get("actions", [])
        tool_calls = result.get("tool_calls", [])
        updated_history = result.get("conversation_history", user_history)
        suggestions = result.get("suggestions")

        # Create snapshot if there were modifying actions
        snapshot_id = None
        if actions and any(a["type"] in ["create_event", "update_event", "delete_event"] for a in actions):
            try:
                from app.models.snapshot import EventChange

                # Build changes list from actions
                changes = []
                for action in actions:
                    change_dict = {
                        "event_id": action["event_id"],
                        "action": action["type"].replace("_event", ""),  # create_event -> create
                        "event": action.get("event")
                    }
                    if "before" in action:
                        change_dict["before"] = action["before"]
                    if "after" in action:
                        change_dict["after"] = action["after"]

                    changes.append(EventChange(**change_dict))

                # Create snapshot
                snapshot = await snapshot_manager.create_snapshot(
                    user_id=request.user_id,
                    trigger_message=request.message,
                    changes=changes
                )
                snapshot_id = snapshot.id

            except Exception as e:
                # Snapshot creation failure shouldn't break the chat
                print(f"[Chat API] Warning: Failed to create snapshot: {e}")

        # Update conversation history
        conversation_history[request.user_id] = updated_history

        # Convert actions to schema format
        action_responses = [
            ActionResult(
                type=action["type"],
                event_id=action.get("event_id"),
                event=action.get("event")
            )
            for action in actions
        ]

        # Convert suggestions to schema format
        suggestion_responses = None
        if suggestions:
            from app.schemas.chat import Suggestion
            suggestion_responses = [
                Suggestion(
                    label=s.get("label"),
                    value=s.get("value"),
                    description=s.get("description")
                )
                for s in suggestions
            ]

        return ChatResponse(
            reply=reply,
            actions=action_responses,
            snapshot_id=snapshot_id,
            suggestions=suggestion_responses
        )

    except Exception as e:
        print(f"[Chat API] Error: {e}")
        import traceback
        traceback.print_exc()

        return ChatResponse(
            reply=f"抱歉，处理您的请求时出现了错误：{str(e)}。请稍后重试。",
            actions=[],
            snapshot_id=None
        )


@router.post("/chat/feedback")
async def chat_feedback(request: Dict[str, Any]):
    """
    Provide feedback on agent responses for learning

    This endpoint allows users to rate agent responses,
    which will be used to improve performance over time.
    """
    # TODO: Implement feedback storage and learning
    # Store feedback in database for MemoryAgent to learn from
    return {
        "status": "success",
        "message": "感谢您的反馈，我们会持续改进！"
    }


@router.get("/chat/history")
async def get_chat_history(user_id: str, limit: int = 50):
    """Get conversation history for a user"""
    history = conversation_history.get(user_id, [])
    return {
        "user_id": user_id,
        "history": history[-limit:]
    }


@router.delete("/chat/history")
async def clear_chat_history(user_id: str):
    """Clear conversation history for a user"""
    if user_id in conversation_history:
        conversation_history[user_id] = []
    return {
        "status": "success",
        "message": "对话历史已清除。"
    }
