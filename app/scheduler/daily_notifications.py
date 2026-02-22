"""
Daily Notifications - 每日通知调度模块

实现四个关键通知节点：
1. 🌅 早安简报 (Morning Briefing) - 用户起床时间
2. ☀️ 午间检查 (Afternoon Check-in) - 12:00
3. 🌙 晚间切换 (Evening Switch) - 18:00
4. 🛌 睡前仪式 (Closing Ritual) - 用户睡觉时间前15分钟

改造后：
- 所有推送文案由 NotificationAgent (LLM + soul.md) 动态生成
- 支持 should_send = false 跳过无意义推送
- 推送内容同时注入到用户的聊天记录中
"""
from typing import List, Dict, Any, Optional
from datetime import datetime, date, timedelta, time
import asyncio

from app.utils.awake_window import AwakeWindowChecker, get_user_awake_checker
from app.agents.notification_agent import notification_agent


class DailyNotificationScheduler:
    """每日通知调度器"""
    
    # 固定节点时间
    AFTERNOON_CHECKIN_TIME = "12:00"
    EVENING_SWITCH_TIME = "18:00"
    CLOSING_RITUAL_ADVANCE_MINUTES = 15
    
    def __init__(self):
        self.db_service = None  # 延迟加载
    
    def _get_db_service(self):
        """延迟加载数据库服务"""
        if self.db_service is None:
            from app.services.db import db_service
            self.db_service = db_service
        return self.db_service
    
    # ==================== 早安简报 ====================
    
    async def send_morning_briefing(self, user_id: str, force: bool = False) -> bool:
        """
        🌅 早安简报
        
        收集上午事件 + 记忆 + 上下文，交由 NotificationAgent 生成文案。
        NotificationAgent 会自行决定是否跳过推送。
        """
        try:
            # 检查用户是否启用此通知
            settings = await self._get_user_notification_settings(user_id)
            if not settings.get("morning_briefing_enabled", True) and not force:
                return False
            
            # 获取今日日程
            today_events = await self._get_today_events(user_id)
            morning_events = self._filter_morning_events(today_events)
            
            # 获取上下文
            recent_context = await self._get_recent_context(user_id)
            
            # 交给 NotificationAgent 处理（它会决定是否发送、生成文案、注入对话）
            result = await notification_agent.generate_periodic_notification(
                user_id=user_id,
                period="morning",
                events=morning_events + [e for e in today_events if e.get("time_period") == "anytime"],
                recent_context=recent_context
            )
            
            if result.get("should_send"):
                print(f"[DailyNotification] Morning briefing sent to {user_id}")
            else:
                print(f"[DailyNotification] Morning briefing skipped for {user_id}: {result.get('reasoning', '')[:60]}")
            
            return result.get("should_send", False)
            
        except Exception as e:
            print(f"[DailyNotification] Error sending morning briefing to {user_id}: {e}")
            return False
    
    # ==================== 午间检查 ====================
    
    async def send_afternoon_checkin(self, user_id: str, force: bool = False) -> bool:
        """
        ☀️ 午间检查
        
        触发条件：下午有硬日程时才触发
        """
        try:
            settings = await self._get_user_notification_settings(user_id)
            if not settings.get("afternoon_checkin_enabled", True) and not force:
                return False
            
            checker = get_user_awake_checker(settings)
            if not checker.should_send_notification("afternoon_checkin") and not force:
                return False
            
            # 获取下午日程
            afternoon_events = await self._get_afternoon_events(user_id)
            
            # 如果下午没有任何事件，直接跳过（不浪费 LLM 调用）
            if not afternoon_events and not force:
                return False
            
            recent_context = await self._get_recent_context(user_id)
            
            result = await notification_agent.generate_periodic_notification(
                user_id=user_id,
                period="afternoon",
                events=afternoon_events,
                recent_context=recent_context
            )
            
            if result.get("should_send"):
                print(f"[DailyNotification] Afternoon check-in sent to {user_id}")
            else:
                print(f"[DailyNotification] Afternoon check-in skipped for {user_id}")
            
            return result.get("should_send", False)
            
        except Exception as e:
            print(f"[DailyNotification] Error sending afternoon check-in to {user_id}: {e}")
            return False
    
    # ==================== 晚间切换 ====================
    
    async def send_evening_switch(self, user_id: str, force: bool = False) -> bool:
        """
        🌙 晚间切换
        
        重点提醒晚间生活类日程
        """
        try:
            settings = await self._get_user_notification_settings(user_id)
            if not settings.get("evening_switch_enabled", True) and not force:
                return False
            
            checker = get_user_awake_checker(settings)
            if not checker.should_send_notification("evening_switch") and not force:
                return False
            
            # 获取晚间日程
            evening_events = await self._get_evening_events(user_id)
            
            # 如果晚间没有任何事件，直接跳过
            if not evening_events and not force:
                return False
            
            recent_context = await self._get_recent_context(user_id)
            
            result = await notification_agent.generate_periodic_notification(
                user_id=user_id,
                period="evening",
                events=evening_events,
                recent_context=recent_context
            )
            
            if result.get("should_send"):
                print(f"[DailyNotification] Evening switch sent to {user_id}")
            else:
                print(f"[DailyNotification] Evening switch skipped for {user_id}")
            
            return result.get("should_send", False)
            
        except Exception as e:
            print(f"[DailyNotification] Error sending evening switch to {user_id}: {e}")
            return False
    
    # ==================== 睡前仪式 ====================
    
    async def send_closing_ritual(self, user_id: str, force: bool = False) -> bool:
        """
        🛌 睡前仪式
        
        盘点今日完成情况，NotificationAgent 会综合判断文案风格：
        - 全部完成 → 庆祝
        - 有未完成 → 结合明日日程给出建议
        """
        try:
            settings = await self._get_user_notification_settings(user_id)
            if not settings.get("closing_ritual_enabled", True) and not force:
                return False
            
            # 获取今日全部任务（包含完成和未完成）
            today_events = await self._get_today_events(user_id)
            
            recent_context = await self._get_recent_context(user_id)
            
            result = await notification_agent.generate_periodic_notification(
                user_id=user_id,
                period="night",
                events=today_events,
                recent_context=recent_context
            )
            
            if result.get("should_send"):
                print(f"[DailyNotification] Closing ritual sent to {user_id}")
            else:
                print(f"[DailyNotification] Closing ritual skipped for {user_id}")
            
            return result.get("should_send", False)
            
        except Exception as e:
            print(f"[DailyNotification] Error sending closing ritual to {user_id}: {e}")
            return False
    
    # ==================== 辅助方法 ====================
    
    async def _get_recent_context(self, user_id: str) -> str:
        """获取用户最近的对话上下文摘要"""
        try:
            from app.services.conversation_service import conversation_service
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
        except Exception:
            return ""
    
    async def _get_user_notification_settings(self, user_id: str) -> Dict[str, Any]:
        """获取用户通知设置"""
        try:
            from app.services.profile_service import profile_service
            profile = profile_service.get_or_create_profile(user_id)
            return profile.preferences
        except Exception as e:
            print(f"[DailyNotification] Error getting user settings: {e}")
            return {
                "wake_time": "08:00",
                "sleep_time": "22:00",
                "morning_briefing_enabled": True,
                "afternoon_checkin_enabled": True,
                "evening_switch_enabled": True,
                "closing_ritual_enabled": True
            }
    
    async def _get_today_events(self, user_id: str) -> List[Dict]:
        """获取今日所有日程"""
        try:
            db = self._get_db_service()
            today = date.today()
            events = await db.get_events_for_date(user_id, today)
            return events if events else []
        except Exception as e:
            print(f"[DailyNotification] Error getting today events: {e}")
            return []
    
    async def _get_tomorrow_events(self, user_id: str) -> List[Dict]:
        """获取明日日程"""
        try:
            db = self._get_db_service()
            tomorrow = date.today() + timedelta(days=1)
            events = await db.get_events_for_date(user_id, tomorrow)
            return events if events else []
        except Exception as e:
            print(f"[DailyNotification] Error getting tomorrow events: {e}")
            return []
    
    async def _get_afternoon_events(self, user_id: str) -> List[Dict]:
        """获取今日下午日程 (12:00-18:00)"""
        today_events = await self._get_today_events(user_id)
        return self._filter_time_range_events(today_events, 12, 18)
    
    async def _get_evening_events(self, user_id: str) -> List[Dict]:
        """获取今日晚间日程 (18:00-24:00)"""
        today_events = await self._get_today_events(user_id)
        return self._filter_time_range_events(today_events, 18, 24)
    
    def _filter_morning_events(self, events: List[Dict]) -> List[Dict]:
        """筛选上午日程 (06:00-12:00)"""
        return self._filter_time_range_events(events, 6, 12)
    
    def _filter_time_range_events(
        self, 
        events: List[Dict], 
        start_hour: int, 
        end_hour: int
    ) -> List[Dict]:
        """筛选指定时间范围内的日程"""
        filtered = []
        for event in events:
            start_time = event.get("start_time")
            if not start_time:
                # 检查 time_period
                time_period = event.get("time_period", "").lower()
                if start_hour < 12 and time_period == "morning":
                    filtered.append(event)
                elif 12 <= start_hour < 18 and time_period == "afternoon":
                    filtered.append(event)
                elif start_hour >= 18 and time_period in ["evening", "night"]:
                    filtered.append(event)
                continue
            
            # 解析时间
            try:
                if isinstance(start_time, str):
                    event_time = datetime.fromisoformat(start_time.replace("Z", "+00:00"))
                elif isinstance(start_time, datetime):
                    event_time = start_time
                else:
                    continue
                
                event_hour = event_time.hour
                if start_hour <= event_hour < end_hour:
                    filtered.append(event)
            except Exception:
                continue
        
        # 按时间排序
        filtered.sort(key=lambda e: e.get("start_time", "") or "")
        return filtered
    
    def _is_urgent(self, task: Dict) -> bool:
        """判断任务是否紧急"""
        # 检查 deadline
        deadline = task.get("deadline")
        if deadline:
            try:
                if isinstance(deadline, str):
                    deadline_dt = datetime.fromisoformat(deadline.replace("Z", "+00:00"))
                else:
                    deadline_dt = deadline
                
                tomorrow = datetime.now() + timedelta(days=1)
                if deadline_dt < tomorrow:
                    return True
            except Exception:
                pass
        
        event_type = task.get("event_type", "").lower()
        if event_type in ["deadline", "appointment"]:
            return True
        
        if task.get("is_mentally_demanding") and task.get("is_physically_demanding"):
            return True
        
        return False
    
    def _format_event_time(self, event: Dict) -> str:
        """格式化事件时间显示"""
        start_time = event.get("start_time")
        if not start_time:
            time_period = event.get("time_period", "")
            period_map = {
                "morning": "上午",
                "afternoon": "下午",
                "evening": "晚间",
                "night": "晚间",
                "anytime": ""
            }
            return period_map.get(time_period.lower(), "")
        
        try:
            if isinstance(start_time, str):
                event_time = datetime.fromisoformat(start_time.replace("Z", "+00:00"))
            else:
                event_time = start_time
            
            return f"（{event_time.strftime('%H:%M')}）"
        except Exception:
            return ""


# 全局实例
daily_notification_scheduler = DailyNotificationScheduler()
