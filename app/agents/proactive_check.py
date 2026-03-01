"""
Proactive Check Agent - AI 自主心跳检查（统一推送引擎）

在定时触发点（早晨、中午、傍晚、睡前），后台唤醒一次 AI 思考过程：
- 检查用户当前时段的日程（融合了原 daily_notification 的时段过滤能力）
- 检查近期记忆和对话上下文
- 结合 AI 自身身份/性格进行决策
- 自主决定是否发送消息，以及说什么

如果没有任何值得说的事情，保持沉默。

注意：破冰（Breaking the Ice）逻辑已移至前端触发 → unified_agent 路径，
本模块不再自动触发破冰。
"""
import logging
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta

from app.services.llm import llm_service
from app.services.memory_service import memory_service
from app.services.soul_service import soul_service
from app.services.identity_service import identity_service
from app.services.db import db_service
from app.services.notification_service import notification_service
from app.services.conversation_service import conversation_service
from app.models.notification import (
    NotificationPayload, NotificationType, NotificationPriority
)

logger = logging.getLogger("proactive_check")


# ============ 统一心跳 Prompt（身份感知 + 时段日程注入） ============

PROACTIVE_SYSTEM_PROMPT = """你是 {agent_name} {agent_emoji}，你正在进行一次"自我检查"。
现在是 {current_time}，时段类型: {check_type_label}。

## 你是谁
- 名字: {agent_name}
- 标志: {agent_emoji}
- 性格: {agent_vibe}

## 你的灵魂
{soul_content}

## 你的近期记忆
{memory_content}

## 本时段日程（{check_type_label}）
{period_events}

## 用户今日完整日程
{today_events}

## 用户明日日程
{tomorrow_events}

## 最近的对话上下文摘要
{recent_context}

---

# 任务
请思考以下问题：
1. 当前时段有没有即将开始、容易遗忘的事件需要提醒？
2. 从全天日程来看，用户今天的安排是否合理？有没有需要关注的节奏问题？
3. 根据你的记忆，用户最近的状态如何？是否需要关怀？
4. 现在这个时间点，有没有自然、不突兀的话想对用户说？

# 决策规则
- 如果确实有值得说的事 → should_message = true
- 如果没什么特别的、用户日程清闲、最近也没聊什么 → should_message = false
- **绝不做冗余信息发送**。宁可沉默，也不要发无意义的消息。
- 消息应该自然、简短、像朋友一样，不要像通知系统。
- **用你自己的性格说话**，不是用"系统"的口吻。你是 {agent_name}，不是通知机器人。

# 输出格式（纯 JSON）
```json
{{
    "should_message": true/false,
    "reasoning": "你的内部思考过程（不会展示给用户）",
    "message_content": "给用户的消息内容（若 should_message=false 则为空字符串）"
}}
```
"""

# 时段标签映射
CHECK_TYPE_LABELS = {
    "morning": "🌅 早晨",
    "noon": "☀️ 午间",
    "evening": "🌙 傍晚",
    "night": "🛌 睡前",
    "general": "日常",
}

# 时段对应的小时范围（用于过滤日程）
CHECK_TYPE_HOUR_RANGES = {
    "morning": (6, 12),
    "noon": (12, 18),
    "evening": (18, 24),
    "night": (0, 24),  # 睡前回顾全天
    "general": (0, 24),
}


class ProactiveCheckAgent:
    """统一心跳检查引擎（融合了原 daily_notification + proactive_check）"""

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

        # 获取 AI 身份
        identity = identity_service.get_identity(user_id)
        
        # 获取用户画像，检查是否处于破冰模式
        from app.services.profile_service import profile_service
        user_field_id = user_id
        try:
            user_data = await db_service.get_user(user_id)
            if user_data and user_data.get("user_id"):
                user_field_id = user_data["user_id"]
        except Exception:
            pass
            
        user_profile = profile_service.get_or_create_profile(user_field_id)
        needs_onboarding = user_profile.preferences.get("needs_onboarding", False)
        
        # 破冰阶段不主动打扰用户
        if needs_onboarding or identity_service.is_default(user_id):
            logger.info(f"Heartbeat skipped for {user_id}: User needs onboarding")
            return {"should_message": False, "reasoning": "User needs onboarding", "message_content": ""}

        # 收集上下文
        soul_content = soul_service.get_soul(user_id)
        memory_content = memory_service.get_recent_diary(user_id, days=3)

        # 获取日程（按时段过滤 + 全天 + 明天）
        today_str = now.strftime("%Y-%m-%d")
        tomorrow_str = (now + timedelta(days=1)).strftime("%Y-%m-%d")

        today_events_raw = await self._get_events(user_id, today_str)
        tomorrow_events_raw = await self._get_events(user_id, tomorrow_str)

        # 按时段过滤当前时段的事件
        hour_range = CHECK_TYPE_HOUR_RANGES.get(check_type, (0, 24))
        period_events = self._filter_events_by_hours(today_events_raw, hour_range[0], hour_range[1])

        period_events_str = self._format_events(period_events) if period_events else "（本时段暂无日程）"
        today_events_str = self._format_events(today_events_raw) if today_events_raw else "（今日暂无日程）"
        tomorrow_events_str = self._format_events(tomorrow_events_raw) if tomorrow_events_raw else "（明日暂无日程）"

        recent_context = await self._get_recent_context_summary(user_id)

        # 渲染 prompt
        prompt = PROACTIVE_SYSTEM_PROMPT.format(
            agent_name=identity.name,
            agent_emoji=identity.emoji,
            agent_vibe=identity.vibe,
            current_time=current_time,
            check_type_label=CHECK_TYPE_LABELS.get(check_type, check_type),
            soul_content=soul_content or "（尚未形成）",
            memory_content=memory_content or "（暂无记忆）",
            period_events=period_events_str,
            today_events=today_events_str,
            tomorrow_events=tomorrow_events_str,
            recent_context=recent_context or "（最近没有对话）"
        )

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
            f"Heartbeat [{check_type}] for user {user_id}: "
            f"should_message={result.get('should_message', False)}"
        )

        # 如果决定发消息，发送推送并注入对话记录
        if result.get("should_message") and result.get("message_content"):
            await self._send_and_inject(
                user_id=user_id,
                message=result["message_content"],
                check_type=check_type,
                identity=identity
            )

        return result

    # ==================== 日程获取与过滤 ====================

    async def _get_events(self, user_id: str, date_str: str) -> List[Dict]:
        """获取某日的事件列表"""
        try:
            events = await db_service.get_events(
                user_id=user_id,
                start_date=date_str,
                end_date=date_str
            )
            return events if events else []
        except Exception as ex:
            logger.warning(f"Failed to get events for {date_str}: {ex}")
            return []

    def _filter_events_by_hours(
        self, events: List[Dict], start_hour: int, end_hour: int
    ) -> List[Dict]:
        """按小时范围过滤事件（融合自 daily_notifications 的逻辑）"""
        filtered = []
        for event in events:
            start_time = event.get("start_time")
            if not start_time:
                # 按 time_period 粗匹配
                time_period = event.get("time_period", "").lower()
                if start_hour < 12 and time_period == "morning":
                    filtered.append(event)
                elif 12 <= start_hour < 18 and time_period == "afternoon":
                    filtered.append(event)
                elif start_hour >= 18 and time_period in ("evening", "night"):
                    filtered.append(event)
                elif time_period == "anytime":
                    filtered.append(event)
                continue

            try:
                if isinstance(start_time, str):
                    event_time = datetime.fromisoformat(start_time.replace("Z", "+00:00"))
                elif isinstance(start_time, datetime):
                    event_time = start_time
                else:
                    continue

                if start_hour <= event_time.hour < end_hour:
                    filtered.append(event)
            except Exception:
                continue

        return filtered

    def _format_events(self, events: List[Dict]) -> str:
        """格式化事件列表为可读字符串"""
        lines = []
        for e in events:
            title = e.get("title", "")
            start_time = e.get("start_time", "")
            time_period = e.get("time_period", "")
            status = e.get("status", "")
            time_info = start_time or time_period or "随时"
            lines.append(f"- {title} ({time_info}) [{status}]")
        return "\n".join(lines)

    # ==================== 对话上下文 ====================

    async def _get_recent_context_summary(self, user_id: str) -> str:
        """获取最近对话的简要摘要"""
        try:
            messages = await conversation_service.get_recent_context(
                user_id=user_id,
                conversation_id="",
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

    # ==================== 发送 + 注入对话 ====================

    async def _send_and_inject(
        self,
        user_id: str,
        message: str,
        check_type: str,
        identity: Any
    ) -> None:
        """
        发送推送通知，并将消息注入到用户的对话记录中
        （融合了 notification_agent._send_and_inject 的能力）
        """
        import json

        title = f"{identity.name} {identity.emoji}"

        # 1. 发送推送
        try:
            payload = NotificationPayload(
                type=NotificationType.PROACTIVE_CHECK,
                title=title,
                body=message,
                priority=NotificationPriority.MEDIUM,
                data={
                    "source": "heartbeat",
                    "check_type": check_type
                }
            )
            await notification_service.send_notification(
                user_id, payload,
                notification_type=NotificationType.PROACTIVE_CHECK
            )
            logger.info(f"Heartbeat push sent to {user_id}: {message[:50]}...")
        except Exception as ex:
            logger.warning(f"Failed to send heartbeat push: {ex}")

        # 2. 注入到用户最近的对话中（保证用户打开 App 能看到这条消息）
        try:
            recent_convs = conversation_service.get_recent_conversations(
                user_id=user_id,
                days=3,
                limit=1
            )
            if recent_convs:
                conv = recent_convs[0]
            else:
                conv = conversation_service.create_conversation(
                    user_id=user_id,
                    title=f"{identity.name} 的心跳"
                )
                logger.info(f"Created new conversation {conv.id} for heartbeat injection")

            conversation_service.add_message(
                conversation_id=conv.id,
                role="assistant",
                content=message,
                extra_metadata=json.dumps({
                    "source": "heartbeat",
                    "check_type": check_type,
                    "auto_generated": True
                })
            )
            logger.info(f"Heartbeat message injected into conversation {conv.id}")
        except Exception as ex:
            logger.warning(f"Failed to inject heartbeat message: {ex}")

    # ==================== 响应解析 ====================

    def _parse_response(self, content: str) -> Dict[str, Any]:
        """解析 LLM JSON 响应"""
        import json
        try:
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
            logger.warning(f"Failed to parse heartbeat response: {e}")
            return {
                "should_message": False,
                "reasoning": f"Parse error: {e}",
                "message_content": ""
            }


# 全局实例
proactive_check_agent = ProactiveCheckAgent()
