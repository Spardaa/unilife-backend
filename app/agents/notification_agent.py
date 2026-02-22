"""
Notification Agent - 智能推送文案生成

在定时触发点（早上、中午、晚上、睡前、事件开始前），
收集 Checklist（事件 + 上下文 + 记忆），
注入 soul.md，由 LLM 决定是否推送以及生成个性化文案。

与 ProactiveCheckAgent 的区别：
  - ProactiveCheckAgent 是开放式"有话想说就说"
  - NotificationAgent 是基于具体事件/时间节点的提醒式消息
  - 两者可以同一时间点各自运行，互不干扰

Prompt 文件:
  - prompts/agents/notification_periodic.txt  (早/中/晚/睡前，含 should_send 决策)
  - prompts/agents/notification_event.txt     (事件开始前，始终发送)
"""
import json
import logging
from pathlib import Path
from typing import Dict, Any, Optional, List
from datetime import datetime

from app.services.llm import llm_service
from app.services.soul_service import soul_service
from app.services.memory_service import memory_service
from app.services.notification_service import notification_service
from app.services.conversation_service import conversation_service
from app.models.notification import (
    NotificationPayload, NotificationType, NotificationPriority
)

logger = logging.getLogger("notification_agent")

# Prompt 文件根目录（相对于当前文件：app/agents/ → 上上级 → prompts/agents/）
_PROMPTS_DIR = Path(__file__).parent.parent.parent / "prompts" / "agents"


def _load_prompt(filename: str) -> str:
    """从 prompts/agents/ 目录读取提示词文件"""
    try:
        return (_PROMPTS_DIR / filename).read_text(encoding="utf-8")
    except Exception as e:
        logger.warning(f"Failed to load prompt file {filename}: {e}")
        return ""


class NotificationAgent:
    """智能推送文案生成引擎"""

    def __init__(self):
        self.llm = llm_service
        # 从外部文件加载提示词
        self._periodic_prompt = _load_prompt("notification_periodic.txt")
        self._event_prompt = _load_prompt("notification_event.txt")

    # ==================== 定时节点推送 ====================

    async def generate_periodic_notification(
        self,
        user_id: str,
        period: str,
        events: List[Dict],
        recent_context: str = "",
        current_time: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        定时节点推送（早/中/晚/睡前）。

        Args:
            user_id: 用户 ID
            period: 时间节点 (morning / afternoon / evening / night)
            events: 当前时段的事件列表
            recent_context: 最近对话上下文摘要
            current_time: 当前时间字符串

        Returns:
            {
                "should_send": bool,
                "title": str,
                "body": str,
                "reasoning": str
            }
        """
        import pytz
        user_tz = pytz.timezone("Asia/Shanghai")
        now = datetime.now(user_tz)
        current_time = current_time or now.strftime("%Y-%m-%d %H:%M")

        # 收集 Checklist
        soul_content = soul_service.get_soul(user_id)
        memory_content = memory_service.get_recent_diary(user_id, days=3)

        # 格式化事件列表
        events_str = self._format_events(events) if events else "（本时段暂无日程）"

        # 渲染 prompt（从外部 txt 文件加载）
        prompt = self._periodic_prompt.format(
            current_time=current_time,
            notification_type=self._period_label(period),
            soul_content=soul_content or "（尚未形成）",
            memory_content=memory_content or "（暂无记忆）",
            today_events=events_str,
            recent_context=recent_context or "（最近没有对话）"
        )

        messages = [
            {"role": "system", "content": prompt},
            {"role": "user", "content": f"现在是 {current_time}，请决定是否发送{self._period_label(period)}提醒。"}
        ]

        response = await self.llm.chat_completion(
            messages=messages,
            temperature=0.6
        )

        content = response.get("content", "")
        result = self._parse_periodic_response(content)

        logger.info(
            f"NotificationAgent [{period}] for user {user_id}: "
            f"should_send={result.get('should_send', False)}"
        )

        # 如果决定发送
        if result.get("should_send") and result.get("body"):
            await self._send_and_inject(
                user_id=user_id,
                title=result.get("title", "UniLife"),
                body=result["body"],
                notification_type=NotificationType.GREETING,
                category=f"{period.upper()}_NOTIFICATION",
                data={
                    "type": f"{period}_notification",
                    "source": "notification_agent",
                    "action": "open_today"
                }
            )

        return result

    # ==================== 事件开始前提醒 ====================

    async def generate_event_reminder(
        self,
        user_id: str,
        event_title: str,
        event_start_time: str,
        minutes_until: int,
        event_id: str,
        current_time: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        事件开始前的提醒推送（始终发送，不做 skip 判断）。

        Args:
            user_id: 用户 ID
            event_title: 事件标题
            event_start_time: 事件开始时间
            minutes_until: 距离开始的分钟数
            event_id: 事件 ID
            current_time: 当前时间字符串

        Returns:
            {"title": str, "body": str}
        """
        import pytz
        user_tz = pytz.timezone("Asia/Shanghai")
        now = datetime.now(user_tz)
        current_time = current_time or now.strftime("%Y-%m-%d %H:%M")

        soul_content = soul_service.get_soul(user_id)

        # 检索与该事件相关的记忆
        memory_content = memory_service.get_relevant_memory(
            user_id=user_id,
            query=event_title,
            days=14
        )

        # 渲染 prompt（从外部 txt 文件加载）
        prompt = self._event_prompt.format(
            current_time=current_time,
            soul_content=soul_content or "（尚未形成）",
            memory_content=memory_content or "（无相关记忆）",
            event_title=event_title,
            minutes_until=minutes_until
        )

        messages = [
            {"role": "system", "content": prompt},
            {"role": "user", "content": f"请为「{event_title}」生成提醒。"}
        ]

        response = await self.llm.chat_completion(
            messages=messages,
            temperature=0.5
        )

        content = response.get("content", "")
        result = self._parse_event_reminder_response(content, event_title, minutes_until)

        # 始终发送
        await self._send_and_inject(
            user_id=user_id,
            title=result.get("title", "⏰ 日程提醒"),
            body=result["body"],
            notification_type=NotificationType.EVENT_REMINDER,
            category="EVENT_REMINDER",
            priority=NotificationPriority.HIGH,
            data={
                "type": "event_reminder",
                "event_id": event_id,
                "action": "open_event",
                "source": "notification_agent"
            }
        )

        return result

    # ==================== 发送 + 注入对话 ====================

    async def _send_and_inject(
        self,
        user_id: str,
        title: str,
        body: str,
        notification_type: NotificationType,
        category: str,
        data: Dict[str, Any],
        priority: NotificationPriority = NotificationPriority.NORMAL
    ) -> None:
        """发送推送通知，并将消息注入到用户最近的对话中"""
        try:
            # 1. 发送推送通知
            await notification_service.send_notification(
                user_id=user_id,
                payload=NotificationPayload(
                    title=title,
                    body=body,
                    category=category,
                    data=data
                ),
                notification_type=notification_type,
                priority=priority
            )
            logger.info(f"Notification sent to {user_id}: {body[:30]}...")
        except Exception as e:
            logger.warning(f"Failed to send push notification: {e}")

        try:
            # 2. 注入到用户的最近对话中，作为 AI 发的消息
            recent_convs = conversation_service.get_recent_conversations(
                user_id=user_id,
                days=3,
                limit=1
            )
            if recent_convs:
                conv = recent_convs[0]
            else:
                # 没有最近对话时，新建一个对话，确保推送内容不会丢失
                conv = conversation_service.create_conversation(
                    user_id=user_id,
                    title="UniLife 通知"
                )
                logger.info(f"Created new conversation {conv.id} for notification injection (user {user_id})")

            conversation_service.add_message(
                conversation_id=conv.id,
                role="assistant",
                content=body,
                extra_metadata=json.dumps({
                    "source": "notification_agent",
                    "notification_type": category,
                    "auto_generated": True
                })
            )
            logger.info(f"Message injected into conversation {conv.id} for user {user_id}")
        except Exception as e:
            logger.warning(f"Failed to inject message into conversation: {e}")

    # ==================== 辅助方法 ====================

    def _format_events(self, events: List[Dict]) -> str:
        """格式化事件列表为可读字符串"""
        if not events:
            return ""
        lines = []
        for e in events:
            title = e.get("title", "")
            start_time = e.get("start_time", "")
            time_period = e.get("time_period", "")
            status = e.get("status", "")
            duration = e.get("duration", "")
            time_info = start_time or time_period or "随时"
            duration_str = f" ({duration}min)" if duration else ""
            lines.append(f"- {title} ({time_info}){duration_str} [{status}]")
        return "\n".join(lines)

    def _period_label(self, period: str) -> str:
        """将时段代码转为中文标签"""
        labels = {
            "morning": "早安简报",
            "afternoon": "午间检查",
            "evening": "晚间切换",
            "night": "睡前仪式"
        }
        return labels.get(period, period)

    def _parse_periodic_response(self, content: str) -> Dict[str, Any]:
        """解析定时节点推送的 LLM JSON 响应"""
        try:
            json_str = self._extract_json(content)
            data = json.loads(json_str)
            return {
                "should_send": bool(data.get("should_send", False)),
                "reasoning": data.get("reasoning", ""),
                "title": data.get("title", "UniLife"),
                "body": data.get("body", "")
            }
        except Exception as e:
            logger.warning(f"Failed to parse periodic notification response: {e}")
            return {
                "should_send": False,
                "reasoning": f"Parse error: {e}",
                "title": "",
                "body": ""
            }

    def _parse_event_reminder_response(
        self, content: str, fallback_title: str, minutes: int
    ) -> Dict[str, Any]:
        """解析事件提醒的 LLM JSON 响应，带 fallback"""
        try:
            json_str = self._extract_json(content)
            data = json.loads(json_str)
            return {
                "title": data.get("title", "⏰ 日程提醒"),
                "body": data.get("body", f"「{fallback_title}」{minutes}分钟后开始")
            }
        except Exception as e:
            logger.warning(f"Failed to parse event reminder response: {e}")
            # Fallback 到静态文本
            return {
                "title": "⏰ 日程提醒",
                "body": f"「{fallback_title}」{minutes}分钟后开始"
            }

    def _extract_json(self, content: str) -> str:
        """从 LLM 响应中提取 JSON 字符串"""
        if "```json" in content:
            return content.split("```json")[1].split("```")[0].strip()
        elif "```" in content:
            return content.split("```")[1].split("```")[0].strip()
        else:
            return content.strip()


# 全局实例
notification_agent = NotificationAgent()
