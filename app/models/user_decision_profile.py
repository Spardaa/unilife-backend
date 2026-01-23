"""
User Decision Profile Model - 用户决策偏好模型
存储用户在不同场景下的决策模式，用于 Executor 智能决策
"""
from typing import Dict, Any, List, Optional
from datetime import datetime
from pydantic import BaseModel, Field
import uuid


class TimePreference(BaseModel):
    """时间偏好"""
    start_of_day: str = Field(default="09:00", description="一天开始时间")
    end_of_day: str = Field(default="22:00", description="一天结束时间")
    deep_work_window: List[str] = Field(
        default_factory=lambda: ["09:00", "12:00"],
        description="深度工作时间窗口 [开始, 结束]"
    )
    shallow_work_window: List[str] = Field(
        default_factory=lambda: ["14:00", "17:00"],
        description="浅层工作时间窗口 [开始, 结束]"
    )
    break_preference: str = Field(default="flexible", description="休息偏好: fixed | flexible | none")


class MeetingPreference(BaseModel):
    """会议偏好"""
    stacking_style: str = Field(
        default="stacked",
        description="会议堆叠风格: stacked（连续）| spaced（分散）| flexible（灵活）"
    )
    max_back_to_back: int = Field(default=3, description="最多连续会议数")
    buffer_time: int = Field(default=15, description="会议间缓冲时间（分钟）")
    preferred_days: List[int] = Field(
        default_factory=lambda: [0, 1, 2, 3, 4],  # 周一到周五
        description="偏好开会的星期几（0=周一, 6=周日）"
    )


class EnergyProfile(BaseModel):
    """能量模式"""
    peak_hours: List[str] = Field(
        default_factory=lambda: ["09:00", "11:00"],
        description="高峰时段"
    )
    low_hours: List[str] = Field(
        default_factory=lambda: ["14:00", "16:00"],
        description="低谷时段"
    )
    energy_by_day: Dict[str, str] = Field(
        default_factory=lambda: {
            "monday": "high",
            "tuesday": "high",
            "wednesday": "medium",
            "thursday": "medium",
            "friday": "low",
            "saturday": "low",
            "sunday": "low"
        },
        description="每天的能量水平: high | medium | low"
    )


class ConflictResolution(BaseModel):
    """冲突解决偏好"""
    strategy: str = Field(
        default="ask",
        description="默认策略: ask（询问）| prioritize_urgent（优先紧急）| prioritize_important（优先重要）| merge（合并）"
    )
    cancellation_threshold: float = Field(
        default=0.8,
        description="取消事件的置信度阈值（>= 0.8 才自动取消）"
    )
    reschedule_preference: str = Field(
        default="same_day",
        description="重新安排偏好: same_day | next_available | ask"
    )


class ScenarioPreference(BaseModel):
    """特定场景的偏好"""
    scenario_type: str = Field(..., description="场景类型（如 time_conflict, event_cancellation）")
    preferred_action: str = Field(..., description="首选行动")
    confidence: float = Field(default=0.5, ge=0, le=1, description="置信度")
    sample_count: int = Field(default=1, description="样本数量")
    last_updated: datetime = Field(default_factory=datetime.utcnow)


class UserDecisionProfile(BaseModel):
    """
    用户决策偏好

    存储用户在不同决策场景下的模式，帮助 Executor 做出更符合用户偏好的决策。
    与 UserProfile 不同，这里关注"怎么做决策"而非"用户是什么样的人"。
    """
    # Primary key
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))

    # User reference
    user_id: str

    # 时间偏好
    time_preference: TimePreference = Field(default_factory=TimePreference)

    # 会议偏好
    meeting_preference: MeetingPreference = Field(default_factory=MeetingPreference)

    # 能量模式
    energy_profile: EnergyProfile = Field(default_factory=EnergyProfile)

    # 冲突解决偏好
    conflict_resolution: ConflictResolution = Field(default_factory=ConflictResolution)

    # 场景化偏好（从历史决策中学习）
    scenario_preferences: List[ScenarioPreference] = Field(default_factory=list)

    # 显式规则（用户直接告诉我们的规则）
    explicit_rules: List[str] = Field(default_factory=list)

    # 置信度分数（各种预测的准确度）
    confidence_scores: Dict[str, float] = Field(
        default_factory=lambda: {
            "time_estimation": 0.5,
            "conflict_resolution": 0.5,
            "energy_prediction": 0.5
        }
    )

    # 元数据
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    class Config:
        json_schema_extra = {
            "example": {
                "user_id": "user-123",
                "time_preference": {
                    "start_of_day": "08:00",
                    "end_of_day": "23:00",
                    "deep_work_window": ["09:00", "12:00"],
                    "shallow_work_window": ["14:00", "17:00"]
                },
                "meeting_preference": {
                    "stacking_style": "stacked",
                    "max_back_to_back": 3,
                    "buffer_time": 10
                },
                "conflict_resolution": {
                    "strategy": "prioritize_important",
                    "cancellation_threshold": 0.85
                },
                "scenario_preferences": [
                    {
                        "scenario_type": "time_conflict",
                        "preferred_action": "merge",
                        "confidence": 0.8,
                        "sample_count": 12
                    }
                ]
            }
        }

    def to_dict(self) -> dict:
        """转换为字典（用于数据库存储）"""
        return self.model_dump(mode='json')

    @classmethod
    def from_dict(cls, data: dict) -> "UserDecisionProfile":
        """从字典创建"""
        return cls(**data)

    def get_scenario_preference(self, scenario_type: str) -> Optional[ScenarioPreference]:
        """获取特定场景的偏好"""
        for pref in self.scenario_preferences:
            if pref.scenario_type == scenario_type:
                return pref
        return None

    def update_scenario_preference(
        self,
        scenario_type: str,
        action: str,
        confidence: float = 0.5
    ) -> ScenarioPreference:
        """更新或创建场景偏好"""
        existing = self.get_scenario_preference(scenario_type)

        if existing:
            # 更新现有偏好（加权平均）
            alpha = 0.3  # 新数据权重
            existing.confidence = (1 - alpha) * existing.confidence + alpha * confidence
            existing.sample_count += 1
            existing.last_updated = datetime.utcnow()
            # 如果置信度更高，更新首选行动
            if confidence > existing.confidence * 0.9:
                existing.preferred_action = action
            self.updated_at = datetime.utcnow()
            return existing
        else:
            # 创建新偏好
            new_pref = ScenarioPreference(
                scenario_type=scenario_type,
                preferred_action=action,
                confidence=confidence,
                sample_count=1
            )
            self.scenario_preferences.append(new_pref)
            self.updated_at = datetime.utcnow()
            return new_pref

    def add_explicit_rule(self, rule: str) -> None:
        """添加显式规则"""
        if rule not in self.explicit_rules:
            self.explicit_rules.append(rule)
            self.updated_at = datetime.utcnow()

    def remove_explicit_rule(self, rule: str) -> bool:
        """移除显式规则"""
        if rule in self.explicit_rules:
            self.explicit_rules.remove(rule)
            self.updated_at = datetime.utcnow()
            return True
        return False

    def get_rules_for_context(self, context: Dict[str, Any]) -> List[str]:
        """根据上下文获取相关规则"""
        relevant_rules = []
        context_str = str(context).lower()

        for rule in self.explicit_rules:
            # 简单的关键词匹配
            rule_lower = rule.lower()
            if any(keyword in context_str for keyword in rule_lower.split()[:3]):
                relevant_rules.append(rule)

        return relevant_rules


# 数据库表模型（如果需要持久化到数据库）
from sqlalchemy import Column, String, DateTime, Integer, Float, Text, JSON
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()


class UserDecisionProfileDB(Base):
    """用户决策偏好数据库表"""
    __tablename__ = "user_decision_profiles"

    id = Column(String, primary_key=True)
    user_id = Column(String, unique=True, nullable=False, index=True)

    # JSON 存储
    time_preference = Column(JSON, nullable=True)
    meeting_preference = Column(JSON, nullable=True)
    energy_profile = Column(JSON, nullable=True)
    conflict_resolution = Column(JSON, nullable=True)
    scenario_preferences = Column(JSON, nullable=True)
    explicit_rules = Column(JSON, nullable=True)
    confidence_scores = Column(JSON, nullable=True)

    created_at = Column(DateTime, nullable=False)
    updated_at = Column(DateTime, nullable=False)

    def to_profile(self) -> UserDecisionProfile:
        """转换为 Pydantic 模型"""
        return UserDecisionProfile(
            id=self.id,
            user_id=self.user_id,
            time_preference=TimePreference(**(self.time_preference or {})),
            meeting_preference=MeetingPreference(**(self.meeting_preference or {})),
            energy_profile=EnergyProfile(**(self.energy_profile or {})),
            conflict_resolution=ConflictResolution(**(self.conflict_resolution or {})),
            scenario_preferences=[
                ScenarioPreference(**p) for p in (self.scenario_preferences or [])
            ],
            explicit_rules=self.explicit_rules or [],
            confidence_scores=self.confidence_scores or {},
            created_at=self.created_at,
            updated_at=self.updated_at
        )

    @classmethod
    def from_profile(cls, profile: UserDecisionProfile) -> "UserDecisionProfileDB":
        """从 Pydantic 模型创建"""
        return cls(
            id=profile.id,
            user_id=profile.user_id,
            time_preference=profile.time_preference.model_dump(),
            meeting_preference=profile.meeting_preference.model_dump(),
            energy_profile=profile.energy_profile.model_dump(),
            conflict_resolution=profile.conflict_resolution.model_dump(),
            scenario_preferences=[p.model_dump() for p in profile.scenario_preferences],
            explicit_rules=profile.explicit_rules,
            confidence_scores=profile.confidence_scores,
            created_at=profile.created_at,
            updated_at=profile.updated_at
        )
