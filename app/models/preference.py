"""
User Preference Model - 用户偏好学习模型
用于记录和分析用户的决策模式，实现智能预测
"""
from sqlalchemy import Column, String, Integer, Float, DateTime, JSON, Text
from sqlalchemy.orm import declarative_base
from datetime import datetime
import uuid
from typing import Dict, Any, List, Optional

Base = declarative_base()


class UserPreference(Base):
    """用户偏好记录"""
    __tablename__ = "user_preferences"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String, index=True, nullable=False)

    # 场景信息
    scenario_type = Column(String, nullable=False)  # 场景类型：time_conflict, event_cancellation, etc.
    context = Column(JSON)  # 上下文信息（事件类型、时间段等）

    # 用户选择
    decision = Column(String, nullable=False)  # 用户做出的选择
    decision_type = Column(String)  # 决策类型：merge, cancel, reschedule, etc.

    # 元数据
    created_at = Column(DateTime, default=datetime.utcnow)
    weight = Column(Float, default=1.0)  # 权重（可以随时间衰减）

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "user_id": self.user_id,
            "scenario_type": self.scenario_type,
            "context": self.context,
            "decision": self.decision,
            "decision_type": self.decision_type,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "weight": self.weight
        }


class PreferenceAnalyzer:
    """偏好分析器 - 分析用户决策模式"""

    @staticmethod
    def analyze_scenario(
        history: List[UserPreference],
        scenario_type: str,
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        分析特定场景下的用户偏好

        Returns:
            {
                "predictions": [
                    {"option": "merge", "probability": 0.75, "confidence": "high"},
                    {"option": "cancel", "probability": 0.15, "confidence": "low"},
                    ...
                ],
                "recommended_action": "merge",  # 如果某个选项 > 50%
                "confidence": 75,  # 推荐的置信度
                "sample_size": 12  # 样本数量
            }
        """
        # 过滤相同场景的历史记录
        scenario_history = [
            h for h in history
            if h.scenario_type == scenario_type
        ]

        if not scenario_history:
            return {
                "predictions": [],
                "recommended_action": None,
                "confidence": 0,
                "sample_size": 0,
                "reason": "no_history"
            }

        # 统计各种决策的频率
        decision_counts = {}
        total_weight = 0

        for record in scenario_history:
            decision = record.decision
            weight = record.weight or 1.0
            decision_counts[decision] = decision_counts.get(decision, 0) + weight
            total_weight += weight

        # 计算概率
        predictions = []
        for decision, count in decision_counts.items():
            probability = count / total_weight if total_weight > 0 else 0

            # 确定置信度
            if probability >= 0.7:
                confidence = "high"
            elif probability >= 0.4:
                confidence = "medium"
            else:
                confidence = "low"

            predictions.append({
                "option": decision,
                "probability": round(probability * 100, 1),
                "confidence": confidence
            })

        # 按概率排序
        predictions.sort(key=lambda x: x["probability"], reverse=True)

        # 推荐操作（概率 > 50%）
        recommended = None
        max_confidence = 0
        if predictions:
            top = predictions[0]
            if top["probability"] > 50:
                recommended = top["option"]
                max_confidence = top["probability"]

        return {
            "predictions": predictions,
            "recommended_action": recommended,
            "confidence": max_confidence,
            "sample_size": len(scenario_history)
        }

    @staticmethod
    def calculate_context_similarity(
        context1: Dict[str, Any],
        context2: Dict[str, Any]
    ) -> float:
        """
        计算两个上下文的相似度（0-1）

        考虑因素：
        - 事件类型相似性
        - 时间段相似性
        - 其他上下文因素
        """
        score = 0.0
        factors = 0

        # 事件类型
        if "event_type" in context1 and "event_type" in context2:
            factors += 1
            if context1["event_type"] == context2["event_type"]:
                score += 1.0

        # 时间段
        if "time_period" in context1 and "time_period" in context2:
            factors += 1
            if context1["time_period"] == context2["time_period"]:
                score += 1.0

        # 能量需求
        if "energy_level" in context1 and "energy_level" in context2:
            factors += 1
            if context1["energy_level"] == context2["energy_level"]:
                score += 0.5

        return score / factors if factors > 0 else 0.0
