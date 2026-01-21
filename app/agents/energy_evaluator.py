"""
Energy Evaluator Agent - 精力消耗评估专家
评估事件在体力和精神两个维度的消耗程度
"""
from typing import Dict, Any, Optional
from datetime import datetime
from app.models.event import EnergyConsumption, EnergyDimension
from app.services.llm import llm_service


class EnergyEvaluatorAgent:
    """精力消耗评估 Agent"""

    def __init__(self):
        self.name = "energy_evaluator_agent"
        self.llm = llm_service

    async def evaluate(
        self,
        event_data: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None
    ) -> EnergyConsumption:
        """
        评估事件的精力消耗

        Args:
            event_data: 事件数据（title, description, duration, location等）
            context: 上下文信息（user_profile, recent_events, time_of_day等）

        Returns:
            EnergyConsumption 对象
        """
        # 构建评估 prompt
        prompt = self._build_evaluation_prompt(event_data, context)

        # 调用 LLM
        messages = [{"role": "user", "content": prompt}]
        llm_response = await self.llm.chat_completion(
            messages=messages,
            temperature=0.3
        )

        # 获取内容
        response = llm_response.get("content", "")

        # 解析响应
        evaluation = self._parse_evaluation(response)

        return evaluation

    def _build_evaluation_prompt(
        self,
        event_data: Dict[str, Any],
        context: Optional[Dict[str, Any]]
    ) -> str:
        """构建评估 prompt"""

        event_title = event_data.get("title", "")
        event_description = event_data.get("description", "")
        event_duration = event_data.get("duration", "未指定")
        event_location = event_data.get("location", "未指定")

        # 获取用户画像信息（如果有）
        user_profile_str = ""
        if context and "user_profile" in context:
            user_profile = context["user_profile"]
            user_profile_str = f"""
用户画像信息：
- 职业：{user_profile.get('occupation', '未知')}
- 工作性质：{user_profile.get('work_style', '未知')}
- 精力特点：{user_profile.get('energy_pattern', '未知')}
"""

        # 获取最近活动（如果有）
        recent_events_str = ""
        if context and "recent_events" in context:
            recent_events = context["recent_events"]
            recent_events_str = "\n".join([
                f"- {evt.get('title', '')} ({evt.get('time', '')})"
                for evt in recent_events[:5]
            ])
            if recent_events_str:
                recent_events_str = f"最近活动：\n{recent_events_str}"

        prompt = f"""你是精力消耗评估专家。请分析以下事件的体力消耗和精神消耗程度。

事件信息：
标题：{event_title}
描述：{event_description}
时长：{event_duration}
地点：{event_location}

{user_profile_str}

{recent_events_str}

请按照以下标准评估：

【体力消耗评估标准】
- Low (0-3分): 久坐、轻微移动（如：开会、写代码、听课）
- Medium (4-6分): 轻度活动、走动（如：购物、短途出行、家务）
- High (7-10分): 重度活动、运动、长时间站立（如：健身、搬运、登山、长时间站立工作）

【精神消耗评估标准】
- Low (0-3分): 机械操作、重复性工作（如：整理文件、数据录入）
- Medium (4-6分): 需要专注和思考（如：学习、普通工作、阅读）
- High (7-10分): 深度思考、创造性工作、高压决策（如：编程、设计、重要会议）

请以JSON格式返回评估结果：
{{
    "physical": {{
        "level": "low" | "medium" | "high",
        "score": 0-10的整数,
        "description": "自然语言描述为什么是这个级别",
        "factors": ["具体因素1", "具体因素2"]
    }},
    "mental": {{
        "level": "low" | "medium" | "high",
        "score": 0-10的整数,
        "description": "自然语言描述为什么是这个级别",
        "factors": ["具体因素1", "具体因素2"]
    }}
}}

注意：
1. 如果信息不足，根据事件标题进行合理推测
2. description 要具体说明判断依据
3. factors 列出2-4个关键影响因素
4. 评分要准确反映实际消耗程度
"""

        return prompt

    def _parse_evaluation(self, response: str) -> EnergyConsumption:
        """解析 LLM 响应为 EnergyConsumption 对象"""
        import json

        try:
            # 尝试提取 JSON
            if "```json" in response:
                json_str = response.split("```json")[1].split("```")[0].strip()
            elif "```" in response:
                json_str = response.split("```")[1].split("```")[0].strip()
            else:
                json_str = response.strip()

            data = json.loads(json_str)

            # 构建 EnergyConsumption
            physical = EnergyDimension(**data["physical"])
            mental = EnergyDimension(**data["mental"])

            return EnergyConsumption(
                physical=physical,
                mental=mental,
                evaluated_at=datetime.utcnow(),
                evaluated_by=self.name
            )

        except Exception as e:
            # 解析失败时返回默认值
            print(f"[Energy Evaluator] Failed to parse response: {e}")
            return EnergyConsumption(
                physical=EnergyDimension(
                    level="medium",
                    score=5,
                    description="无法准确评估，使用默认值",
                    factors=[]
                ),
                mental=EnergyDimension(
                    level="medium",
                    score=5,
                    description="无法准确评估，使用默认值",
                    factors=[]
                ),
                evaluated_at=datetime.utcnow(),
                evaluated_by=self.name + "_fallback"
            )

    def batch_evaluate(
        self,
        events: list[Dict[str, Any]],
        context: Optional[Dict[str, Any]] = None
    ) -> list[EnergyConsumption]:
        """
        批量评估多个事件

        Args:
            events: 事件列表
            context: 共享的上下文信息

        Returns:
            评估结果列表
        """
        import asyncio

        async def _batch():
            tasks = [
                self.evaluate(event, context)
                for event in events
            ]
            return await asyncio.gather(*tasks)

        return asyncio.run(_batch())


# 全局实例
energy_evaluator_agent = EnergyEvaluatorAgent()
