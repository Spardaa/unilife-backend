"""
ScheduleAgent - Event CRUD execution and scheduling
"""
from typing import Dict, Any, List, Optional
from datetime import datetime
import json

from app.services.llm import llm_service
from app.services.db import db_service
from app.services.prompt import prompt_service
from app.models.event import Event, EventType, EventStatus, Category, EnergyLevel
from app.agents.intent import Intent


class ScheduleAgent:
    """
    Agent responsible for event CRUD operations, conflict handling, and smart scheduling
    """

    def __init__(self):
        self.llm = llm_service
        self.db = db_service

    async def handle_create_event(
        self,
        user_message: str,
        user_id: str,
        context: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """
        Handle event creation from natural language

        Args:
            user_message: User's natural language message
            user_id: User ID
            context: Optional context (conversation history, etc.)

        Returns:
            Result with created event and agent response
        """
        # Parse event from user message using LLM
        event_data = await self._parse_event_from_message(user_message, user_id)

        if not event_data:
            return {
                "success": False,
                "reply": "抱歉，我没有完全理解您的意图。能再详细描述一下这个日程吗？",
                "actions": []
            }

        # Check for time conflicts if event has fixed time
        if event_data.get("start_time") and event_data.get("end_time"):
            conflicts = await self.db.check_time_conflict(
                user_id=user_id,
                start_time=event_data["start_time"],
                end_time=event_data["end_time"]
            )

            if conflicts:
                # Conflict detected - ask user how to handle
                conflict_info = self._format_conflicts(conflicts)
                return {
                    "success": False,
                    "reply": f"检测到时间冲突：\n{conflict_info}\n\n建议改期或调整时间，您希望怎么处理？",
                    "actions": [],
                    "conflicts": conflicts
                }

        # Create event in database
        created_event = await self.db.create_event(event_data)

        return {
            "success": True,
            "reply": self._generate_creation_reply(created_event),
            "actions": [
                {
                    "type": "create_event",
                    "event_id": created_event["id"],
                    "event": created_event
                }
            ]
        }

    async def handle_query_event(
        self,
        user_message: str,
        user_id: str,
        context: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """
        Handle event query from natural language

        Returns events matching the query
        """
        # Parse query to extract filters (date range, type, etc.)
        filters = await self._parse_query_filters(user_message)

        # Get events from database
        events = await self.db.get_events(user_id, filters=filters, limit=50)

        if not events:
            return {
                "success": True,
                "reply": "这个时间段没有安排任何事件。",
                "actions": [],
                "events": []
            }

        # Format events for display
        events_summary = self._format_events_summary(events)

        return {
            "success": True,
            "reply": events_summary,
            "actions": [],
            "events": events
        }

    async def handle_update_event(
        self,
        user_message: str,
        user_id: str,
        context: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """
        Handle event update from natural language

        Updates event properties based on user request
        """
        # Parse which event to update and what to change
        update_request = await self._parse_update_request(user_message, user_id)

        if not update_request:
            return {
                "success": False,
                "reply": "抱歉，我没有理解您想修改什么。能再说明一下吗？",
                "actions": []
            }

        event_id = update_request["event_id"]
        update_data = update_request["update_data"]

        # Get current event state
        current_event = await self.db.get_event(event_id, user_id)

        if not current_event:
            return {
                "success": False,
                "reply": "未找到指定的事件。",
                "actions": []
            }

        # Check for new time conflicts if time is being updated
        if update_data.get("start_time") and update_data.get("end_time"):
            conflicts = await self.db.check_time_conflict(
                user_id=user_id,
                start_time=update_data["start_time"],
                end_time=update_data["end_time"],
                exclude_event_id=event_id
            )

            if conflicts:
                conflict_info = self._format_conflicts(conflicts)
                return {
                    "success": False,
                    "reply": f"检测到时间冲突：\n{conflict_info}\n\n无法修改到该时间，请选择其他时间。",
                    "actions": []
                }

        # Update event
        updated_event = await self.db.update_event(event_id, user_id, update_data)

        return {
            "success": True,
            "reply": self._generate_update_reply(current_event, updated_event),
            "actions": [
                {
                    "type": "update_event",
                    "event_id": updated_event["id"],
                    "event": updated_event
                }
            ],
            "before": current_event,
            "after": updated_event
        }

    async def handle_delete_event(
        self,
        user_message: str,
        user_id: str,
        context: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """
        Handle event deletion from natural language
        """
        # Parse which event to delete
        event_id = await self._parse_event_to_delete(user_message, user_id)

        if not event_id:
            # Try to identify from context
            if context and "last_event_id" in context:
                event_id = context["last_event_id"]

        if not event_id:
            return {
                "success": False,
                "reply": "请明确指定要取消哪个事件。",
                "actions": []
            }

        # Get event for confirmation message
        event = await self.db.get_event(event_id, user_id)

        if not event:
            return {
                "success": False,
                "reply": "未找到指定的事件。",
                "actions": []
            }

        # Delete event
        success = await self.db.delete_event(event_id, user_id)

        if success:
            return {
                "success": True,
                "reply": f"已取消：{event['title']}（{self._format_time(event)}）",
                "actions": [
                    {
                        "type": "delete_event",
                        "event_id": event_id,
                        "event": event
                    }
                ],
                "before": event,
                "after": None
            }
        else:
            return {
                "success": False,
                "reply": "删除事件失败，请稍后重试。",
                "actions": []
            }

    # ============ Helper Methods ============

    async def _parse_event_from_message(self, message: str, user_id: str) -> Optional[Dict[str, Any]]:
        """Parse event data from natural language message using LLM"""
        # Load prompt from external file
        system_prompt = prompt_service.load_prompt("scheduler_parse_event")

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": message}
        ]

        try:
            response = await self.llm.chat_completion(
                messages=messages,
                temperature=0.3
            )

            # Parse JSON from response
            content = response["content"]
            # Extract JSON from markdown code blocks if present
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0].strip()
            elif "```" in content:
                content = content.split("```")[1].split("```")[0].strip()

            event_data = json.loads(content)

            # Add user_id and metadata
            event_data["user_id"] = user_id
            event_data["status"] = EventStatus.PENDING.value
            event_data["created_by"] = "agent"
            event_data["ai_confidence"] = 0.8
            event_data["ai_reasoning"] = "Parsed from natural language"

            # Convert string times to datetime if present
            if event_data.get("start_time"):
                event_data["start_time"] = datetime.fromisoformat(event_data["start_time"])
            if event_data.get("end_time"):
                event_data["end_time"] = datetime.fromisoformat(event_data["end_time"])

            return event_data

        except Exception as e:
            print(f"Error parsing event: {e}")
            return None

    async def _parse_query_filters(self, message: str) -> Dict[str, Any]:
        """Parse query filters from natural language"""
        # Simple keyword-based filtering for now
        filters = {}
        message_lower = message.lower()

        # Date-based filters (simplified - should use NLP in production)
        if "今天" in message or "today" in message_lower:
            pass  # Would filter by today's date
        elif "明天" in message or "tomorrow" in message_lower:
            pass  # Would filter by tomorrow's date
        elif "本周" in message or "this week" in message_lower:
            pass  # Would filter by this week

        # Category filters
        if "会议" in message or "meeting" in message_lower:
            filters["category"] = Category.WORK.value
        elif "学习" in message or "study" in message_lower:
            filters["category"] = Category.STUDY.value
        elif "社交" in message or "social" in message_lower:
            filters["category"] = Category.SOCIAL.value

        # Status filters
        if "完成" in message or "completed" in message_lower:
            filters["status"] = EventStatus.COMPLETED.value
        elif "待办" in message or "pending" in message_lower:
            filters["status"] = EventStatus.PENDING.value

        return filters

    async def _parse_update_request(self, message: str, user_id: str) -> Optional[Dict[str, Any]]:
        """Parse update request - which event and what to change"""
        # For now, return None - needs context or more advanced parsing
        return None

    async def _parse_event_to_delete(self, message: str, user_id: str) -> Optional[str]:
        """Parse which event to delete"""
        # For now, return None - needs context or more advanced parsing
        return None

    def _format_conflicts(self, conflicts: List[Dict[str, Any]]) -> str:
        """Format conflicting events for display"""
        lines = []
        for conflict in conflicts:
            lines.append(f"- {conflict['title']}（{self._format_time(conflict)}）")
        return "\n".join(lines)

    def _format_time(self, event: Dict[str, Any]) -> str:
        """Format event time for display"""
        if event.get("start_time") and event.get("end_time"):
            start = datetime.fromisoformat(event["start_time"]).strftime("%H:%M")
            end = datetime.fromisoformat(event["end_time"]).strftime("%H:%M")
            return f"{start}-{end}"
        elif event.get("end_time"):
            ddl = datetime.fromisoformat(event["end_time"]).strftime("%m/%d %H:%M")
            return f"截止: {ddl}"
        return "无固定时间"

    def _format_events_summary(self, events: List[Dict[str, Any]]) -> str:
        """Format events list for display"""
        if not events:
            return "没有找到任何事件。"

        lines = ["您的安排："]
        for event in events:
            time_str = self._format_time(event)
            status_icon = "✓" if event["status"] == "COMPLETED" else "○"
            lines.append(f"{status_icon} {event['title']}（{time_str}）")

        return "\n".join(lines)

    def _generate_creation_reply(self, event: Dict[str, Any]) -> str:
        """Generate natural language reply for event creation"""
        time_str = self._format_time(event)
        reply = f"已为您安排：{event['title']}"
        if time_str != "无固定时间":
            reply += f"（{time_str}）"
        return reply

    def _generate_update_reply(self, before: Dict[str, Any], after: Dict[str, Any]) -> str:
        """Generate natural language reply for event update"""
        return f"已更新：{after['title']}"


# Global ScheduleAgent instance
schedule_agent = ScheduleAgent()
