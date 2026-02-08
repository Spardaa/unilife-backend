"""
Background Tasks - 定时任务调度器 (简化版)
使用 APScheduler 实现定时任务
"""
from typing import Optional, List
from datetime import datetime, date, timedelta
import asyncio

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from app.agents.observer import observer_agent
from app.scheduler.daily_notifications import daily_notification_scheduler


class BackgroundTaskScheduler:
    """后台任务调度器（简化版）"""

    def __init__(self):
        self.scheduler: Optional[AsyncIOScheduler] = None
        self.notification_scheduler = daily_notification_scheduler

    def start(self):
        """启动调度器"""
        if self.scheduler and self.scheduler.running:
            print("[Scheduler] Already running, skipping...")
            return

        print("[Scheduler] Starting background task scheduler...")

        self.scheduler = AsyncIOScheduler()

        # 每日凌晨 3:00 分析用户偏好
        self.scheduler.add_job(
            self._analyze_daily_preferences,
            trigger=CronTrigger(hour=3, minute=0),
            id="analyze_daily_preferences",
            name="Analyze Daily User Preferences",
            replace_existing=True
        )
        
        # 每分钟检查并发送用户个性化通知
        self.scheduler.add_job(
            self._check_and_send_notifications,
            trigger=CronTrigger(minute="*"),  # 每分钟
            id="check_user_notifications",
            name="Check and Send User Notifications",
            replace_existing=True
        )
        
        # 每分钟处理待发送的定时通知(Event Reminders)
        self.scheduler.add_job(
            self._process_pending_notifications,
            trigger=CronTrigger(minute="*"),  # 每分钟
            id="process_pending_notifications",
            name="Process Pending Notifications",
            replace_existing=True
        )
        
        # 每分钟检查即将开始的事件并发送提醒
        self.scheduler.add_job(
            self._check_event_reminders,
            trigger=CronTrigger(minute="*"),  # 每分钟
            id="check_event_reminders",
            name="Check Event Reminders",
            replace_existing=True
        )

        self.scheduler.start()
        print("[Scheduler] Background tasks scheduler started successfully")
        print("[Scheduler] Scheduled jobs:")
        for job in self.scheduler.get_jobs():
            print(f"  - {job.name} (ID: {job.id}, Next run: {job.next_run_time})")

    def stop(self):
        """停止调度器"""
        if self.scheduler and self.scheduler.running:
            print("[Scheduler] Stopping background task scheduler...")
            self.scheduler.shutdown(wait=False)
            print("[Scheduler] Scheduler stopped")

    async def _analyze_daily_preferences(self):
        """每日偏好分析任务"""
        print(f"[Scheduler] Running daily preference analysis at {datetime.now()}")

        try:
            target_date = date.today() - timedelta(days=1)
            user_ids = self._get_active_users_for_date(target_date)

            analyzed_count = 0
            failed_count = 0

            for user_id in user_ids:
                try:
                    conversations = self._get_user_conversations(user_id, target_date)
                    for conv_id in conversations[:5]:
                        await observer_agent.analyze_conversation_batch(
                            conversation_id=conv_id,
                            user_id=user_id
                        )
                    analyzed_count += 1
                    print(f"[Scheduler] Analyzed preferences for user {user_id}")

                except Exception as e:
                    failed_count += 1
                    print(f"[Scheduler] Error analyzing user {user_id}: {e}")

            print(f"[Scheduler] Daily preference analysis completed: "
                  f"{analyzed_count} analyzed, {failed_count} failed")

        except Exception as e:
            print(f"[Scheduler] Error in daily preference analysis task: {e}")

    async def _check_and_send_notifications(self):
        """
        每分钟检查所有用户的通知时间点
        
        由于每个用户的作息时间不同，需要逐个检查
        """
        current_time = datetime.now()
        current_hm = current_time.strftime("%H:%M")
        
        # 只在整分钟时记录日志，避免刷屏
        if current_time.second < 5:
            print(f"[Scheduler] Checking notifications at {current_hm}")
        
        try:
            # 获取所有活跃用户
            user_ids = self._get_all_active_users()
            
            for user_id in user_ids:
                await self._check_user_notifications(user_id, current_hm)
                
        except Exception as e:
            print(f"[Scheduler] Error checking notifications: {e}")
    
    async def _process_pending_notifications(self):
        """处理待发送的通知"""
        try:
            from app.services.notification_service import notification_service
            await notification_service.process_pending_notifications()
        except Exception as e:
            print(f"[Scheduler] Error processing pending notifications: {e}")

    async def _check_event_reminders(self):
        """
        检查即将开始的事件并发送提醒通知
        
        时区处理说明：
        - 数据库中 start_time 存储的是本地时间 (Asia/Shanghai) 的 naive datetime
        - datetime.now() 也是本地 naive datetime
        - 因此可以直接比较，无需时区转换
        
        逻辑：
        1. 查询当天/明天有 start_time 的事件
        2. 在 Python 中精确计算时间差
        3. 检查用户是否开启了事件提醒
        4. 避免重复发送
        5. 发送 event_reminder 通知
        """
        current_time = datetime.now()
        today_str = current_time.strftime("%Y-%m-%d")
        tomorrow_str = (current_time + timedelta(days=1)).strftime("%Y-%m-%d")
        
        try:
            from sqlalchemy import create_engine, text
            from app.config import settings
            from app.services.notification_service import notification_service
            from app.services.profile_service import profile_service
            from app.models.notification import NotificationType, NotificationPriority, NotificationPayload
            
            db_path = settings.database_url.replace("sqlite:///", "")
            engine = create_engine(f"sqlite:///{db_path}")
            
            with engine.connect() as conn:
                # 查询今天或明天有 start_time 的未完成事件
                # 用 LIKE 匹配日期字符串前缀，避免 SQLite datetime() 的解析问题
                result = conn.execute(
                    text("""
                        SELECT e.id, e.user_id, e.title, e.start_time, e.event_date, u.user_id as profile_user_id
                        FROM events e
                        LEFT JOIN users u ON e.user_id = u.id
                        WHERE (e.start_time LIKE :today_pattern OR e.start_time LIKE :tomorrow_pattern)
                        AND e.status IN ('pending', 'in_progress', 'PENDING', 'IN_PROGRESS')
                        AND e.event_type != 'routine'
                        AND e.is_template = 0
                    """),
                    {
                        "today_pattern": f"{today_str}%",
                        "tomorrow_pattern": f"{tomorrow_str}%"
                    }
                ).fetchall()
                
                if not result:
                    return
                
                events_to_remind = []
                
                for row in result:
                    event_id, user_uuid, title, start_time_raw, event_date, profile_user_id = row
                    
                    # 使用 profile_user_id (例如 "001762...") 查找配置，因为这是前端更新配置时使用的 ID
                    # 如果没有，则回退到 user_uuid
                    target_user_id = profile_user_id if profile_user_id else user_uuid
                    
                    try:
                        # 解析事件开始时间
                        event_start = self._parse_start_time(start_time_raw)
                        if not event_start:
                            continue
                        
                        # 获取用户提醒设置
                        profile = profile_service.get_or_create_profile(target_user_id)
                        prefs = profile.preferences
                        
                        reminder_minutes = prefs.get("event_reminder_minutes", 15)
                        
                        # 计算距离事件开始的分钟数
                        time_diff = (event_start - current_time).total_seconds() / 60
                        
                        if not prefs.get("event_reminders_enabled", True):
                            continue
                        
                        # 检查是否应该发送提醒：
                        # - 只在 (reminder_minutes - 1, reminder_minutes] 范围内触发一次
                        # - 例如：设置15分钟提醒，只在 14-15 分钟时触发（调度器每分钟检查一次）
                        # - 这确保每个事件只在一个时间窗口内触发一次
                        if time_diff > 0 and (reminder_minutes - 1) < time_diff <= reminder_minutes:
                            # 先检查是否已发送过提醒（在构建列表前就去重）
                            already_sent = conn.execute(
                                text("""
                                    SELECT id FROM notifications 
                                    WHERE user_id = :user_id 
                                    AND type = 'event_reminder'
                                    AND payload LIKE :event_pattern
                                    AND created_at >= :today_start
                                """),
                                {
                                    "user_id": user_uuid,
                                    "event_pattern": f'%{event_id}%',
                                    "today_start": current_time.replace(hour=0, minute=0, second=0).isoformat()
                                }
                            ).fetchone()
                            
                            if already_sent:
                                continue
                                
                            events_to_remind.append({
                                "event_id": event_id,
                                "user_id": user_uuid,
                                "title": title,
                                "reminder_minutes": reminder_minutes,
                                "minutes_until": round(time_diff)
                            })
                            
                    except Exception as e:
                        print(f"[Scheduler] Error parsing event {event_id}: {e}")
                
                if not events_to_remind:
                    return
                    
                print(f"[Scheduler] Found {len(events_to_remind)} events needing reminders")
                
                for event in events_to_remind:
                    try:
                        # 发送提醒通知
                        print(f"[Scheduler] Sending event reminder: '{event['title']}' in {event['minutes_until']} min (user: {event['user_id'][:8]}...)")
                        
                        await notification_service.send_notification(
                            user_id=event["user_id"],
                            payload=NotificationPayload(
                                title="⏰ 日程提醒",
                                body=f"「{event['title']}」将在 {event['minutes_until']} 分钟后开始",
                                category="EVENT_REMINDER",
                                data={
                                    "type": "event_reminder",
                                    "event_id": event["event_id"],
                                    "action": "open_event",
                                    "minutes_before": event["reminder_minutes"]
                                }
                            ),
                            notification_type=NotificationType.EVENT_REMINDER,
                            priority=NotificationPriority.HIGH
                        )
                        
                    except Exception as e:
                        print(f"[Scheduler] Error sending reminder for event {event['event_id']}: {e}")
                        
        except Exception as e:
            print(f"[Scheduler] Error checking event reminders: {e}")
    
    def _parse_start_time(self, start_time_raw) -> datetime:
        """
        解析 start_time，处理各种可能的格式
        
        数据库中可能的格式：
        - datetime 对象
        - "2026-02-08 15:30:00.000000" (SQLite 存储格式)
        - "2026-02-08T15:30:00" (ISO 格式)
        - "2026-02-08T15:30:00Z" (UTC ISO 格式)
        - "2026-02-08T15:30:00+08:00" (带时区 ISO 格式)
        """
        if start_time_raw is None:
            return None
            
        if isinstance(start_time_raw, datetime):
            # 如果已经是 datetime，去掉时区信息（确保是 naive）
            return start_time_raw.replace(tzinfo=None) if start_time_raw.tzinfo else start_time_raw
        
        if isinstance(start_time_raw, str):
            try:
                # 尝试各种格式
                time_str = start_time_raw.strip()
                
                # 处理带时区后缀的情况
                if time_str.endswith('Z'):
                    time_str = time_str[:-1] + '+00:00'
                
                # 尝试 fromisoformat（支持多种 ISO 格式）
                try:
                    parsed = datetime.fromisoformat(time_str)
                    if parsed.tzinfo:
                        # 有时区信息，转换为本地时间
                        import pytz
                        local_tz = pytz.timezone("Asia/Shanghai")
                        parsed = parsed.astimezone(local_tz).replace(tzinfo=None)
                    return parsed
                except ValueError:
                    pass
                
                # 尝试 SQLite 存储格式
                for fmt in ["%Y-%m-%d %H:%M:%S.%f", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M"]:
                    try:
                        return datetime.strptime(time_str, fmt)
                    except ValueError:
                        continue
                        
            except Exception as e:
                print(f"[Scheduler] Failed to parse start_time '{start_time_raw}': {e}")
                
        return None

    async def _check_user_notifications(self, user_id: str, current_hm: str):
        """检查单个用户的通知时间点"""
        try:
            # 获取用户设置
            from app.services.profile_service import profile_service
            profile = profile_service.get_or_create_profile(user_id)
            settings = profile.preferences
            
            wake_time = settings.get("wake_time", "08:00")
            sleep_time = settings.get("sleep_time", "22:00")
            
            # 早安简报 - 用户起床时间
            if current_hm == wake_time:
                await self.notification_scheduler.send_morning_briefing(user_id)
            
            # 午间检查 - 固定 12:00
            if current_hm == "12:00":
                await self.notification_scheduler.send_afternoon_checkin(user_id)
            
            # 晚间切换 - 固定 18:00
            if current_hm == "18:00":
                await self.notification_scheduler.send_evening_switch(user_id)
            
            # 睡前仪式 - 睡觉时间前15分钟
            ritual_time = self._subtract_minutes(sleep_time, 15)
            if current_hm == ritual_time:
                await self.notification_scheduler.send_closing_ritual(user_id)
                
        except Exception as e:
            print(f"[Scheduler] Error checking notifications for {user_id}: {e}")
    
    def _subtract_minutes(self, time_str: str, minutes: int) -> str:
        """从时间字符串减去指定分钟数"""
        try:
            parts = time_str.split(":")
            hour = int(parts[0])
            minute = int(parts[1])
            
            total_minutes = hour * 60 + minute - minutes
            if total_minutes < 0:
                total_minutes += 24 * 60  # 处理跨天
            
            new_hour = total_minutes // 60
            new_minute = total_minutes % 60
            
            return f"{new_hour:02d}:{new_minute:02d}"
        except Exception:
            return time_str
    
    def _get_all_active_users(self) -> List[str]:
        """获取所有活跃用户（7天内有活动）"""
        from sqlalchemy import create_engine, text
        from app.config import settings
        
        try:
            db_path = settings.database_url.replace("sqlite:///", "")
            engine = create_engine(f"sqlite:///{db_path}")
            
            with engine.connect() as conn:
                # 获取7天内有活动的用户
                seven_days_ago = (datetime.now() - timedelta(days=7)).isoformat()
                
                result = conn.execute(
                    text("""SELECT DISTINCT user_id FROM users
                           WHERE last_active_at >= :since OR created_at >= :since"""),
                    {"since": seven_days_ago}
                ).fetchall()
                
                return [row[0] for row in result if row[0]]
        except Exception as e:
            print(f"[Scheduler] Error getting active users: {e}")
            return []


    def _get_active_users_for_date(self, target_date: date) -> List[str]:
        """获取指定日期有对话的用户列表"""
        from sqlalchemy import create_engine, text
        from app.config import settings

        db_path = settings.database_url.replace("sqlite:///", "")
        engine = create_engine(f"sqlite:///{db_path}")

        with engine.connect() as conn:
            start_datetime = datetime.combine(target_date, datetime.min.time())
            end_datetime = datetime.combine(target_date, datetime.max.time())

            result = conn.execute(
                text("""SELECT DISTINCT user_id FROM conversations
                       WHERE created_at >= :start AND created_at <= :end"""),
                {"start": start_datetime.isoformat(), "end": end_datetime.isoformat()}
            ).fetchall()

            return [row[0] for row in result]

    def _get_user_conversations(self, user_id: str, target_date: date) -> List[str]:
        """获取用户在指定日期的对话ID列表"""
        from sqlalchemy import create_engine, text
        from app.config import settings

        db_path = settings.database_url.replace("sqlite:///", "")
        engine = create_engine(f"sqlite:///{db_path}")

        with engine.connect() as conn:
            start_datetime = datetime.combine(target_date, datetime.min.time())
            end_datetime = datetime.combine(target_date, datetime.max.time())

            result = conn.execute(
                text("""SELECT id FROM conversations
                       WHERE user_id = :user_id 
                       AND created_at >= :start AND created_at <= :end"""),
                {
                    "user_id": user_id,
                    "start": start_datetime.isoformat(),
                    "end": end_datetime.isoformat()
                }
            ).fetchall()

            return [row[0] for row in result]

    def get_job_status(self) -> dict:
        """获取调度器状态"""
        if not self.scheduler:
            return {"running": False, "jobs": []}

        return {
            "running": self.scheduler.running,
            "jobs": [
                {
                    "id": job.id,
                    "name": job.name,
                    "next_run_time": job.next_run_time.isoformat() if job.next_run_time else None
                }
                for job in self.scheduler.get_jobs()
            ]
        }


# 全局调度器实例
task_scheduler = BackgroundTaskScheduler()
