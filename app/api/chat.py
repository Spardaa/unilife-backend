"""
Chat API - Conversational interface for UniLife (多智能体架构版)
使用 AgentOrchestrator 协调 Router、Executor、Persona、Observer
"""
from typing import List, Dict, Any, Optional
from fastapi import APIRouter, HTTPException
import json

from app.schemas.chat import (
    ChatRequest, ChatResponse, ActionResult,
    CreateConversationRequest, ConversationResponse, MessageResponse
)
from app.agents.orchestrator import agent_orchestrator
from app.services.snapshot import snapshot_manager
from app.services.conversation_service import conversation_service

router = APIRouter()


@router.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """
    Main conversational endpoint for UniLife

    多智能体架构说明：
    - Router → 识别意图，决定路由
    - Executor → 执行工具调用（如果需要）
    - Persona → 生成拟人化回复
    - Observer → 异步分析，更新画像

    如果提供 conversation_id，继续现有对话
    如果不提供，创建新对话
    """
    # 获取或创建对话
    conversation_id = request.conversation_id
    if conversation_id:
        conversation = conversation_service.get_conversation(conversation_id)
        if not conversation:
            # 对话不存在，创建新的
            conversation = conversation_service.create_conversation(
                user_id=request.user_id,
                title=request.message[:50]  # 用第一条消息的前50字符作为标题
            )
            conversation_id = conversation.id
    else:
        # 创建新对话
        conversation = conversation_service.create_conversation(
            user_id=request.user_id,
            title=request.message[:50]  # 用第一条消息的前50字符作为标题
        )
        conversation_id = conversation.id

    try:
        # Call Agent Orchestrator (before saving user message to avoid duplication)
        result = await agent_orchestrator.process_message(
            user_message=request.message,
            user_id=request.user_id,
            conversation_id=conversation_id,
            current_time=request.current_time  # Pass virtual time for testing
        )

        # Save user message after orchestrator processing
        conversation_service.add_message(
            conversation_id=conversation_id,
            role="user",
            content=request.message
        )

        reply = result["reply"]
        actions = result.get("actions", [])
        tool_calls = result.get("tool_calls", [])
        suggestions = result.get("suggestions")
        routing_metadata = result.get("routing_metadata", {})

        # 保存助手回复（不含 tool_calls，因为后面会单独保存）
        assistant_msg_id = conversation_service.add_message(
            conversation_id=conversation_id,
            role="assistant",
            content=reply
        ).id

        # 保存 tool_calls（如果有）
        if tool_calls:
            import json
            from app.services.conversation_service import Message
            db = conversation_service.get_session()
            try:
                msg = db.query(Message).filter(Message.id == assistant_msg_id).first()
                if msg:
                    msg.tool_calls = json.dumps(tool_calls)
                    db.commit()
            finally:
                db.close()

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
            suggestions=suggestion_responses,
            conversation_id=conversation_id  # 返回对话ID，前端下次请求时带上
        )

    except Exception as e:
        print(f"[Chat API] Error: {e}")
        import traceback
        traceback.print_exc()

        # 即使出错也保存错误消息
        conversation_service.add_message(
            conversation_id=conversation_id,
            role="assistant",
            content=f"抱歉，处理您的请求时出现了错误：{str(e)}。请稍后重试。"
        )

        return ChatResponse(
            reply=f"抱歉，处理您的请求时出现了错误：{str(e)}。请稍后重试。",
            actions=[],
            snapshot_id=None,
            conversation_id=conversation_id
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


# Conversation Management Endpoints

@router.post("/conversations", response_model=ConversationResponse)
async def create_conversation(request: CreateConversationRequest):
    """创建新对话会话"""
    conversation = conversation_service.create_conversation(
        user_id=request.user_id,
        title=request.title
    )
    return ConversationResponse(
        id=conversation.id,
        user_id=conversation.user_id,
        title=conversation.title,
        created_at=conversation.created_at.isoformat(),
        updated_at=conversation.updated_at.isoformat(),
        message_count=conversation.message_count
    )


@router.get("/conversations", response_model=List[ConversationResponse])
async def list_conversations(
    user_id: str,
    limit: int = 50,
    offset: int = 0
):
    """获取用户的对话列表"""
    conversations = conversation_service.list_conversations(
        user_id=user_id,
        limit=limit,
        offset=offset
    )
    return [
        ConversationResponse(
            id=c.id,
            user_id=c.user_id,
            title=c.title,
            created_at=c.created_at.isoformat(),
            updated_at=c.updated_at.isoformat(),
            message_count=c.message_count
        )
        for c in conversations
    ]


@router.get("/conversations/{conversation_id}", response_model=ConversationResponse)
async def get_conversation(conversation_id: str):
    """获取对话详情"""
    conversation = conversation_service.get_conversation(conversation_id)
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return ConversationResponse(
        id=conversation.id,
        user_id=conversation.user_id,
        title=conversation.title,
        created_at=conversation.created_at.isoformat(),
        updated_at=conversation.updated_at.isoformat(),
        message_count=conversation.message_count
    )


@router.get("/conversations/{conversation_id}/messages", response_model=List[MessageResponse])
async def get_conversation_messages(
    conversation_id: str,
    limit: int = 100,
    offset: int = 0
):
    """获取对话的消息列表"""
    messages = conversation_service.get_messages(
        conversation_id=conversation_id,
        limit=limit,
        offset=offset
    )
    return [
        MessageResponse(
            id=m.id,
            conversation_id=m.conversation_id,
            role=m.role,
            content=m.content,
            created_at=m.created_at.isoformat()
        )
        for m in messages
    ]


@router.delete("/conversations/{conversation_id}")
async def delete_conversation(conversation_id: str):
    """删除对话"""
    success = conversation_service.delete_conversation(conversation_id)
    if not success:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return {"status": "success", "message": "对话已删除"}


@router.put("/conversations/{conversation_id}/title")
async def update_conversation_title(
    conversation_id: str,
    title: str
):
    """更新对话标题"""
    success = conversation_service.update_conversation_title(
        conversation_id=conversation_id,
        title=title
    )
    if not success:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return {"status": "success", "message": "标题已更新"}
