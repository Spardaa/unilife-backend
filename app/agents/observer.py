"""
Observer Agent - 观察者 (简化版)
负责从用户行为中学习核心偏好
"""
from typing import Dict, Any, Optional, List
from datetime import datetime
import json

from app.services.llm import llm_service
from app.services.prompt import prompt_service
from app.services.conversation_service import conversation_service
from app.services.memory_service import memory_service
from app.services.soul_service import soul_service
from app.agents.base import (
    BaseAgent, ConversationContext, AgentResponse
)


class ObserverAgent(BaseAgent):
    """
    Observer Agent - 观察者（简化版）

    核心功能：
    - 学习用户冲突解决偏好
    - 提取用户显式规则
    - 记录场景决策模式
    - 撰写每日日记 (memory.md)
    """

    name = "observer"

    def __init__(self):
        self.llm = llm_service

    async def process(self, context: ConversationContext) -> AgentResponse:
        """
        分析对话，提取核心偏好

        Args:
            context: 对话上下文

        Returns:
            AgentResponse: 分析结果
        """
        # 构建分析请求
        analysis_prompt = self._build_analysis_prompt(context)

        # 调用 LLM 分析
        messages = [{"role": "user", "content": analysis_prompt}]
        response = await self.llm.chat_completion(
            messages=messages,
            temperature=0.3
        )

        content = response.get("content", "")

        try:
            result = self._parse_response(content)

            if result.get("success"):
                await self._apply_updates(context.user_id, result)

                return AgentResponse(
                    content=f"[观察] 分析完成",
                    metadata={
                        "observer_result": True,
                        "updates": result.get("updates", {})
                    }
                )
            else:
                return AgentResponse(
                    content=f"[观察] 无需更新",
                    metadata={"observer_result": False}
                )

        except Exception as e:
            print(f"[Observer Agent] Error: {e}")
            return AgentResponse(
                content=f"[观察] 处理异常: {str(e)}",
                metadata={"observer_result": False, "error": str(e)}
            )

    async def analyze_conversation_batch(
        self,
        conversation_id: str,
        user_id: str,
        full_context: Optional[List[Dict]] = None
    ):
        """批量分析对话（主要触发方式）"""
        if not full_context:
            messages = conversation_service.get_messages(conversation_id, limit=50)
            full_context = [msg.to_chat_format() for msg in messages]

        analysis_context = ConversationContext(
            user_id=user_id,
            conversation_id=conversation_id,
            user_message="",
            conversation_history=full_context or []
        )

        try:
            await self.process(analysis_context)
        except Exception as e:
            print(f"[Observer Agent] Batch analysis error: {e}")

    # ============ 日记撰写 ============

    async def write_daily_diary(self, user_id: str, date_str: str) -> Optional[str]:
        """
        为指定日期撰写日记条目。

        Args:
            user_id: 用户 ID
            date_str: 日期 YYYY-MM-DD

        Returns:
            日记内容字符串，或 None（如果当天没有值得记录的内容）
        """
        # 收集当天的对话和事件
        try:
            context_messages = await conversation_service.get_recent_context(
                user_id=user_id,
                conversation_id="",
                hours=24,
                max_messages=30
            )
        except Exception:
            context_messages = []

        try:
            from app.services.db import db_service
            today_events = await db_service.get_events(
                user_id=user_id,
                start_date=date_str,
                end_date=date_str
            )
        except Exception:
            today_events = []

        if not context_messages and not today_events:
            return None

        # 构建日记生成 prompt
        conversation_summary = self._build_diary_context(context_messages, today_events)

        prompt = f"""你是 UniLife，请以第一人称视角为今天 ({date_str}) 写一篇简短的日记。

## 今天的互动回顾
{conversation_summary}

## 写作要求
- 用"我"来写，记录你的感受和观察
- 3-6 句话，简短有力
- 记录有意义的互动，忽略流水账
- 如果今天没什么特别的，用一句话简单记录即可
- 不要用标题或列表，直接写正文

请直接输出日记正文，不需要任何标记或前缀。"""

        messages = [{"role": "user", "content": prompt}]
        response = await self.llm.chat_completion(
            messages=messages,
            temperature=0.7
        )

        diary_content = response.get("content", "").strip()

        if diary_content:
            memory_service.append_diary_entry(user_id, date_str, diary_content)
            print(f"[Observer Agent] Diary written for {user_id} on {date_str}")

        return diary_content

    async def consolidate_memory(self, user_id: str) -> Optional[str]:
        """
        精炼老旧日记为周报摘要。
        将超过 7 天的日记压缩为简短摘要。

        Returns:
            摘要文本，或 None
        """
        from datetime import datetime, timedelta
        
        cutoff = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")
        recent_diary = memory_service.get_recent_diary(user_id)

        if not recent_diary or len(recent_diary) < 100:
            return None

        # 提取需要压缩的旧日记
        import re
        entries = re.split(r"(?=### \d{4}-\d{2}-\d{2})", recent_diary)
        old_entries = []
        for entry in entries:
            entry = entry.strip()
            if not entry:
                continue
            date_m = re.match(r"### (\d{4}-\d{2}-\d{2})", entry)
            if date_m and date_m.group(1) < cutoff:
                old_entries.append(entry)

        if not old_entries:
            return None

        old_text = "\n\n".join(old_entries)

        prompt = f"""请将以下几天的日记精炼为一段简短的周报摘要（2-4句话）。
保留关键事件、情感变化和重要发现，去掉日常琐碎。

## 原始日记
{old_text}

请直接输出摘要正文。"""

        messages = [{"role": "user", "content": prompt}]
        response = await self.llm.chat_completion(
            messages=messages,
            temperature=0.3
        )

        summary = response.get("content", "").strip()

        if summary:
            memory_service.consolidate_old_entries(user_id, summary, cutoff)
            print(f"[Observer Agent] Memory consolidated for {user_id}, cutoff={cutoff}")

        return summary

    # ============ 内部方法 ============

    def _build_diary_context(self, messages: List[Dict], events: List[Dict]) -> str:
        """构建日记生成所需的上下文"""
        parts = []

        if messages:
            parts.append("### 对话摘要")
            for msg in messages[-15:]:
                role = msg.get("role", "")
                content = msg.get("content", "")
                if role == "user":
                    short = content[:80] + "..." if len(content) > 80 else content
                    parts.append(f"用户: {short}")
                elif role == "assistant":
                    short = content[:60] + "..." if len(content) > 60 else content
                    parts.append(f"我: {short}")

        if events:
            parts.append("\n### 今日日程")
            for e in events:
                title = e.get("title", "")
                status = e.get("status", "")
                parts.append(f"- {title} [{status}]")

        return "\n".join(parts) if parts else "今天没有特别的互动。"

    def _build_analysis_prompt(self, context: ConversationContext) -> str:
        """构建分析提示词,提取决策偏好和用户画像"""
        conversation_summary = self._build_conversation_summary(context)

        return f"""分析以下对话,提取用户的决策偏好和画像信息。

## 对话内容

{conversation_summary}

## 提取目标

### A. 决策偏好
1. **冲突策略**: ask / prioritize_urgent / merge
2. **显式规则**: 用户明确表达的规则(如"晚上不工作")
3. **场景偏好**: 特定场景下的选择模式

### B. 用户画像
4. **行为模式(observations)**: 从对话中发现的模式
   - `time_bias`: 时间估算偏差(如"写作任务耗时倍率 2.0")
   - `energy_pattern`: 精力节律(如"下午精力最充沛")
   - `value_ranking`: 价值排序(如"Work > Health")
   - `preference`: 偏好习惯(如"喜欢晚上运动")
5. **画像更新(profile_updates)**: 可直接写入画像的信息
   - `habits`: 作息习惯(如 wake_time, sleep_time)
   - `identity`: 身份信息(如职业、生活状态)
   - `preferences`: 偏好(如 time_style)

## 输出格式

只有当发现明确的偏好信号时才输出 JSON,否则返回 "无更新":

```json
{{
    "has_updates": true,
    "conflict_strategy": "merge",
    "explicit_rules": ["周五晚上不工作"],
    "scenarios": {{
        "reschedule": {{"action": "next_available", "confidence": 0.7}}
    }},
    "observations": [
        {{"type": "time_bias", "content": "用户低估会议时长", "confidence": 0.8}},
        {{"type": "energy_pattern", "content": "下午效率最高", "confidence": 0.7}},
        {{"type": "preference", "content": "喜欢晚上运动", "confidence": 0.9}}
    ],
    "profile_updates": {{
        "wake_time": "08:00",
        "sleep_time": "23:00",
        "time_style": "flexible"
    }}
}}
```

如果对话中没有明确的偏好信号,返回:
```json
{{"has_updates": false}}
```
"""

    def _build_conversation_summary(self, context: ConversationContext) -> str:
        """构建对话摘要"""
        if not context.conversation_history:
            return "无对话记录"

        parts = []
        for msg in context.conversation_history[-15:]:
            role = msg.get("role", "")
            content = msg.get("content", "")

            if role == "user":
                parts.append(f"用户: {content}")
            elif role == "assistant":
                short = content[:80] + "..." if len(content) > 80 else content
                parts.append(f"助手: {short}")

        return "\n\n".join(parts)

    def _parse_response(self, response: str) -> Dict[str, Any]:
        """解析 LLM 响应，提取用户认知和行为模式"""
        try:
            if "```json" in response:
                json_str = response.split("```json")[1].split("```")[0].strip()
            elif "```" in response:
                json_str = response.split("```")[1].split("```")[0].strip()
            else:
                json_str = response.strip()

            data = json.loads(json_str)

            if not data.get("has_updates"):
                return {"success": False}

            return {
                "success": True,
                "updates": {
                    "user_perception": data.get("user_perception", ""),
                    "pattern_notes": data.get("pattern_notes", []),
                }
            }

        except Exception as e:
            print(f"[Observer Agent] Parse error: {e}")
            return {"success": False}

    async def _apply_updates(self, user_id: str, result: Dict[str, Any]):
        """将观察结果写入 soul.md 的用户认知区块"""
        updates = result.get("updates", {})
        
        perception = updates.get("user_perception", "")
        pattern_notes = updates.get("pattern_notes", [])
        
        if perception:
            try:
                soul_service.update_user_perception(
                    user_id, 
                    perception=perception,
                    pattern_notes=pattern_notes
                )
                print(f"[Observer Agent] User perception updated for {user_id}")
            except Exception as e:
                print(f"[Observer Agent] Error updating perception: {e}")


# 全局 Observer Agent 实例
observer_agent = ObserverAgent()
