"""
User Diary Model - 用户观察日记模型
存储每日生成的用户行为观察日记
"""
from typing import Dict, Any, List, Optional
from datetime import datetime, date
from pydantic import BaseModel, Field
import uuid


class KeyInsights(BaseModel):
    """关键洞察"""
    activities: List[str] = Field(default_factory=list, description="活动类型")
    emotions: List[str] = Field(default_factory=list, description="情绪状态")
    patterns: List[str] = Field(default_factory=list, description="行为模式")
    time_preference: str = Field(default="unknown", description="时间偏好")
    decision_style: str = Field(default="unknown", description="决策风格")


class ExtractedSignal(BaseModel):
    """提取的行为信号"""
    type: str = Field(..., description="信号类型: habit, preference, behavior, etc.")
    value: str = Field(..., description="信号值")
    confidence: float = Field(..., ge=0, le=1, description="置信度")
    evidence: str = Field(default="", description="证据来源")


class UserDiary(BaseModel):
    """用户观察日记"""

    # Primary key
    id: str = Field(default_factory=lambda: str(uuid.uuid4()), description="Diary ID")

    # User reference
    user_id: str = Field(..., description="User ID")

    # Diary content
    diary_date: date = Field(..., description="日记日期")
    summary: str = Field(..., description="AI 生成的当天摘要（3-5句话）")
    key_insights: KeyInsights = Field(default_factory=KeyInsights, description="关键洞察")
    extracted_signals: List[ExtractedSignal] = Field(default_factory=list, description="提取的信号")

    # Daily statistics
    conversation_count: int = Field(default=0, description="当天对话数量")
    message_count: int = Field(default=0, description="当天消息数量")
    tool_calls_count: int = Field(default=0, description="当天工具调用次数")

    # Timestamps
    created_at: datetime = Field(default_factory=datetime.utcnow, description="创建时间")

    class Config:
        json_schema_extra = {
            "example": {
                "user_id": "user-123",
                "diary_date": "2026-01-23",
                "summary": "用户今天主要处理了工作任务，安排了3个会议。表现出明显的工作偏好...",
                "key_insights": {
                    "activities": ["工作", "会议"],
                    "emotions": ["专注", "高效"],
                    "patterns": ["上午工作效率高"],
                    "time_preference": "morning",
                    "decision_style": "decisive"
                },
                "extracted_signals": [
                    {
                        "type": "habit",
                        "value": "早起",
                        "confidence": 0.9,
                        "evidence": "早上8点就开始安排任务"
                    }
                ],
                "conversation_count": 5,
                "message_count": 42,
                "tool_calls_count": 15
            }
        }

    def to_dict(self) -> dict:
        """转换为字典（用于数据库存储）"""
        data = self.model_dump(mode='json')
        # 处理 date 类型
        if isinstance(data.get('diary_date'), date):
            data['diary_date'] = data['diary_date'].isoformat()
        return data

    @classmethod
    def from_dict(cls, data: dict) -> "UserDiary":
        """从字典创建"""
        # 处理 diary_date 字符串
        if isinstance(data.get('diary_date'), str):
            from datetime import datetime
            data['diary_date'] = datetime.fromisoformat(data['diary_date']).date()
        return cls(**data)


class DiaryStats(BaseModel):
    """日记统计"""
    total_diaries: int = Field(default=0, description="日记总数")
    total_conversations: int = Field(default=0, description="总对话数")
    total_messages: int = Field(default=0, description="总消息数")
    total_tool_calls: int = Field(default=0, description="总工具调用数")
    avg_conversations_per_day: float = Field(default=0.0, description="日均对话数")
    date_range: Optional[Dict[str, str]] = Field(default=None, description="日期范围")
