"""
Chat API - Conversational interface for Jarvis
"""
from typing import List, Dict, Any, Optional
from fastapi import APIRouter, HTTPException

from app.schemas.chat import ChatRequest, ChatResponse, ActionResult
from app.agents.router import router_agent
from app.agents.scheduler import schedule_agent
from app.agents.energy import energy_agent
from app.services.snapshot import snapshot_manager
from app.services.llm import llm_service
from app.agents.intent import Intent

router = APIRouter()

# Store conversation history (in production, use Redis or database)
conversation_history: Dict[str, List[Dict[str, str]]] = {}


@router.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """
    Main conversational endpoint for Jarvis

    Handles natural language input and returns agent responses

    This is the primary entry point for all interactions with Jarvis.
    """
    # Update conversation history
    if request.user_id not in conversation_history:
        conversation_history[request.user_id] = []

    conversation_history[request.user_id].append({
        "role": "user",
        "content": request.message
    })

    try:
        # Step 1: Classify intent using RouterAgent
        intent_result = await router_agent.classify_intent(
            user_message=request.message,
            user_id=request.user_id,
            conversation_history=conversation_history[request.user_id]
        )

        intent = intent_result.intent
        print(f"[RouterAgent] Intent: {intent.value}, Confidence: {intent_result.confidence}")

        # Step 2: Handle based on intent
        actions: List[ActionResult] = []
        snapshot_id: Optional[str] = None
        reply = ""

        # Handle conversation intents (greeting, thanks, goodbye, chitchat, unknown)
        if intent in [Intent.GREETING, Intent.THANKS, Intent.GOODBYE, Intent.CHITCHAT, Intent.UNKNOWN]:
            reply = await _handle_conversation(request.message, intent)

        # Handle event operations
        elif intent == Intent.CREATE_EVENT:
            result = await schedule_agent.handle_create_event(
                user_message=request.message,
                user_id=request.user_id,
                context=request.context
            )
            reply = result["reply"]
            actions = result.get("actions", [])

            # Create snapshot if changes were made
            if result["success"] and actions:
                from app.models.snapshot import EventChange
                snapshot = await snapshot_manager.create_snapshot(
                    user_id=request.user_id,
                    trigger_message=request.message,
                    changes=[EventChange(
                        event_id=actions[0]["event_id"],
                        action="create",
                        after=actions[0]["event"]
                    )]
                )
                snapshot_id = snapshot.id

        elif intent == Intent.QUERY_EVENT:
            result = await schedule_agent.handle_query_event(
                user_message=request.message,
                user_id=request.user_id,
                context=request.context
            )
            reply = result["reply"]

        elif intent == Intent.UPDATE_EVENT:
            result = await schedule_agent.handle_update_event(
                user_message=request.message,
                user_id=request.user_id,
                context=request.context
            )
            reply = result["reply"]
            actions = result.get("actions", [])

            # Create snapshot if changes were made
            if result["success"] and actions:
                from app.models.snapshot import EventChange
                snapshot = await snapshot_manager.create_snapshot(
                    user_id=request.user_id,
                    trigger_message=request.message,
                    changes=[EventChange(
                        event_id=actions[0]["event_id"],
                        action="update",
                        before=result.get("before"),
                        after=result.get("after")
                    )]
                )
                snapshot_id = snapshot.id

        elif intent == Intent.DELETE_EVENT:
            result = await schedule_agent.handle_delete_event(
                user_message=request.message,
                user_id=request.user_id,
                context=request.context
            )
            reply = result["reply"]
            actions = result.get("actions", [])

            # Create snapshot if changes were made
            if result["success"] and actions:
                from app.models.snapshot import EventChange
                snapshot = await snapshot_manager.create_snapshot(
                    user_id=request.user_id,
                    trigger_message=request.message,
                    changes=[EventChange(
                        event_id=actions[0]["event_id"],
                        action="delete",
                        before=result.get("before")
                    )]
                )
                snapshot_id = snapshot.id

        # Handle snapshot operations
        elif intent == Intent.UNDO_CHANGE:
            result = await snapshot_manager.undo_last_change(request.user_id)
            reply = result["message"]

        elif intent == Intent.RESTORE_SNAPSHOT:
            # For now, treat as undo (specific snapshot ID would need to be parsed)
            result = await snapshot_manager.undo_last_change(request.user_id)
            reply = result["message"]

        # Handle energy operations
        elif intent == Intent.CHECK_ENERGY:
            result = await energy_agent.check_energy(request.user_id)
            reply = result["message"]

        elif intent == Intent.SUGGEST_SCHEDULE:
            result = await energy_agent.suggest_schedule(request.user_id)
            reply = result["message"]

        # Handle stats operations
        elif intent == Intent.GET_STATS:
            reply = "统计功能正在开发中，敬请期待！"

        else:
            reply = "我没有完全理解您的意图，能再说一遍吗？"

        # Add assistant response to conversation history
        conversation_history[request.user_id].append({
            "role": "assistant",
            "content": reply
        })

        return ChatResponse(
            reply=reply,
            actions=actions,
            snapshot_id=snapshot_id
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


# ============ Helper Functions ============

async def _handle_conversation(message: str, intent: Intent) -> str:
    """
    Handle conversational intents (greeting, thanks, goodbye, chitchat)

    Args:
        message: User's message
        intent: Classified intent

    Returns:
        Natural language response
    """
    from app.agents.intent import Intent
    from app.services.prompt import prompt_service
    import random

    if intent == Intent.GREETING:
        greetings = [
            "你好！我是 Jarvis，你的 AI 生活管家。有什么我可以帮你的吗？",
            "Hi！我是 Jarvis。今天有什么安排需要我帮忙的吗？",
            "你好呀！我是 Jarvis，随时为你效劳。"
        ]
        return random.choice(greetings)

    elif intent == Intent.THANKS:
        thanks = [
            "不客气！这是我的荣幸。",
            "很高兴能帮到你！",
            "随时为你服务！"
        ]
        return random.choice(thanks)

    elif intent == Intent.GOODBYE:
        goodbyes = [
            "再见！祝你今天愉快！",
            "拜拜，有需要随时找我！",
            "再见！期待下次交流。"
        ]
        return random.choice(goodbyes)

    elif intent == Intent.CHITCHAT:
        # Load Jarvis persona from external file
        system_prompt = prompt_service.load_prompt("jarvis_persona")

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": message}
        ]

        response = await llm_service.chat_completion(messages, temperature=0.7)
        return response["content"]

    else:  # UNKNOWN
        return (
            "抱歉，我没有完全理解您的意思。\n\n"
            "您可以试着这样对我说：\n"
            "- 帮我安排明天下午3点开会\n"
            "- 我明天有什么安排\n"
            "- 取消今天的会议\n"
            "- 我现在状态怎么样\n"
            "- 帮我安排一下今天\n"
            "- 撤销刚才的操作"
        )
