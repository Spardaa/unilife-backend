"""
User Decision Profile Model - 用户决策偏好模型 (简化版)
存储用户在不同场景下的决策模式，用于 Executor 智能决策
"""
from typing import Dict, Any, List, Optional
from datetime import datetime
from pydantic import BaseModel, Field
import uuid


class UserDecisionProfile(BaseModel):
    """
    用户决策偏好（简化版）

    核心功能：
    - 冲突解决策略
    - 显式规则列表
    - 场景偏好统计
    """
    # Primary key
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))

    # User reference
    user_id: str

    # 核心决策偏好
    conflict_strategy: str = Field(
        default="ask",
        description="冲突策略: ask（询问）| prioritize_urgent | merge"
    )

    # 显式规则（用户直接告诉我们的规则）
    explicit_rules: List[str] = Field(default_factory=list)

    # 场景偏好统计（从历史决策中学习）
    # 格式: {"scenario_type": {"action": "merge", "confidence": 0.8, "count": 5}}
    scenario_stats: Dict[str, Dict[str, Any]] = Field(default_factory=dict)

    # 元数据
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    class Config:
        json_schema_extra = {
            "example": {
                "user_id": "user-123",
                "conflict_strategy": "merge",
                "explicit_rules": [
                    "周五晚上不安排工作",
                    "早上9点前不开会"
                ],
                "scenario_stats": {
                    "time_conflict": {
                        "action": "merge",
                        "confidence": 0.8,
                        "count": 12
                    }
                }
            }
        }

    def to_dict(self) -> dict:
        """转换为字典（用于数据库存储）"""
        return self.model_dump(mode='json')

    @classmethod
    def from_dict(cls, data: dict) -> "UserDecisionProfile":
        """从字典创建（兼容旧格式）"""
        # 兼容旧格式迁移
        if "time_preference" in data or "meeting_preference" in data:
            conflict = data.get("conflict_resolution", {})
            return cls(
                user_id=data.get("user_id", ""),
                conflict_strategy=conflict.get("strategy", "ask") if isinstance(conflict, dict) else "ask",
                explicit_rules=data.get("explicit_rules", []),
                scenario_stats={}
            )
        return cls(**data)

    def get_scenario_preference(self, scenario_type: str) -> Optional[Dict[str, Any]]:
        """获取特定场景的偏好"""
        return self.scenario_stats.get(scenario_type)

    def update_scenario(
        self,
        scenario_type: str,
        action: str,
        confidence: float = 0.5
    ) -> None:
        """记录场景决策，更新统计"""
        existing = self.scenario_stats.get(scenario_type)

        if existing:
            # 加权平均更新置信度
            old_conf = existing.get("confidence", 0.5)
            new_conf = old_conf * 0.7 + confidence * 0.3
            existing["confidence"] = round(new_conf, 2)
            existing["count"] = existing.get("count", 0) + 1
            # 如果新行动置信度更高，更新首选行动
            if confidence > old_conf * 0.9:
                existing["action"] = action
        else:
            self.scenario_stats[scenario_type] = {
                "action": action,
                "confidence": confidence,
                "count": 1
            }

        self.updated_at = datetime.utcnow()

    def add_explicit_rule(self, rule: str) -> None:
        """添加显式规则"""
        if rule and rule not in self.explicit_rules:
            self.explicit_rules.append(rule)
            self.updated_at = datetime.utcnow()

    def remove_explicit_rule(self, rule: str) -> bool:
        """移除显式规则"""
        if rule in self.explicit_rules:
            self.explicit_rules.remove(rule)
            self.updated_at = datetime.utcnow()
            return True
        return False

    def get_summary_for_executor(self) -> Dict[str, Any]:
        """获取精简摘要（用于注入 Executor Agent）"""
        return {
            "conflict_strategy": self.conflict_strategy,
            "explicit_rules": self.explicit_rules[:5],  # 最多5条
            "top_scenarios": {
                k: v["action"]
                for k, v in sorted(
                    self.scenario_stats.items(),
                    key=lambda x: x[1].get("confidence", 0),
                    reverse=True
                )[:3]  # 最多3个高置信度场景
            }
        }
