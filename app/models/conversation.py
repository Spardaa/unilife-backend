"""
Conversation and Message Models - 对话和消息数据模型
用于持久化存储用户对话历史
"""
from sqlalchemy import Column, String, DateTime, Text, Float, Integer, ForeignKey, Index
from sqlalchemy.orm import declarative_base, relationship
from datetime import datetime
import uuid
from typing import Dict, Any, List, Optional

Base = declarative_base()


class Conversation(Base):
    """对话会话"""
    __tablename__ = "conversations"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String, index=True, nullable=False)

    # 会话信息
    title = Column(String)  # 会话标题（可选，自动生成或用户指定）
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # 统计信息
    message_count = Column(Integer, default=0)  # 消息数量

    # 元数据
    extra_metadata = Column(Text)  # JSON字符串，存储额外信息（如标签、摘要等）

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "user_id": self.user_id,
            "title": self.title,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "message_count": self.message_count,
            "extra_metadata": self.extra_metadata
        }


class Message(Base):
    """对话消息"""
    __tablename__ = "messages"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    conversation_id = Column(String, ForeignKey("conversations.id"), index=True, nullable=False)

    # 消息内容
    role = Column(String, nullable=False)  # user, assistant, system, tool
    content = Column(Text)  # 消息内容

    # 工具调用相关（当 role=assistant 时）
    tool_calls = Column(Text)  # JSON字符串，存储tool_calls信息

    # 工具返回结果（当 role=tool 时）
    tool_call_id = Column(String)  # 对应的tool_call_id

    # 时间戳
    created_at = Column(DateTime, default=datetime.utcnow, index=True)

    # Token 统计
    tokens_used = Column(Integer)  # 使用的token数量

    # 元数据
    extra_metadata = Column(Text)  # JSON字符串，存储额外信息

    # 关联
    conversation = relationship("Conversation", backref="messages")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "conversation_id": self.conversation_id,
            "role": self.role,
            "content": self.content,
            "tool_calls": self.tool_calls,
            "tool_call_id": self.tool_call_id,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "tokens_used": self.tokens_used,
            "extra_metadata": self.extra_metadata
        }

    def to_chat_format(self) -> Dict[str, Any]:
        """
        转换为聊天格式（用于传递给LLM）
        """
        msg = {
            "role": self.role,
            "content": self.content
        }

        # 添加 tool_calls（如果有）
        if self.tool_calls:
            import json
            msg["tool_calls"] = json.loads(self.tool_calls)

        # 添加 tool_call_id（如果是tool消息）
        if self.tool_call_id:
            msg["tool_call_id"] = self.tool_call_id

        return msg


# 创建索引
Index('idx_conversation_user_time', Conversation.user_id, Conversation.created_at)
Index('idx_message_conversation_time', Message.conversation_id, Message.created_at)
