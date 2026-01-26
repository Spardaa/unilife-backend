"""
Conversation Service - 对话服务
负责对话历史的管理和智能上下文选择
"""
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
from sqlalchemy import create_engine, desc, and_, or_
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import StaticPool
import pytz

from app.models.conversation import Conversation, Message, Base
from app.config import settings


def _get_user_local_time(utc_time: datetime, timezone_str: str = "Asia/Shanghai") -> datetime:
    """
    将 UTC 时间转换为用户本地时间

    Args:
        utc_time: UTC 时间
        timezone_str: 时区字符串（如 "Asia/Shanghai"）

    Returns:
        用户本地时间
    """
    try:
        tz = pytz.timezone(timezone_str)
        # 如果 utc_time 没有 timezone 信息，先设置为 UTC
        if utc_time.tzinfo is None:
            utc_time = pytz.UTC.localize(utc_time)
        return utc_time.astimezone(tz).replace(tzinfo=None)
    except:
        # 如果时区转换失败，直接返回原时间
        return utc_time


class ConversationService:
    """对话服务"""

    def __init__(self, db_path: str = None):
        """
        初始化对话服务

        Args:
            db_path: 数据库路径（默认使用 settings.database_url）
        """
        if db_path is None:
            # 从 settings.database_url 提取路径
            db_path = settings.database_url.replace("sqlite:///", "")

        self.engine = create_engine(
            f"sqlite:///{db_path}",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
            echo=False  # 关闭 SQL 日志
        )

        # 创建表（如果不存在）
        Base.metadata.create_all(self.engine)

        self.SessionLocal = sessionmaker(
            autocommit=False,
            autoflush=False,
            bind=self.engine
        )

    def get_session(self) -> Session:
        """获取数据库会话"""
        return self.SessionLocal()

    def create_conversation(
        self,
        user_id: str,
        title: str = None,
        extra_metadata: str = None
    ) -> Conversation:
        """
        创建新对话会话

        Args:
            user_id: 用户ID
            title: 会话标题（可选）
            extra_metadata: 元数据JSON字符串（可选）

        Returns:
            Conversation 对象
        """
        db = self.get_session()
        try:
            conversation = Conversation(
                user_id=user_id,
                title=title,
                extra_metadata=extra_metadata
            )
            db.add(conversation)
            db.commit()
            db.refresh(conversation)
            return conversation
        finally:
            db.close()

    def get_conversation(
        self,
        conversation_id: str
    ) -> Optional[Conversation]:
        """获取对话会话"""
        db = self.get_session()
        try:
            return db.query(Conversation).filter(
                Conversation.id == conversation_id
            ).first()
        finally:
            db.close()

    def list_conversations(
        self,
        user_id: str,
        limit: int = 50,
        offset: int = 0
    ) -> List[Conversation]:
        """
        列出用户的对话会话

        Args:
            user_id: 用户ID
            limit: 返回数量限制
            offset: 偏移量

        Returns:
            对话会话列表
        """
        db = self.get_session()
        try:
            return db.query(Conversation).filter(
                Conversation.user_id == user_id
            ).order_by(
                desc(Conversation.updated_at)
            ).limit(limit).offset(offset).all()
        finally:
            db.close()

    def add_message(
        self,
        conversation_id: str,
        role: str,
        content: str,
        tool_calls: str = None,
        tool_call_id: str = None,
        tokens_used: int = None,
        extra_metadata: str = None
    ) -> Message:
        """
        添加消息到对话

        Args:
            conversation_id: 对话ID
            role: 消息角色（user, assistant, system, tool）
            content: 消息内容
            tool_calls: 工具调用JSON字符串（可选）
            tool_call_id: 工具调用ID（可选，用于tool消息）
            tokens_used: 使用的token数量（可选）
            extra_metadata: 元数据JSON字符串（可选）

        Returns:
            Message 对象
        """
        db = self.get_session()
        try:
            message = Message(
                conversation_id=conversation_id,
                role=role,
                content=content,
                tool_calls=tool_calls,
                tool_call_id=tool_call_id,
                tokens_used=tokens_used,
                extra_metadata=extra_metadata
            )
            db.add(message)

            # 更新对话的消息数量和更新时间
            conversation = db.query(Conversation).filter(
                Conversation.id == conversation_id
            ).first()
            if conversation:
                conversation.message_count += 1
                conversation.updated_at = datetime.utcnow()

            db.commit()
            db.refresh(message)
            return message
        finally:
            db.close()

    def get_messages(
        self,
        conversation_id: str,
        limit: int = None,
        offset: int = 0
    ) -> List[Message]:
        """
        获取对话的消息列表

        Args:
            conversation_id: 对话ID
            limit: 返回数量限制
            offset: 偏移量

        Returns:
            消息列表
        """
        db = self.get_session()
        try:
            query = db.query(Message).filter(
                Message.conversation_id == conversation_id
            ).order_by(Message.created_at)

            if limit:
                query = query.limit(limit)
            if offset:
                query = query.offset(offset)

            return query.all()
        finally:
            db.close()

    def get_context_for_llm(
        self,
        conversation_id: str,
        max_messages: int = 20,
        max_tokens: int = 8000
    ) -> List[Dict[str, Any]]:
        """
        为LLM获取智能上下文

        策略：
        1. 优先获取最近的消息
        2. 确保消息序列完整性（成对的 tool_calls + tool 消息）
        3. 控制总token数量

        Args:
            conversation_id: 对话ID
            max_messages: 最大消息数量
            max_tokens: 最大token数估算

        Returns:
            格式化的消息列表（用于LLM）
        """
        messages = self.get_messages(
            conversation_id,
            limit=max_messages * 2  # 多取一些，后续筛选
        )

        # 按时间倒序排列，从最新的开始选择
        messages.reverse()

        selected_messages = []
        total_tokens = 0
        last_assistant_had_tool_calls = False

        for msg in messages:
            # 转换为聊天格式
            chat_msg = msg.to_chat_format()

            # 估算token数量（粗略估算：1字符≈0.5token）
            content = chat_msg.get("content", "")
            msg_tokens = len(content) * 0.5
            if chat_msg.get("tool_calls"):
                msg_tokens += 100  # tool_calls 的额外开销

            # 检查是否超出限制
            if total_tokens + msg_tokens > max_tokens and selected_messages:
                break

            # 确保消息序列完整性
            if chat_msg["role"] == "tool":
                # 只保留有对应 tool_calls 的 tool 消息
                if last_assistant_had_tool_calls:
                    selected_messages.append(chat_msg)
                    total_tokens += msg_tokens
                    last_assistant_had_tool_calls = False
            else:
                selected_messages.append(chat_msg)
                total_tokens += msg_tokens
                if chat_msg["role"] == "assistant":
                    last_assistant_had_tool_calls = bool(chat_msg.get("tool_calls"))
                else:
                    last_assistant_had_tool_calls = False

        # 恢复正确的时间顺序
        selected_messages.reverse()

        return selected_messages

    def delete_conversation(self, conversation_id: str) -> bool:
        """
        删除对话（及其所有消息）

        Args:
            conversation_id: 对话ID

        Returns:
            是否成功删除
        """
        db = self.get_session()
        try:
            # 删除消息
            db.query(Message).filter(
                Message.conversation_id == conversation_id
            ).delete()

            # 删除对话
            result = db.query(Conversation).filter(
                Conversation.id == conversation_id
            ).delete()

            db.commit()
            return result > 0
        finally:
            db.close()

    def update_conversation_title(
        self,
        conversation_id: str,
        title: str
    ) -> bool:
        """更新对话标题"""
        db = self.get_session()
        try:
            conversation = db.query(Conversation).filter(
                Conversation.id == conversation_id
            ).first()
            if conversation:
                conversation.title = title
                db.commit()
                return True
            return False
        finally:
            db.close()

    def get_recent_conversations(
        self,
        user_id: str,
        days: int = 7,
        limit: int = 10
    ) -> List[Conversation]:
        """
        获取最近的对话会话

        Args:
            user_id: 用户ID
            days: 最近多少天
            limit: 返回数量限制

        Returns:
            对话会话列表
        """
        db = self.get_session()
        try:
            since = datetime.utcnow() - timedelta(days=days)
            return db.query(Conversation).filter(
                and_(
                    Conversation.user_id == user_id,
                    Conversation.created_at >= since
                )
            ).order_by(
                desc(Conversation.updated_at)
            ).limit(limit).all()
        finally:
            db.close()

    async def get_recent_context(
        self,
        user_id: str,
        conversation_id: str,
        hours: int = 72,
        max_messages: int = 30
    ) -> List[Dict[str, Any]]:
        """
        获取近 N 小时内的对话历史（带时间戳标注）

        这是系统的"短期记忆"功能，用于给 Agent 提供完整的对话上下文。

        Args:
            user_id: 用户ID
            conversation_id: 当前对话ID
            hours: 时间窗口（小时），默认 72 小时（3天）
            max_messages: 最大消息数量（来回对话数量）

        Returns:
            带时间戳的消息列表，格式：
            [
                {"role": "user", "content": "...", "timestamp": "[22:30]"},
                {"role": "assistant", "content": "...", "timestamp": "[22:31]"},
                ...
            ]
        """
        db = self.get_session()
        try:
            # 获取用户时区
            from app.services.db import db_service
            user = await db_service.get_user(user_id)
            user_timezone = user.get("timezone", "Asia/Shanghai") if user else "Asia/Shanghai"

            # 计算时间边界
            since = datetime.utcnow() - timedelta(hours=hours)

            # 获取当前对话
            current_conv = db.query(Conversation).filter(
                Conversation.id == conversation_id
            ).first()

            if not current_conv:
                return []

            # 获取当前对话的消息
            messages = db.query(Message).filter(
                and_(
                    Message.conversation_id == conversation_id,
                    Message.created_at >= since
                )
            ).order_by(Message.created_at).all()

            # 获取用户的其他对话（补充上下文）
            other_conv_messages = db.query(Message).join(
                Conversation, Message.conversation_id == Conversation.id
            ).filter(
                and_(
                    Conversation.user_id == user_id,
                    Conversation.id != conversation_id,
                    Message.created_at >= since
                )
            ).order_by(Message.created_at).all()

            # 合并并按时间排序
            all_messages = messages + other_conv_messages
            all_messages.sort(key=lambda m: m.created_at)

            # 只取最近的 max_messages 条消息（来回对话）
            all_messages = all_messages[-max_messages:]

            # 转换为带时间戳的格式（用户本地时间）
            result = []
            for msg in all_messages:
                # 将 UTC 时间转换为用户本地时间
                local_time = _get_user_local_time(msg.created_at, user_timezone)
                timestamp = local_time.strftime("%H:%M")
                result.append({
                    "role": msg.role,
                    "content": msg.content,
                    "timestamp": f"[{timestamp}]"
                })

            return result

        finally:
            db.close()


# 全局对话服务实例
conversation_service = ConversationService()
