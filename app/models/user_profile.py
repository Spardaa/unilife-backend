"""
User Profile Model - 用户画像模型
存储从事件中学习到的用户信息
"""
from typing import Dict, Any, List, Optional
from datetime import datetime
from pydantic import BaseModel, Field
import uuid

from app.models.event import ExtractedPoint


class RelationshipProfile(BaseModel):
    """关系状态画像"""
    status: str = Field(default="unknown", description="single | dating | married | complicated | unknown")
    confidence: float = Field(default=0.0, ge=0, le=1, description="置信度")
    evidence_count: int = Field(default=0, description="支持证据数量")
    recent_evidence: List[str] = Field(default_factory=list, description="最近的证据")


class IdentityProfile(BaseModel):
    """用户身份画像"""
    occupation: str = Field(default="unknown", description="职业")
    industry: str = Field(default="unknown", description="行业")
    position: str = Field(default="unknown", description="职位级别")
    confidence: float = Field(default=0.0, ge=0, le=1, description="置信度")
    evidence_count: int = Field(default=0, description="支持证据数量")


class PreferenceProfile(BaseModel):
    """个人喜好画像"""
    activity_types: List[str] = Field(default_factory=list, description="喜欢的活动类型")
    social_preference: str = Field(default="unknown", description="introverted | extroverted | balanced | unknown")
    work_style: str = Field(default="unknown", description="deep_work | collaborative | flexible | unknown")
    stress_coping: str = Field(default="unknown", description="如何应对压力")


class HabitProfile(BaseModel):
    """个人习惯画像"""
    sleep_schedule: str = Field(default="unknown", description="early_bird | night_owl | irregular | unknown")
    work_hours: str = Field(default="unknown", description="9-5 | flexible | irregular | unknown")
    exercise_frequency: str = Field(default="unknown", description="daily | weekly | rarely | unknown")
    meal_patterns: List[str] = Field(default_factory=list, description="饮食模式")


class UserProfile(BaseModel):
    """用户画像（汇总）"""

    # Primary key
    id: str = Field(default_factory=lambda: str(uuid.uuid4()), description="Profile ID")

    # User reference
    user_id: str = Field(..., description="User ID")

    # 四大画像类型
    relationships: RelationshipProfile = Field(default_factory=RelationshipProfile)
    identity: IdentityProfile = Field(default_factory=IdentityProfile)
    preferences: PreferenceProfile = Field(default_factory=PreferenceProfile)
    habits: HabitProfile = Field(default_factory=HabitProfile)

    # Metadata
    created_at: datetime = Field(default_factory=datetime.utcnow, description="创建时间")
    updated_at: datetime = Field(default_factory=datetime.utcnow, description="更新时间")
    total_points: int = Field(default=0, description="累计提取的点数")

    class Config:
        json_schema_extra = {
            "example": {
                "user_id": "user-123",
                "relationships": {
                    "status": "dating",
                    "confidence": 0.8,
                    "evidence_count": 5,
                    "recent_evidence": ["约会", "情人节礼物"]
                },
                "identity": {
                    "occupation": "程序员",
                    "industry": "IT",
                    "position": "senior",
                    "confidence": 0.9
                },
                "preferences": {
                    "activity_types": ["编程", "阅读", "游戏"],
                    "social_preference": "introverted",
                    "work_style": "deep_work"
                },
                "habits": {
                    "sleep_schedule": "night_owl",
                    "work_hours": "flexible",
                    "exercise_frequency": "weekly"
                }
            }
        }

    def to_dict(self) -> dict:
        """转换为字典（用于数据库存储）"""
        return self.model_dump(mode='json')

    @classmethod
    def from_dict(cls, data: dict) -> "UserProfile":
        """从字典创建"""
        return cls(**data)

    def update_from_points(self, points: List[Dict[str, Any]]):
        """从提取的画像点更新"""
        from app.models.event import ExtractedPoint

        for point_data in points:
            point = ExtractedPoint(**point_data)
            point_type = point.type

            # 根据类型更新相应字段
            if point_type == "relationship":
                self._update_relationship(point)
            elif point_type == "identity":
                self._update_identity(point)
            elif point_type == "preference":
                self._update_preferences(point)
            elif point_type == "habit":
                self._update_habits(point)

            self.total_points += 1

        self.updated_at = datetime.utcnow()

    def _update_relationship(self, point: ExtractedPoint):
        """更新关系状态"""
        # 简单策略：如果新点置信度更高，覆盖；否则累积证据
        if point.confidence > self.relationships.confidence:
            self.relationships.confidence = point.confidence
            # 从 content 提取 status
            content_lower = point.content.lower()
            if "单身" in content_lower or "single" in content_lower:
                self.relationships.status = "single"
            elif "约会" in content_lower or "dating" in content_lower or "恋人" in content_lower:
                self.relationships.status = "dating"
            elif "已婚" in content_lower or "结婚" in content_lower:
                self.relationships.status = "married"

        self.relationships.evidence_count += 1
        for evidence in point.evidence:
            if evidence not in self.relationships.recent_evidence:
                self.relationships.recent_evidence.insert(0, evidence)
                if len(self.relationships.recent_evidence) > 10:
                    self.relationships.recent_evidence.pop()

    def _update_identity(self, point: ExtractedPoint):
        """更新用户身份"""
        if point.confidence > self.identity.confidence:
            self.identity.confidence = point.confidence

        # 从 content 提取信息
        content = point.content
        if "程序员" in content or "编程" in content or "代码" in content:
            self.identity.occupation = "程序员"
            self.identity.industry = "IT"
        elif "学生" in content:
            self.identity.occupation = "学生"
        # ... 更多职业识别

        self.identity.evidence_count += 1

    def _update_preferences(self, point: ExtractedPoint):
        """更新个人喜好"""
        # 从 content 提取活动类型
        for activity in ["运动", "阅读", "游戏", "音乐", "电影", "旅行", "美食", "健身"]:
            if activity in point.content and activity not in self.preferences.activity_types:
                self.preferences.activity_types.append(activity)

        # 社交倾向
        if "内向" in point.content or "独处" in point.content:
            self.preferences.social_preference = "introverted"
        elif "外向" in point.content or "社交" in point.content:
            self.preferences.social_preference = "extroverted"

    def _update_habits(self, point: ExtractedPoint):
        """更新个人习惯"""
        content = point.content

        if "早起" in content or "早" in content:
            self.habits.sleep_schedule = "early_bird"
        elif "晚" in content or "夜" in content:
            self.habits.sleep_schedule = "night_owl"

        if "每天" in content:
            if "运动" in content or "锻炼" in content:
                self.habits.exercise_frequency = "daily"
        elif "每周" in content:
            if "运动" in content or "锻炼" in content:
                self.habits.exercise_frequency = "weekly"
