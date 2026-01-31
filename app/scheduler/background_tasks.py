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


class BackgroundTaskScheduler:
    """后台任务调度器（简化版）"""

    def __init__(self):
        self.scheduler: Optional[AsyncIOScheduler] = None

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
