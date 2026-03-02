"""
Chat API - Conversational interface for UniLife (多智能体架构版)
使用 AgentOrchestrator 协调 Router、Executor、Persona、Observer
"""
from typing import List, Dict, Any, Optional
from fastapi import APIRouter, HTTPException
import json
from datetime import datetime, timedelta

from app.schemas.chat import (
    ChatRequest, ChatResponse, ActionResult,
    CreateConversationRequest, ConversationResponse, MessageResponse
)
from app.agents.orchestrator import agent_orchestrator
from app.services.snapshot import snapshot_manager
from app.services.conversation_service import conversation_service
import pytz

# Hardcoded daily limit for AI requests
MAX_DAILY_AI_REQUESTS = 50


async def handle_test_observer_command(
    user_id: str,
    conversation_id: str,
    message: str
) -> ChatResponse:
    """
    处理 /test_observer 命令
    触发一次 Observer 的 daily_review 方法，并输出诊断信息
    用法: /test_observer 或 /test_observer 2026-03-01
    """
    from app.agents.observer import observer_agent
    from app.services.db import db_service

    # 解析可选的日期参数
    parts = message.strip().split()
    if len(parts) > 1:
        date_str = parts[1]
    else:
        user_tz = pytz.timezone("Asia/Shanghai")
        date_str = datetime.now(user_tz).strftime("%Y-%m-%d")

    # === 诊断阶段：检查数据源 ===
    diagnostics = []

    # 1. 检查对话历史 - 修复：使用 get_user_message_history 替代 get_recent_context
    # 因为后者需要有效的 conversation_id，空字符串会直接返回空
    try:
        context_messages = conversation_service.get_user_message_history(
            user_id=user_id,
            limit=200
        )
        # 过滤24小时内的消息
        user_tz = pytz.timezone("Asia/Shanghai")
        now = datetime.now(user_tz)
        cutoff = now - timedelta(hours=24)
        if context_messages:
            context_messages = [
                m for m in context_messages
                if m.created_at.replace(tzinfo=pytz.UTC).astimezone(user_tz) >= cutoff
            ]
        msg_count = len(context_messages) if context_messages else 0
        diagnostics.append(f"📝 对话消息数: {msg_count}")
    except Exception as e:
        import traceback
        traceback.print_exc()
        diagnostics.append(f"📝 对话消息数: 获取失败 - {str(e)}")
        context_messages = None

    # 2. 检查当日事件 - 修复：将字符串日期转换为 datetime 对象
    try:
        user_tz = pytz.timezone("Asia/Shanghai")
        dt = datetime.strptime(date_str, "%Y-%m-%d")
        dt = user_tz.localize(dt)
        start_dt = dt.replace(hour=0, minute=0, second=0, microsecond=0)
        end_dt = dt.replace(hour=23, minute=59, second=59, microsecond=999999)

        today_events = await db_service.get_events(
            user_id=user_id,
            start_date=start_dt,
            end_date=end_dt
        )
        event_count = len(today_events) if today_events else 0
        diagnostics.append(f"📅 当日事件数: {event_count}")
    except Exception as e:
        import traceback
        traceback.print_exc()
        diagnostics.append(f"📅 当日事件数: 获取失败 - {str(e)}")
        today_events = None

    # 3. 检查 soul.md
    try:
        from app.services.soul_service import soul_service
        soul = soul_service.get_soul(user_id)
        soul_status = f"{len(soul)} 字符" if soul else "不存在"
        diagnostics.append(f"🧠 soul.md: {soul_status}")
    except Exception as e:
        diagnostics.append(f"🧠 soul.md: 获取失败 - {str(e)}")

    # 4. 检查 memory.md
    try:
        from app.services.memory_service import memory_service
        memory = memory_service.get_memory(user_id)
        memory_status = f"{len(memory)} 字符" if memory else "不存在"
        diagnostics.append(f"📔 memory.md: {memory_status}")
    except Exception as e:
        diagnostics.append(f"📔 memory.md: 获取失败 - {str(e)}")

    # === 执行 Observer ===
    try:
        result = await observer_agent.daily_review(
            user_id=user_id,
            date_str=date_str
        )

        if result:
            reply = f"✅ Observer daily_review 已执行 (日期: {date_str})\n\n"
            reply += "## 诊断信息\n" + "\n".join(diagnostics) + "\n\n"
            reply += f"## 执行结果\n{result}"
        else:
            reply = f"⚠️ Observer 返回空 (日期: {date_str})\n\n"
            reply += "## 诊断信息\n" + "\n".join(diagnostics) + "\n\n"
            reply += "**可能原因**:\n"
            reply += "- 对话消息数 = 0 且 当日事件数 = 0\n"
            reply += "- LLM 响应解析失败"

    except Exception as e:
        import traceback
        traceback.print_exc()
        reply = f"❌ 执行 daily_review 时出错: {str(e)}\n\n"
        reply += "## 诊断信息\n" + "\n".join(diagnostics)

    # 保存消息到对话历史
    conversation_service.add_message(
        conversation_id=conversation_id,
        role="user",
        content=message
    )
    conversation_service.add_message(
        conversation_id=conversation_id,
        role="assistant",
        content=reply
    )

    return ChatResponse(
        reply=reply,
        actions=[],
        snapshot_id=None,
        conversation_id=conversation_id
    )

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
        from app.services.db import db_service
        # Check daily AI request limit
        is_allowed = await db_service.check_and_increment_ai_request(
            user_id=request.user_id,
            limit=MAX_DAILY_AI_REQUESTS
        )
        
        if not is_allowed:
            # Create a limit reached message
            reply = f"抱歉，您今天已经达到了每日 {MAX_DAILY_AI_REQUESTS} 次对话请求上限。请明天再来吧！"
            
            # Save user message
            conversation_service.add_message(
                conversation_id=conversation_id,
                role="user",
                content=request.message
            )
            
            # Save assistant message
            conversation_service.add_message(
                conversation_id=conversation_id,
                role="assistant",
                content=reply
            )
            
            return ChatResponse(
                reply=reply,
                actions=[],
                snapshot_id=None,
                conversation_id=conversation_id
            )

        # 拦截测试命令 (不消耗 AI 请求配额)
        if request.message.strip().startswith("/test_observer"):
            return await handle_test_observer_command(
                user_id=request.user_id,
                conversation_id=conversation_id,
                message=request.message
            )

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

        # 保存助手回复（含 tool_calls 如果有）
        tool_calls_json = None
        if tool_calls:
            tool_calls_json = json.dumps(tool_calls)
        
        assistant_msg = conversation_service.add_message(
            conversation_id=conversation_id,
            role="assistant",
            content=reply,
            tool_calls=tool_calls_json
        )

        # 🔧 核心修复：保存 tool 执行结果到数据库
        # 这样下一轮对话加载历史时，tool_calls 和 tool results 配对完整
        # LLM 就能知道上次问了什么问题、给出了什么选项
        tool_result_pairs = result.get("tool_results", [])
        if tool_result_pairs:
            for pair in tool_result_pairs:
                conversation_service.add_message(
                    conversation_id=conversation_id,
                    role="tool",
                    content=pair.get("result", "{}"),
                    tool_call_id=pair.get("tool_call_id")
                )

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

        # Convert questions to schema format
        question_responses = None
        questions_data = result.get("questions")
        if questions_data:
            from app.schemas.chat import InteractiveQuestion, InteractiveOption
            question_responses = []
            for q in questions_data:
                options = None
                if q.get("options"):
                    options = [
                        InteractiveOption(label=o.get("label", ""), value=o.get("value", ""))
                        for o in q["options"]
                    ]
                question_responses.append(
                    InteractiveQuestion(
                        id=q.get("id", ""),
                        text=q.get("text", ""),
                        type=q.get("type", "single_choice"),
                        options=options,
                        placeholder=q.get("placeholder")
                    )
                )

        # Convert query_results to schema format
        query_results = result.get("query_results")
        query_result_responses = None
        if query_results:
            from app.schemas.chat import QueryResult, QueryStats
            query_result_responses = []
            for qr in query_results:
                stats = None
                if qr.get("statistics"):
                    stats = QueryStats(
                        total=qr["statistics"].get("total"),
                        pending=qr["statistics"].get("pending"),
                        completed=qr["statistics"].get("completed")
                    )
                query_result_responses.append(
                    QueryResult(
                        type=qr.get("type", "events"),
                        events=qr.get("events"),
                        statistics=stats,
                        count=qr.get("count")
                    )
                )

        return ChatResponse(
            reply=reply,
            actions=action_responses,
            snapshot_id=snapshot_id,
            suggestions=suggestion_responses,
            questions=question_responses,
            query_results=query_result_responses,
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


@router.post("/chat/clear_context")
async def clear_chat_context(request: Dict[str, Any]):
    """
    清空聊天上下文 - 记录清空时间戳

    前端聊天界面清空后调用此接口,
    后端记录 chat_cleared_at 时间戳,
    后续 get_recent_context 会过滤掉此时间之前的消息。
    数据库中的聊天记录不会被删除，用户仍可通过日期查询历史记录。
    """
    user_id = request.get("user_id")
    if not user_id:
        raise HTTPException(status_code=400, detail="user_id is required")

    try:
        from app.services.db import db_service, UserModel
        from sqlalchemy import or_
        db_service._ensure_initialized()
        session = db_service.get_session()
        try:
            user = session.query(UserModel).filter(
                or_(UserModel.id == user_id, UserModel.user_id == user_id)
            ).first()
            if not user:
                raise HTTPException(status_code=404, detail="User not found")

            user.chat_cleared_at = datetime.utcnow()
            session.commit()

            return {
                "status": "success",
                "message": "聊天上下文已清空",
                "cleared_at": user.chat_cleared_at.isoformat()
            }
        finally:
            session.close()
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"清空聊天上下文失败: {str(e)}")


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

@router.get("/messages/history", response_model=List[MessageResponse])
async def get_message_history(
    user_id: str,
    limit: int = 50,
    before: Optional[datetime] = None
):
    """
    获取用户的完整消息历史（跨会话，按时间倒序）
    用于实现类似微信/WhatsApp的连续聊天记录体验
    """
    messages = conversation_service.get_user_message_history(
        user_id=user_id,
        limit=limit,
        before=before
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

@router.get("/messages/history/dates", response_model=List[str])
async def get_message_history_dates(
    user_id: str
):
    """
    获取用户包含聊天记录的所有日期列表
    格式: ["YYYY-MM-DD", ...]
    """
    try:
        from app.services.db import db_service
        user = await db_service.get_user(user_id)
        user_timezone = user.get("timezone", "Asia/Shanghai") if user else "Asia/Shanghai"
        
        dates = conversation_service.get_user_message_dates(
            user_id=user_id,
            timezone_str=user_timezone
        )
        return dates
    except Exception as e:
        print(f"[Chat API] Error getting message dates: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))
