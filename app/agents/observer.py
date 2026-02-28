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
        实现 BaseAgent 抽象方法 (已弃用，请直接调用 daily_review)
        """
        return AgentResponse(content="[观察] 已弃用，使用 daily_review")

    async def daily_review(self, user_id: str, date_str: str) -> Optional[Dict[str, Any]]:
        """
        每日统一复盘：写日记并可能演化灵魂

        Args:
            user_id: 用户 ID
            date_str: 日期 YYYY-MM-DD

        Returns:
            Dict containing the updates or None
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
            print(f"[Observer Agent] No interaction for {user_id} on {date_str}, skipping review.")
            return None

        conversation_summary = self._build_diary_context(context_messages, today_events)

        try:
            soul_content = soul_service.get_soul(user_id)
        except Exception:
            soul_content = ""

        try:
            memory_content = memory_service.get_memory(user_id)
        except Exception:
            memory_content = ""

        try:
            base_prompt = prompt_service.get_prompt("agents/observer")
        except Exception as e:
            print(f"[Observer Agent] Error loading observer prompt: {e}")
            return None

        final_prompt = base_prompt.replace("{soul_content}", soul_content).replace("{memory_content}", memory_content)
        
        full_prompt = f"""{final_prompt}

## 今天的互动回顾 ({date_str})
{conversation_summary}
"""

        messages = [{"role": "user", "content": full_prompt}]
        response = await self.llm.chat_completion(
            messages=messages,
            temperature=0.7
        )

        content = response.get("content", "")
        result = self._parse_unified_response(content)

        if result.get("success"):
            updates = result.get("updates", {})
            diary = updates.get("diary_entry")
            soul_update = updates.get("soul_update")

            if diary:
                memory_service.append_diary_entry(user_id, date_str, diary)
                print(f"[Observer Agent] Diary written for {user_id} on {date_str}")
            
            if soul_update:
                soul_service.update_soul(user_id, soul_update)
                print(f"[Observer Agent] Soul updated for {user_id} on {date_str}")
                
            return updates
        else:
            print(f"[Observer Agent] Failed to parse output for {user_id} on {date_str}")
            return None

    # ============ 日记撰写 ============

    # ============ 旧方法清理 (已由 daily_review 统一) ============
    # process, analyze_conversation_batch, write_daily_diary 已经被合并到 daily_review 中

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

        try:
            base_prompt = prompt_service.get_prompt("agents/memory_consolidation")
        except Exception:
            base_prompt = "请将以下几天的日记精炼为一段简短的周报摘要（2-4句话）。\n\n## 原始日记\n{old_text}"

        prompt = base_prompt.replace("{old_text}", old_text)

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

    # ============ 辅助方法 ============

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

    def _parse_unified_response(self, response: str) -> Dict[str, Any]:
        """解析 LLM 响应，提取日记和可能的灵魂更新"""
        try:
            if "```json" in response:
                json_str = response.split("```json")[1].split("```")[0].strip()
            elif "```" in response:
                json_str = response.split("```")[1].split("```")[0].strip()
            else:
                json_str = response.strip()

            data = json.loads(json_str)

            if not data.get("diary_entry"):
                return {"success": False}

            return {
                "success": True,
                "updates": {
                    "diary_entry": data.get("diary_entry"),
                    "soul_update": data.get("soul_update"),
                }
            }

        except Exception as e:
            print(f"[Observer Agent] Parse error: {e}")
            return {"success": False}


# 全局 Observer Agent 实例
observer_agent = ObserverAgent()
