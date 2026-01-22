"""
Duration Estimator Agent - 时长估计专家
基于历史数据和事件特征智能估计事件时长
"""
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
from pydantic import BaseModel, Field
from app.services.llm import llm_service


class DurationEstimate(BaseModel):
    """时长估计结果"""
    duration: int = Field(..., description="估计时长（分钟）")
    confidence: float = Field(..., ge=0.0, le=1.0, description="置信度 (0.0-1.0)")
    source: str = Field(default="ai_estimate", description="来源：ai_estimate, default")
    similar_events: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="参考的相似事件"
    )
    reasoning: Optional[str] = Field(None, description="估计的推理过程")


class DurationEstimatorAgent:
    """时长估计 Agent"""

    # 默认时长（分钟）
    DEFAULT_DURATIONS = {
        "会议": 60,
        "开会": 60,
        "健身": 90,
        "运动": 60,
        "学习": 90,
        "工作": 120,
        "写代码": 120,
        "午餐": 60,
        "晚餐": 90,
        "约会": 120,
        "电影": 120,
        "购物": 90,
        "通勤": 30,
        "洗澡": 30,
        "阅读": 60,
    }

    def __init__(self):
        self.name = "duration_estimator_agent"
        self.llm = llm_service

    async def estimate(
        self,
        event_title: str,
        event_description: Optional[str] = None,
        user_id: Optional[str] = None,
        recent_events: Optional[List[Dict[str, Any]]] = None,
        use_llm: bool = True
    ) -> DurationEstimate:
        """
        估计事件时长

        Args:
            event_title: 事件标题
            event_description: 事件描述
            user_id: 用户ID（用于查询历史数据）
            recent_events: 用户最近的事件（用于学习）
            use_llm: 是否使用LLM进行智能估计

        Returns:
            DurationEstimate 对象
        """

        # 1. 尝试从历史数据中学习
        historical_estimate = await self._estimate_from_history(
            event_title,
            event_description,
            recent_events
        )

        if historical_estimate and historical_estimate["confidence"] >= 0.7:
            # 历史数据置信度高，直接使用
            return DurationEstimate(
                duration=historical_estimate["duration"],
                confidence=historical_estimate["confidence"],
                source="ai_estimate",
                similar_events=historical_estimate.get("similar_events", []),
                reasoning=historical_estimate.get("reasoning")
            )

        # 2. 尝试从关键词匹配默认值
        default_estimate = self._estimate_from_defaults(event_title)
        if default_estimate:
            return DurationEstimate(
                duration=default_estimate["duration"],
                confidence=0.5,  # 默认值置信度较低
                source="default",
                similar_events=[],
                reasoning=f"匹配到默认值：{default_estimate['matched_keyword']}"
            )

        # 3. 使用LLM进行智能估计
        if use_llm:
            llm_estimate = await self._estimate_from_llm(
                event_title,
                event_description,
                recent_events
            )
            return llm_estimate

        # 4. 兜底：使用全局默认值
        return DurationEstimate(
            duration=60,
            confidence=0.3,
            source="default",
            similar_events=[],
            reasoning="使用全局默认值60分钟"
        )

    async def _estimate_from_history(
        self,
        event_title: str,
        event_description: Optional[str],
        recent_events: Optional[List[Dict[str, Any]]]
    ) -> Optional[Dict[str, Any]]:
        """从历史事件中估计时长"""
        if not recent_events:
            return None

        # 查找相似事件
        similar_events = []
        for event in recent_events:
            # 检查是否有实际时长记录
            if event.get("duration_actual"):
                # 标题相似度检查
                if self._is_similar_event(event_title, event.get("title", "")):
                    similar_events.append(event)

        if not similar_events:
            return None

        # 计算平均时长
        total_duration = sum(e["duration_actual"] for e in similar_events)
        avg_duration = int(total_duration / len(similar_events))

        # 计算方差（置信度依据）
        if len(similar_events) >= 3:
            variance = sum((e["duration_actual"] - avg_duration) ** 2 for e in similar_events)
            std_dev = (variance / len(similar_events)) ** 0.5
            # 标准差越小，置信度越高
            confidence = max(0.0, 1.0 - (std_dev / avg_duration))
        else:
            # 样本少，置信度较低
            confidence = 0.6

        return {
            "duration": avg_duration,
            "confidence": confidence,
            "similar_events": similar_events[:3],  # 返回最多3个参考事件
            "reasoning": f"基于{len(similar_events)}个相似历史事件，平均时长{avg_duration}分钟"
        }

    def _estimate_from_defaults(self, event_title: str) -> Optional[Dict[str, Any]]:
        """从预设默认值中匹配"""
        for keyword, duration in self.DEFAULT_DURATIONS.items():
            if keyword in event_title:
                return {
                    "duration": duration,
                    "matched_keyword": keyword
                }
        return None

    async def _estimate_from_llm(
        self,
        event_title: str,
        event_description: Optional[str],
        recent_events: Optional[List[Dict[str, Any]]]
    ) -> DurationEstimate:
        """使用LLM进行智能估计"""

        # 构建上下文
        context_parts = [f"事件标题：{event_title}"]

        if event_description:
            context_parts.append(f"事件描述：{event_description}")

        # 添加最近事件作为参考
        if recent_events:
            recent_with_actual = [
                e for e in recent_events[-5:]
                if e.get("duration_actual")
            ]
            if recent_with_actual:
                context_parts.append("\n最近类似事件的实际时长：")
                for e in recent_with_actual[:3]:
                    context_parts.append(
                        f"- {e.get('title', '')}: {e['duration_actual']}分钟"
                    )

        context = "\n".join(context_parts)

        prompt = f"""你是时长估计专家。请根据以下信息估计事件的可能时长。

{context}

请考虑：
1. 事件类型的特点
2. 常规情况下的时长
3. 如果有历史数据，参考历史数据

请以JSON格式返回：
{{
    "duration": 时长（分钟，整数）,
    "confidence": 置信度（0.0-1.0）,
    "reasoning": "估计的理由（简短说明）"
}}

注意：
- 时长应该是合理的整数（15, 30, 60, 90, 120等）
- 置信度应该反映你的确定程度
- 如果信息不足，使用保守估计（60分钟）并标注较低置信度
"""

        try:
            messages = [{"role": "user", "content": prompt}]
            llm_response = await self.llm.chat_completion(
                messages=messages,
                temperature=0.3
            )

            response = llm_response.get("content", "")

            # 解析JSON
            import json
            if "```json" in response:
                json_str = response.split("```json")[1].split("```")[0].strip()
            elif "```" in response:
                json_str = response.split("```")[1].split("```")[0].strip()
            else:
                json_str = response.strip()

            data = json.loads(json_str)

            return DurationEstimate(
                duration=data["duration"],
                confidence=data.get("confidence", 0.5),
                source="ai_estimate",
                similar_events=[],
                reasoning=data.get("reasoning", "LLM基于事件特征估计")
            )

        except Exception as e:
            print(f"[Duration Estimator] LLM估计失败: {e}")
            # 兜底
            return DurationEstimate(
                duration=60,
                confidence=0.3,
                source="default",
                similar_events=[],
                reasoning="LLM估计失败，使用默认值"
            )

    def _is_similar_event(self, title1: str, title2: str) -> bool:
        """判断两个事件标题是否相似"""
        # 简单判断：包含关键词
        # 例如："开会" 和 "团队会议" 相似
        keywords1 = set(title1)
        keywords2 = set(title2)

        # 计算交集比例
        intersection = keywords1 & keywords2
        if not intersection:
            return False

        # 如果有共同关键词，认为相似
        return len(intersection) >= 2

    async def learn_from_completion(
        self,
        event_id: str,
        event_title: str,
        estimated_duration: int,
        actual_duration: int,
        user_id: str
    ) -> Dict[str, Any]:
        """
        从事件完成中学习

        Args:
            event_id: 事件ID
            event_title: 事件标题
            estimated_duration: 估计时长
            actual_duration: 实际时长
            user_id: 用户ID

        Returns:
            学习结果统计
        """
        error = abs(actual_duration - estimated_duration)
        error_rate = error / estimated_duration if estimated_duration > 0 else 0

        # 记录学习数据（可以存储到数据库或文件）
        learning_data = {
            "event_id": event_id,
            "event_title": event_title,
            "estimated_duration": estimated_duration,
            "actual_duration": actual_duration,
            "error": error,
            "error_rate": error_rate,
            "timestamp": datetime.utcnow().isoformat(),
            "user_id": user_id
        }

        # TODO: 将学习数据持久化到数据库
        # 可以创建一个 duration_history 表来记录

        return learning_data


# 全局实例
duration_estimator_agent = DurationEstimatorAgent()
