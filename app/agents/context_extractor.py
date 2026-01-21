"""
Context Extractor Agent - 用户画像推测专家
通过观察事件学习用户画像，而不是主动询问
"""
from typing import Dict, Any, List, Optional
from datetime import datetime
from app.models.event import ExtractedPoint
from app.services.llm import llm_service


class ContextExtractorAgent:
    """用户画像推测 Agent"""

    # 提取类型定义
    EXTRACTION_TYPES = {
        "relationship": "关系状态（单身/约会中/已婚等）",
        "identity": "用户身份（职业/行业/职位等）",
        "preference": "个人喜好（活动类型/社交倾向等）",
        "habit": "个人习惯（作息/工作方式等）"
    }

    def __init__(self):
        self.name = "context_extractor_agent"
        self.llm = llm_service

    async def extract(
        self,
        event_data: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        从事件中提取用户画像信息

        Args:
            event_data: 事件数据
            context: 上下文信息（recent_events, conversation_history等）

        Returns:
            {
                "description": str,  # AI 生成的描述
                "extracted_points": List[ExtractedPoint]  # 提取的画像点
            }
        """
        # 构建 prompt
        prompt = self._build_extraction_prompt(event_data, context)

        # 调用 LLM
        messages = [{"role": "user", "content": prompt}]
        llm_response = await self.llm.chat_completion(
            messages=messages,
            temperature=0.3
        )
        response = llm_response.get("content", "")

        # 解析响应
        result = self._parse_extraction(response)

        return result

    def _build_extraction_prompt(
        self,
        event_data: Dict[str, Any],
        context: Optional[Dict[str, Any]]
    ) -> str:
        """构建提取 prompt"""

        title = event_data.get("title", "")
        description = event_data.get("description", "")
        start_time = event_data.get("start_time", "")
        duration = event_data.get("duration", "")

        # 构建事件信息
        event_info = f"""
事件标题：{title}
事件描述：{description or '无'}
时间：{start_time or '未指定'}
时长：{duration or '未指定'}
"""

        # 添加最近活动上下文
        recent_events_str = ""
        if context and "recent_events" in context:
            recent = context["recent_events"][:5]
            recent_events_str = "\n最近活动：\n" + "\n".join([
                f"- {evt.get('title', '')} ({evt.get('time', '')})"
                for evt in recent
            ])

        # 添加对话历史上下文
        conversation_str = ""
        if context and "conversation_history" in context:
            conv = context["conversation_history"][-3:]  # 最近3条
            conversation_str = "\n最近对话：\n" + "\n".join([
                f"{msg.get('role', '')}: {msg.get('content', '')[:50]}"
                for msg in conv
            ])

        # 添加已知用户画像（用于增量学习）
        known_profile_str = ""
        if context and "known_profile" in context:
            profile = context["known_profile"]
            known_profile_str = f"""
已知用户画像：
- 关系状态：{profile.get('relationship', '未知')}
- 职业：{profile.get('occupation', '未知')}
- 主要喜好：{profile.get('preferences', [])}
"""

        prompt = f"""你是用户画像推测专家。请分析以下事件，提取关于用户的线索。

事件信息：
{event_info}
{recent_events_str}
{conversation_str}
{known_profile_str}

请从以下四个类型中提取有价值的用户画像信息：

1. **关系状态 (relationship)**
   - 单身/约会中/已婚/复杂
   - 证据：关键词（约会、情人节、家庭活动）、社交模式

2. **用户身份 (identity)**
   - 职业（程序员/学生/设计师/教师等）
   - 行业（IT/教育/金融/医疗等）
   - 职位（初级/高级/管理等）
   - 证据：工作内容、工作时间、专业术语

3. **个人喜好 (preference)**
   - 活动类型偏好（运动/阅读/游戏/社交等）
   - 社交倾向（内向/外向/平衡）
   - 工作风格（深度工作/协作/灵活）
   - 证据：自由时间安排、活动选择

4. **个人习惯 (habit)**
   - 作息（早鸟/夜猫子）
   - 工作时间（朝九晚五/灵活/不规律）
   - 运动/饮食模式
   - 证据：固定时间段的活动、重复模式

【重要原则】
1. **只提取有明确证据的推测**，置信度要合理
2. **不要强行推测**，如果信息不足，该类型就不返回点
3. **优先考虑高频行为**，单次事件证据较弱
4. **注意隐私边界**，不推测过于私人的信息

请以JSON格式返回：
{{
    "description": "对这个事件的总体描述，说明用户为什么这样安排",
    "extracted_points": [
        {{
            "type": "relationship" | "identity" | "preference" | "habit",
            "content": "推测内容",
            "confidence": 0.0-1.0,
            "evidence": ["证据1", "证据2"]
        }}
    ]
}}

如果没有足够证据提取某个类型，就不要在 extracted_points 中包含该类型。
"""

        return prompt

    def _parse_extraction(self, response: str) -> Dict[str, Any]:
        """解析 LLM 响应"""
        import json

        try:
            # 提取 JSON
            if "```json" in response:
                json_str = response.split("```json")[1].split("```")[0].strip()
            elif "```" in response:
                json_str = response.split("```")[1].split("```")[0].strip()
            else:
                json_str = response.strip()

            data = json.loads(json_str)

            # 转换 extracted_points 为 ExtractedPoint 对象
            points = []
            for point_data in data.get("extracted_points", []):
                # 验证类型
                if point_data["type"] not in self.EXTRACTION_TYPES:
                    continue

                point = ExtractedPoint(
                    type=point_data["type"],
                    content=point_data["content"],
                    confidence=point_data["confidence"],
                    evidence=point_data.get("evidence", []),
                    created_at=datetime.utcnow(),
                    validated=False,
                    validation_count=0
                )
                points.append(point)

            return {
                "success": True,
                "description": data.get("description", ""),
                "extracted_points": points,
                "points_count": len(points)
            }

        except Exception as e:
            print(f"[Context Extractor] Failed to parse response: {e}")
            return {
                "success": False,
                "description": "",
                "extracted_points": [],
                "error": str(e)
            }

    async def batch_extract(
        self,
        events: List[Dict[str, Any]],
        context: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """批量提取"""
        import asyncio

        async def _batch():
            tasks = [self.extract(event, context) for event in events]
            return await asyncio.gather(*tasks)

        return asyncio.run(_batch())


# 全局实例
context_extractor_agent = ContextExtractorAgent()
