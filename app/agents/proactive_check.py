"""
Proactive Check Agent - 自主定时检查

在定时触发点（早晨、中午、傍晚、睡前），后台唤醒一次思考过程：
- 检查用户今日/明日日程
- 检查最近记忆日记
- 检查未完结的上下文
- 自主决策是否给用户发送消息

如果没有任何值得说的事情，保持沉默。
"""
import logging
from typing import Dict, Any, Optional
from datetime import datetime

from app.services.llm import llm_service
from app.services.memory_service import memory_service
from app.services.soul_service import soul_service
from app.services.db import db_service
from app.services.notification_service import notification_service
from app.services.conversation_service import conversation_service
from app.models.notification import (
    NotificationPayload, NotificationType, NotificationPriority
)

logger = logging.getLogger("proactive_check")


PROACTIVE_SYSTEM_PROMPT = """你是 UniLife，你正在进行一次"自我检查"。
现在是 {current_time}，时点类型: {check_type}。

## 你的灵魂
{soul_content}

## 你的近期记忆
{memory_content}

## 用户今日日程
{today_events}

## 用户明日日程
{tomorrow_events}

## 最近的对话上下文摘要
{recent_context}

---

# 任务
请思考以下问题：
1. 用户的日程中有什么需要关注的事吗？（如即将到来的重要事件、可能遗忘的任务）
2. 根据你的记忆，用户最近的状态如何？是否需要关怀？
3. 现在这个时间点，有没有自然、不突兀的话想对用户说？

# 决策规则
- 如果确实有值得说的事 → should_message = true
- 如果没什么特别的、用户日程清闲、最近也没聊什么 → should_message = false
- **绝不做冗余信息发送**。宁可沉默，也不要发无意义的消息。
- 消息应该自然、简短、像朋友一样，不要像通知系统。

# 输出格式（纯 JSON）
```json
{{
    "should_message": true/false,
    "reasoning": "你的内部思考过程（不会展示给用户）",
    "message_content": "给用户的消息内容（若 should_message=false 则为空字符串）"
}}
```
"""


class ProactiveCheckAgent:
    """自主定时检查引擎"""

    def __init__(self):
        self.llm = llm_service

    async def run_check(
        self,
        user_id: str,
        check_type: str = "general",
        current_time: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        执行一次主动检查。

        Args:
            user_id: 用户 ID
            check_type: 检查类型 (morning / noon / evening / night)
            current_time: 当前时间字符串

        Returns:
            {
                "should_message": bool,
                "reasoning": str,
                "message_content": str
            }
        """
        import pytz
        user_tz = pytz.timezone("Asia/Shanghai")
        now = datetime.now(user_tz)
        current_time = current_time or now.strftime("%Y-%m-%d %H:%M:%S")

        # 收集上下文
        soul_content = soul_service.get_soul(user_id)
        memory_content = memory_service.get_recent_diary(user_id, days=3)
        today_events = await self._get_events_str(user_id, now.strftime("%Y-%m-%d"))
        tomorrow_date = (now + __import__("datetime").timedelta(days=1)).strftime("%Y-%m-%d")
        tomorrow_events = await self._get_events_str(user_id, tomorrow_date)
        recent_context = await self._get_recent_context_summary(user_id)

        # 渲染 prompt
        prompt = PROACTIVE_SYSTEM_PROMPT.format(
            current_time=current_time,
            check_type=check_type,
            soul_content=soul_content or "（尚未形成）",
            memory_content=memory_content or "（暂无记忆）",
            today_events=today_events or "（今日暂无日程）",
            tomorrow_events=tomorrow_events or "（明日暂无日程）",
            recent_context=recent_context or "（最近没有对话）"
        )

        # 调用 LLM
        messages = [
            {"role": "system", "content": prompt},
            {"role": "user", "content": f"现在是 {current_time}，请进行自我检查。"}
        ]

        response = await self.llm.chat_completion(
            messages=messages,
            temperature=0.6
        )

        content = response.get("content", "")
        result = self._parse_response(content)

        logger.info(
            f"Proactive check [{check_type}] for user {user_id}: "
            f"should_message={result.get('should_message', False)}"
        )

        # 如果决定发消息，通过推送发送
        if result.get("should_message") and result.get("message_content"):
            await self._send_proactive_message(
                user_id=user_id,
                message=result["message_content"],
                check_type=check_type
            )

        return result

    async def _get_events_str(self, user_id: str, date_str: str) -> str:
        """获取某日的事件列表字符串"""
        try:
            events = await db_service.get_events(
                user_id=user_id,
                start_date=date_str,
                end_date=date_str
            )
            if not events:
                return ""
            lines = []
            for e in events:
                title = e.get("title", "")
                start_time = e.get("start_time", "")
                time_period = e.get("time_period", "")
                status = e.get("status", "")
                time_info = start_time or time_period or "随时"
                lines.append(f"- {title} ({time_info}) [{status}]")
            return "\n".join(lines)
        except Exception as ex:
            logger.warning(f"Failed to get events for {date_str}: {ex}")
            return ""

    async def _get_recent_context_summary(self, user_id: str) -> str:
        """获取最近对话的简要摘要"""
        try:
            # 获取最近 24 小时的对话
            messages = await conversation_service.get_recent_context(
                user_id=user_id,
                conversation_id="",  # 获取所有对话
                hours=24,
                max_messages=10
            )
            if not messages:
                return ""
            lines = []
            for msg in messages:
                role = msg.get("role", "")
                content = msg.get("content", "")
                if role in ("user", "assistant") and content:
                    short = content[:60] + "..." if len(content) > 60 else content
                    lines.append(f"[{role}] {short}")
            return "\n".join(lines)
        except Exception as ex:
            logger.warning(f"Failed to get recent context: {ex}")
            return ""

    async def _send_proactive_message(
        self,
        user_id: str,
        message: str,
        check_type: str
    ) -> None:
        """通过推送通知发送主动消息"""
        try:
            payload = NotificationPayload(
                type=NotificationType.PROACTIVE_CHECK,
                title="UniLife",
                body=message,
                priority=NotificationPriority.MEDIUM,
                data={
                    "source": "proactive_check",
                    "check_type": check_type
                }
            )
            await notification_service.send_notification(user_id, payload, notification_type=NotificationType.PROACTIVE_CHECK)
            logger.info(f"Proactive message sent to {user_id}: {message[:50]}...")
        except Exception as ex:
            logger.warning(f"Failed to send proactive notification: {ex}")

    def _parse_response(self, content: str) -> Dict[str, Any]:
        """解析 LLM JSON 响应"""
        import json
        try:
            # 提取 JSON
            if "```json" in content:
                json_str = content.split("```json")[1].split("```")[0].strip()
            elif "```" in content:
                json_str = content.split("```")[1].split("```")[0].strip()
            else:
                json_str = content.strip()

            data = json.loads(json_str)
            return {
                "should_message": bool(data.get("should_message", False)),
                "reasoning": data.get("reasoning", ""),
                "message_content": data.get("message_content", "")
            }
        except Exception as e:
            logger.warning(f"Failed to parse proactive check response: {e}")
            return {
                "should_message": False,
                "reasoning": f"Parse error: {e}",
                "message_content": ""
            }


# 全局实例
proactive_check_agent = ProactiveCheckAgent()
