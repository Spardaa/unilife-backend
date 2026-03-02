"""
Conversation Summary Model - 对话摘要模型
用于存储对话历史的压缩摘要，减少上下文 token 消耗
"""
from sqlalchemy import Column, String, DateTime, Text, Integer, Boolean, ForeignKey, Index
from sqlalchemy.orm import declarative_base, relationship
from datetime import datetime
import uuid
from typing import Dict, Any, Optional

from app.models.conversation import Base


class ConversationSummary(Base):
    """对话摘要"""
    __tablename__ = "conversation_summaries"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    conversation_id = Column(String, ForeignKey("conversations.id"), index=True, nullable=True)
    user_id = Column(String, index=True, nullable=False)

    # 摘要内容
    summary_text = Column(Text, nullable=False)

    # 摘要范围
    start_message_id = Column(String)  # 摘要开始的消息ID
    end_message_id = Column(String)    # 摘要结束的消息ID
    message_count = Column(Integer, default=0)  # 摘要覆盖的消息数

    # 元数据
    created_at = Column(DateTime, default=datetime.utcnow)
    is_active = Column(Boolean, default=True)  # 清空缓存时设为 False

    # 压缩级别（用于混合压缩时的优先级）
    compression_level = Column(Integer, default=0)  # 0=原始摘要，1=一次压缩，2=两次压缩...

    # 关联
    # conversation = relationship("Conversation", backref="summaries")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "conversation_id": self.conversation_id,
            "user_id": self.user_id,
            "summary_text": self.summary_text,
            "start_message_id": self.start_message_id,
            "end_message_id": self.end_message_id,
            "message_count": self.message_count,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "is_active": self.is_active,
            "compression_level": self.compression_level
        }


# 创建索引
Index('idx_summary_user_active', ConversationSummary.user_id, ConversationSummary.is_active)
Index('idx_summary_conversation', ConversationSummary.conversation_id)
