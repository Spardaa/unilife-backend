"""
Daily Notifications - 每日通知调度模块

实现四个关键通知节点：
1. 🌅 早安简报 (Morning Briefing) - 用户起床时间
2. ☀️ 午间检查 (Afternoon Check-in) - 12:00
3. 🌙 晚间切换 (Evening Switch) - 18:00
4. 🛌 睡前仪式 (Closing Ritual) - 用户睡觉时间前15分钟
"""
from typing import List, Dict, Any, Optional
from datetime import datetime, date, timedelta, time
import asyncio

from app.utils.awake_window import AwakeWindowChecker, get_user_awake_checker
from app.services.notification_service import notification_service
from app.models.notification import (
    NotificationPayload, NotificationType, NotificationPriority
)


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
        
        内容策略：
        - 提取今日上午硬日程
        - 若上午空闲，推荐一个随时任务
        - 生成元气、清晰的文案
        """
        try:
            # 检查用户是否启用此通知
            settings = await self._get_user_notification_settings(user_id)
            if not settings.get("morning_briefing_enabled", True) and not force:
                return False
            
            # 获取今日日程
            today_events = await self._get_today_events(user_id)
            morning_events = self._filter_morning_events(today_events)
            
            # 构建通知内容
            body = ""
            if morning_events:
                first_event = morning_events[0]
                start_time = self._format_event_time(first_event)
                body = f"今天上午有 {len(morning_events)} 个安排。首先是「{first_event.get('title', '待办事项')}」{start_time}。加油！"
            else:
                # 查找随时任务
                anytime_events = [e for e in today_events if e.get("time_period") == "anytime"]
                if anytime_events:
                    suggestion = anytime_events[0]
                    body = f"上午没有固定安排，可以考虑处理「{suggestion.get('title', '待办事项')}」。轻松开启新的一天！"
                else:
                    body = "今天上午没有安排，享受轻松的早晨吧！☀️"
            
            # 发送通知
            await notification_service.send_notification(
                user_id=user_id,
                payload=NotificationPayload(
                    title="🌅 早安",
                    body=body,
                    category="MORNING_BRIEFING",
                    data={
                        "type": "morning_briefing",
                        "action": "open_today",
                        "event_count": len(morning_events)
                    }
                ),
                notification_type=NotificationType.GREETING,
                priority=NotificationPriority.NORMAL
            )
            
            print(f"[DailyNotification] Sent morning briefing to {user_id}")
            return True
            
        except Exception as e:
            print(f"[DailyNotification] Error sending morning briefing to {user_id}: {e}")
            return False
    
    # ==================== 午间检查 ====================
    
    async def send_afternoon_checkin(self, user_id: str, force: bool = False) -> bool:
        """
        ☀️ 午间检查
        
        触发条件：下午有硬日程时才触发
        内容策略：轻松、关怀基调
        """
        try:
            # 检查设置和清醒窗口
            settings = await self._get_user_notification_settings(user_id)
            if not settings.get("afternoon_checkin_enabled", True) and not force:
                return False
            
            checker = get_user_awake_checker(settings)
            if not checker.should_send_notification("afternoon_checkin") and not force:
                return False
            
            # 获取下午日程
            afternoon_events = await self._get_afternoon_events(user_id)
            
            if not afternoon_events:
                if not force:
                    return False  # 下午无事，保持安静
                body = "这是午间检查的测试通知（下午暂无日程，享受悠闲时光吧～）"
                first_event = {} # Dummy
            else:
                first_event = afternoon_events[0]
                start_time = self._format_event_time(first_event)
                if len(afternoon_events) == 1:
                    body = f"下午有 1 个安排：「{first_event.get('title', '待办事项')}」{start_time}"
                else:
                    body = f"下午有 {len(afternoon_events)} 个安排，首先是「{first_event.get('title', '待办事项')}」{start_time}"
            
            await notification_service.send_notification(
                user_id=user_id,
                payload=NotificationPayload(
                    title="☀️ 下午好",
                    body=body,
                    category="AFTERNOON_CHECKIN",
                    data={
                        "type": "afternoon_checkin",
                        "event_count": len(afternoon_events)
                    }
                ),
                notification_type=NotificationType.SUGGESTION,
                priority=NotificationPriority.NORMAL
            )
            
            print(f"[DailyNotification] Sent afternoon check-in to {user_id}")
            return True
            
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
            
            # 筛选生活类日程（更有价值的提醒）
            life_categories = ["LIFE", "SOCIAL", "HEALTH", "life", "social", "health"]
            life_events = [e for e in evening_events if e.get("category") in life_categories]
            
            if not life_events and not evening_events:
                if not force:
                    return False
                body = "这是晚间切换的测试通知（今晚暂无特定生活安排，好好休息～）"
                events_to_show = []
            else:
                # 构建通知内容
                events_to_show = life_events if life_events else evening_events
                first_event = events_to_show[0]
                
                if len(events_to_show) == 1:
                    body = f"今晚记得「{first_event.get('title', '待办事项')}」，好好享受生活～"
                else:
                    body = f"今晚有 {len(events_to_show)} 个安排，首先是「{first_event.get('title', '待办事项')}」"
            
            await notification_service.send_notification(
                user_id=user_id,
                payload=NotificationPayload(
                    title="🌙 晚上好",
                    body=body,
                    category="EVENING_SWITCH",
                    data={
                        "type": "evening_switch",
                        "event_count": len(events_to_show)
                    }
                ),
                notification_type=NotificationType.SUGGESTION,
                priority=NotificationPriority.NORMAL
            )
            
            print(f"[DailyNotification] Sent evening switch to {user_id}")
            return True
            
        except Exception as e:
            print(f"[DailyNotification] Error sending evening switch to {user_id}: {e}")
            return False
    
    # ==================== 睡前仪式 ====================
    
    async def send_closing_ritual(self, user_id: str, force: bool = False) -> bool:
        """
        🛌 睡前仪式
        
        核心差异点功能：
        1. 盘点今日完成情况
        2. 若全部完成 → 庆祝通知
        3. 若有未完成 → 智能决策辅助
        """
        try:
            settings = await self._get_user_notification_settings(user_id)
            if not settings.get("closing_ritual_enabled", True) and not force:
                return False
            
            # 获取今日任务完成情况
            today_events = await self._get_today_events(user_id)
            
            # 过滤出未完成的任务（排除已取消的）
            incomplete_tasks = [
                e for e in today_events 
                if e.get("status") not in ["COMPLETED", "CANCELLED", "completed", "cancelled"]
            ]
            
            completed_tasks = [
                e for e in today_events
                if e.get("status") in ["COMPLETED", "completed"]
            ]
            
            if not incomplete_tasks:
                # 完美一日！
                if completed_tasks:
                    body = f"今天完成了 {len(completed_tasks)} 个任务，太棒了！好好休息吧～"
                else:
                    body = "今天没有安排任务，轻松的一天！晚安～"
                
                await notification_service.send_notification(
                    user_id=user_id,
                    payload=NotificationPayload(
                        title="🎉 完美的一天！",
                        body=body,
                        category="CLOSING_RITUAL_PERFECT",
                        data={
                            "type": "closing_ritual",
                            "mode": "celebrate",
                            "completed_count": len(completed_tasks)
                        }
                    ),
                    notification_type=NotificationType.GREETING,
                    priority=NotificationPriority.NORMAL
                )
                
                print(f"[DailyNotification] Sent closing ritual (celebrate) to {user_id}")
                return True
            
            # 有未完成任务 → 智能决策辅助
            return await self._send_decision_advice(user_id, incomplete_tasks, settings)
            
        except Exception as e:
            print(f"[DailyNotification] Error sending closing ritual to {user_id}: {e}")
            return False
    
    async def _send_decision_advice(
        self, 
        user_id: str, 
        incomplete_tasks: List[Dict],
        settings: Dict
    ) -> bool:
        """
        智能决策辅助
        
        分析明日日程压力，决定建议模式：
        - Defer Mode（顺延）：明日日程空，任务不紧急
        - Sprint Mode（冲刺）：明日日程满，任务紧急
        """
        try:
            # 获取明日日程
            tomorrow_events = await self._get_tomorrow_events(user_id)
            tomorrow_busy = len(tomorrow_events) >= 5  # 简单阈值判断
            
            # 分析未完成任务紧急程度
            urgent_tasks = [t for t in incomplete_tasks if self._is_urgent(t)]
            
            # 计算预估完成时间
            estimated_minutes = sum(
                t.get("duration", 25) for t in incomplete_tasks[:2]
            )
            
            if not tomorrow_busy and not urgent_tasks:
                # Defer Mode - 顺延模式
                advice_mode = "defer"
                title = "🌙 今日盘点"
                body = f"还有 {len(incomplete_tasks)} 个任务未完成。明天比较空闲，建议顺延处理，今晚先好好休息～"
                actions = [
                    {"action": "defer_all", "title": "一键顺延"},
                    {"action": "view_tasks", "title": "查看任务"}
                ]
            else:
                # Sprint Mode - 冲刺模式
                advice_mode = "sprint"
                title = "🌙 今日盘点"
                
                if estimated_minutes <= 30:
                    body = f"还有 {len(incomplete_tasks)} 个任务，预计 {estimated_minutes} 分钟可完成。干完再睡？"
                else:
                    body = f"还有 {len(incomplete_tasks)} 个任务未完成。明天日程较满，建议现在速战速决～"
                
                actions = [
                    {"action": "start_sprint", "title": "干完再睡"},
                    {"action": "defer_all", "title": "明天再说"}
                ]
            
            await notification_service.send_notification(
                user_id=user_id,
                payload=NotificationPayload(
                    title=title,
                    body=body,
                    category="CLOSING_RITUAL_ADVICE",
                    data={
                        "type": "closing_ritual",
                        "mode": advice_mode,
                        "incomplete_task_ids": [t.get("id") for t in incomplete_tasks],
                        "incomplete_count": len(incomplete_tasks),
                        "estimated_minutes": estimated_minutes,
                        "actions": actions
                    }
                ),
                notification_type=NotificationType.SUGGESTION,
                priority=NotificationPriority.HIGH
            )
            
            print(f"[DailyNotification] Sent closing ritual ({advice_mode}) to {user_id}")
            return True
            
        except Exception as e:
            print(f"[DailyNotification] Error in decision advice: {e}")
            return False
    
    # ==================== 辅助方法 ====================
    
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
                
                # 如果截止时间在明天之前，视为紧急
                tomorrow = datetime.now() + timedelta(days=1)
                if deadline_dt < tomorrow:
                    return True
            except Exception:
                pass
        
        # 检查事件类型
        event_type = task.get("event_type", "").lower()
        if event_type in ["deadline", "appointment"]:
            return True
        
        # 检查高消耗任务（可能是重要任务）
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
