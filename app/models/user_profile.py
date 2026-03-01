"""
User Profile Model - 用户画像模型 (简化版)
存储用户的核心偏好和显式规则
"""
from typing import Dict, Any, List, Optional
from datetime import datetime
from pydantic import BaseModel, Field
import uuid


class UserProfile(BaseModel):
    """用户画像（简化版）
    
    保留核心功能：
    - 用户偏好字典（简单键值对）
    - 用户显式规则列表
    - 学习到的模式统计
    """

    # Primary key
    id: str = Field(default_factory=lambda: str(uuid.uuid4()), description="Profile ID")

    # User reference
    user_id: str = Field(..., description="User ID")

    # 简化的偏好存储（替代4个子模型）
    preferences: Dict[str, Any] = Field(
        default_factory=lambda: {
            "conflict_strategy": "ask",  # ask / prioritize_urgent / merge
            "time_style": "flexible",    # flexible / structured
            # 作息时间配置
            "wake_time": "08:00",        # 起床时间 (HH:MM)
            "sleep_time": "22:00",       # 睡觉时间 (HH:MM)
            # 通知开关
            "morning_briefing_enabled": True,    # 早安简报
            "afternoon_checkin_enabled": True,   # 午间检查
            "evening_switch_enabled": True,      # 晚间切换
            "closing_ritual_enabled": True,      # 睡前仪式
            "event_reminders_enabled": True,     # 日程提醒
            "event_reminder_minutes": 15,        # 提前提醒时间（分钟）
            # 破冰状态
            "needs_onboarding": True,            # 是否需要破冰（新用户默认 True）
        },
        description="用户偏好字典"
    )

    # 用户显式表达的规则（如"周五晚上不安排工作"）
    explicit_rules: List[str] = Field(
        default_factory=list,
        description="用户显式规则列表"
    )

    # 学习到的模式统计
    learned_patterns: Dict[str, float] = Field(
        default_factory=dict,
        description="行为模式统计，如 {'prefers_morning_meetings': 0.8}"
    )

    # Metadata
    created_at: datetime = Field(default_factory=datetime.utcnow, description="创建时间")
    updated_at: datetime = Field(default_factory=datetime.utcnow, description="更新时间")

    class Config:
        json_schema_extra = {
            "example": {
                "user_id": "user-123",
                "preferences": {
                    "conflict_strategy": "merge",
                    "time_style": "flexible"
                },
                "explicit_rules": [
                    "周五晚上不安排工作",
                    "早上9点前不开会"
                ],
                "learned_patterns": {
                    "prefers_afternoon_work": 0.7,
                    "cancels_when_tired": 0.6
                }
            }
        }

    def to_dict(self) -> dict:
        """转换为字典（用于数据库存储）"""
        return self.model_dump(mode='json')

    @classmethod
    def from_dict(cls, data: dict) -> "UserProfile":
        """从字典创建"""
        # 兼容旧格式
        if "relationships" in data or "identity" in data:
            # 从旧格式迁移，但尽可能保留现有数据
            return cls(
                user_id=data.get("user_id", ""),
                preferences=data.get("preferences", {"conflict_strategy": "ask", "time_style": "flexible"}),
                explicit_rules=data.get("explicit_rules", []),
                learned_patterns=data.get("learned_patterns", {})
            )
        return cls(**data)

    def update_preference(self, key: str, value: Any):
        """更新单个偏好"""
        self.preferences[key] = value
        self.updated_at = datetime.utcnow()

    def add_explicit_rule(self, rule: str):
        """添加显式规则"""
        if rule and rule not in self.explicit_rules:
            self.explicit_rules.append(rule)
            self.updated_at = datetime.utcnow()

    def remove_explicit_rule(self, rule: str):
        """移除显式规则"""
        if rule in self.explicit_rules:
            self.explicit_rules.remove(rule)
            self.updated_at = datetime.utcnow()

    def update_pattern(self, pattern_name: str, confidence: float):
        """更新学习模式的置信度"""
        # 加权平均：新值占30%，旧值占70%
        old_value = self.learned_patterns.get(pattern_name, 0.5)
        new_value = old_value * 0.7 + confidence * 0.3
        self.learned_patterns[pattern_name] = round(new_value, 2)
        self.updated_at = datetime.utcnow()

    def get_summary(self) -> Dict[str, Any]:
        """获取摘要（用于注入 Agent）"""
        return {
            "conflict_strategy": self.preferences.get("conflict_strategy", "ask"),
            "explicit_rules": self.explicit_rules[:5],  # 最多5条规则
            "top_patterns": dict(
                sorted(
                    self.learned_patterns.items(),
                    key=lambda x: x[1],
                    reverse=True
                )[:3]  # 最多3个高置信度模式
            )
        }
