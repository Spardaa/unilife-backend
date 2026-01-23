"""
Daily Diary Generator Agent - 每日观察日记生成器
汇总用户一天的对话，生成观察日记
"""
from typing import Dict, Any, List, Optional
from datetime import datetime, date
import json

from app.services.llm import llm_service
from app.services.prompt import prompt_service
from app.services.diary_service import diary_service
from app.models.diary import UserDiary, KeyInsights, ExtractedSignal


class DailyDiaryGeneratorAgent:
    """每日观察日记生成 Agent"""

    def __init__(self):
        self.name = "daily_diary_generator"
        self.llm = llm_service

    async def generate_daily_diary(
        self,
        user_id: str,
        target_date: date
    ) -> Dict[str, Any]:
        """
        为指定日期生成日记

        Args:
            user_id: 用户ID
            target_date: 目标日期

        Returns:
            {
                "success": bool,
                "diary": UserDiary,
                "skipped": bool,
                "reason": str
            }
        """
        # 检查日记是否已存在
        if diary_service.diary_exists(user_id, target_date):
            return {
                "success": True,
                "skipped": True,
                "reason": "Diary already exists for this date",
                "diary": diary_service.get_diary_by_date(user_id, target_date)
            }

        # 获取当天的所有对话
        conversations = diary_service.get_conversations_for_date(user_id, target_date)

        if not conversations:
            return {
                "success": False,
                "skipped": True,
                "reason": "No conversations found for this date",
                "diary": None
            }

        # 统计数据
        conversation_count = len(conversations)
        message_count = sum(conv.get("message_count", 0) for conv in conversations)
        tool_calls_count = sum(conv.get("tool_calls_count", 0) for conv in conversations)

        # 构建 prompt
        prompt = self._build_generation_prompt(
            target_date=target_date,
            conversations=conversations,
            conversation_count=conversation_count,
            message_count=message_count,
            tool_calls_count=tool_calls_count
        )

        # 调用 LLM 生成日记
        messages = [{"role": "user", "content": prompt}]
        llm_response = await self.llm.chat_completion(
            messages=messages,
            temperature=0.5
        )
        response = llm_response.get("content", "")

        # 解析响应
        result = self._parse_diary_response(response)

        if not result.get("success"):
            return {
                "success": False,
                "skipped": False,
                "reason": result.get("error", "Failed to parse LLM response"),
                "diary": None
            }

        # 创建并保存日记
        try:
            diary = diary_service.create_daily_diary(
                user_id=user_id,
                diary_date=target_date,
                summary=result["summary"],
                key_insights=result["key_insights"],
                extracted_signals=result["extracted_signals"],
                conversation_count=conversation_count,
                message_count=message_count,
                tool_calls_count=tool_calls_count
            )

            return {
                "success": True,
                "skipped": False,
                "diary": diary
            }

        except Exception as e:
            return {
                "success": False,
                "skipped": False,
                "reason": f"Failed to save diary: {str(e)}",
                "diary": None
            }

    def _build_generation_prompt(
        self,
        target_date: date,
        conversations: List[Dict[str, Any]],
        conversation_count: int,
        message_count: int,
        tool_calls_count: int
    ) -> str:
        """构建日记生成 prompt"""

        # 构建对话摘要
        conversations_summary = self._build_conversations_summary(conversations)

        # 构建工具调用摘要
        tool_calls_summary = self._build_tool_calls_summary(conversations)

        # 尝试加载 prompt 文件
        try:
            base_prompt = prompt_service.load_prompt("daily_diary_generator")
            return base_prompt.format(
                date=target_date.isoformat(),
                conversation_count=conversation_count,
                message_count=message_count,
                tool_calls_count=tool_calls_count,
                conversations_summary=conversations_summary,
                tool_calls_summary=tool_calls_summary
            )
        except:
            # 使用默认 prompt
            return self._get_default_prompt(
                target_date, conversation_count, message_count, tool_calls_count,
                conversations_summary, tool_calls_summary
            )

    def _build_conversations_summary(self, conversations: List[Dict[str, Any]]) -> str:
        """构建对话摘要"""
        if not conversations:
            return "无对话记录"

        summary_parts = []

        for i, conv in enumerate(conversations, 1):
            conv_title = conv.get("title") or f"对话 #{conv['id'][:8]}"
            conv_time = conv.get("created_at", "")[:16] if conv.get("created_at") else ""

            # 提取用户消息摘要
            user_messages = []
            for msg in conv.get("messages", []):
                if msg.get("role") == "user" and msg.get("content"):
                    # 只取前100字
                    content = msg["content"][:100]
                    if len(msg["content"]) > 100:
                        content += "..."
                    user_messages.append(content)

            if user_messages:
                messages_preview = " | ".join(user_messages[:3])
                summary_parts.append(f"{i}. [{conv_time}] {conv_title}: {messages_preview}")

        return "\n".join(summary_parts)

    def _build_tool_calls_summary(self, conversations: List[Dict[str, Any]]) -> str:
        """构建工具调用摘要"""
        tool_actions = []

        for conv in conversations:
            for msg in conv.get("messages", []):
                if msg.get("tool_calls"):
                    try:
                        tool_calls_data = json.loads(msg["tool_calls"])
                        for tool_call in tool_calls_data:
                            func_name = tool_call.get("function", {}).get("name", "unknown")
                            tool_actions.append(func_name)
                    except:
                        pass

        if not tool_actions:
            return "无工具调用"

        # 统计工具调用频率
        from collections import Counter
        tool_counts = Counter(tool_actions)

        summary_parts = []
        for tool, count in tool_counts.most_common():
            summary_parts.append(f"- {tool}: {count}次")

        return "\n".join(summary_parts)

    def _get_default_prompt(
        self,
        target_date: date,
        conversation_count: int,
        message_count: int,
        tool_calls_count: int,
        conversations_summary: str,
        tool_calls_summary: str
    ) -> str:
        """默认 prompt（备用）"""
        return f"""你是用户观察日记专家。请汇总分析用户在 {target_date.isoformat()} 的所有对话，生成一条观察日记。

## 当天对话汇总

对话数量：{conversation_count}
消息数量：{message_count}
工具调用次数：{tool_calls_count}

## 对话内容摘要
{conversations_summary}

## 工具调用记录
{tool_calls_summary}

## 你的任务

请生成一份简洁的观察日记，包含：

1. **总体摘要**（3-5句话）：
   - 用户今天主要做了什么
   - 露了什么偏好或习惯
   - 有什么值得记住的行为模式

2. **关键洞察**：
   - 活动类型（工作/学习/运动/社交等）
   - 时间偏好（早上/下午/晚上/深夜）
   - 情绪状态（如果有明显表现）
   - 决策倾向（果断/犹豫/依赖AI建议等）

3. **结构化信号**：
   - 从对话中提取的行为信号
   - 每个信号标注置信度

## 输出格式（JSON）

{{
    "summary": "用户今天主要是...",
    "key_insights": {{
        "activities": ["工作", "健身"],
        "emotions": ["专注", "高效"],
        "patterns": ["上午工作效率高"],
        "time_preference": "morning",
        "decision_style": "decisive"
    }},
    "extracted_signals": [
        {{"type": "habit", "value": "早起", "confidence": 0.9, "evidence": "早上8点就开始安排任务"}},
        {{"type": "preference", "value": "健康意识强", "confidence": 0.8, "evidence": "安排了健身计划"}}
    ]
}}

请严格遵循JSON格式，确保所有字段都正确填写。
"""

    def _parse_diary_response(self, response: str) -> Dict[str, Any]:
        """解析 LLM 响应"""
        try:
            # 提取 JSON
            if "```json" in response:
                json_str = response.split("```json")[1].split("```")[0].strip()
            elif "```" in response:
                json_str = response.split("```")[1].split("```")[0].strip()
            else:
                json_str = response.strip()

            data = json.loads(json_str)

            # 验证必要字段
            if "summary" not in data:
                raise ValueError("Missing 'summary' field")

            # 构建 key_insights
            key_insights_data = data.get("key_insights", {})
            key_insights = KeyInsights(
                activities=key_insights_data.get("activities", []),
                emotions=key_insights_data.get("emotions", []),
                patterns=key_insights_data.get("patterns", []),
                time_preference=key_insights_data.get("time_preference", "unknown"),
                decision_style=key_insights_data.get("decision_style", "unknown")
            )

            # 构建 extracted_signals
            extracted_signals = []
            for signal_data in data.get("extracted_signals", []):
                signal = ExtractedSignal(
                    type=signal_data.get("type", "unknown"),
                    value=signal_data.get("value", ""),
                    confidence=signal_data.get("confidence", 0.5),
                    evidence=signal_data.get("evidence", "")
                )
                extracted_signals.append(signal)

            return {
                "success": True,
                "summary": data["summary"],
                "key_insights": key_insights.model_dump(),
                "extracted_signals": [s.model_dump() for s in extracted_signals]
            }

        except Exception as e:
            print(f"[Daily Diary Generator] Failed to parse response: {e}")
            print(f"[Daily Diary Generator] Response: {response[:500]}")
            return {
                "success": False,
                "error": str(e)
            }

    async def generate_missing_diaries(
        self,
        user_id: str,
        start_date: date,
        end_date: date
    ) -> List[Dict[str, Any]]:
        """
        批量生成缺失的日记

        Args:
            user_id: 用户ID
            start_date: 开始日期
            end_date: 结束日期

        Returns:
            生成结果列表
        """
        import asyncio

        results = []

        # 计算日期范围
        current = start_date
        while current <= end_date:
            # 检查是否已存在
            if not diary_service.diary_exists(user_id, current):
                result = await self.generate_daily_diary(user_id, current)
                results.append({
                    "date": current.isoformat(),
                    "result": result
                })

            current = current.next_day() if hasattr(current, 'next_day') else date.fromordinal(current.toordinal() + 1)

        return results


# 全局实例
daily_diary_generator = DailyDiaryGeneratorAgent()
