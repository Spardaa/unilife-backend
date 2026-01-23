"""
Background Tasks - 定时任务调度器
使用 APScheduler 实现定时任务
"""
from typing import Optional
from datetime import datetime, date, timedelta
import asyncio

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from app.agents.daily_diary_generator import daily_diary_generator
from app.services.profile_refinement_service import profile_refinement_service
from app.services.diary_service import diary_service


class BackgroundTaskScheduler:
    """后台任务调度器"""

    def __init__(self):
        self.scheduler: Optional[AsyncIOScheduler] = None

    def start(self):
        """启动调度器"""
        if self.scheduler and self.scheduler.running:
            print("[Scheduler] Already running, skipping...")
            return

        print("[Scheduler] Starting background task scheduler...")

        # 创建调度器
        self.scheduler = AsyncIOScheduler()

        # ==================== 定时任务配置 ====================

        # 每日凌晨 3:00 生成前一天的用户日记
        self.scheduler.add_job(
            self._generate_daily_diaries,
            trigger=CronTrigger(hour=3, minute=0),
            id="generate_daily_diaries",
            name="Generate Daily User Diaries",
            replace_existing=True
        )

        # 每日凌晨 3:15 分析用户画像（基于前一天日记）
        self.scheduler.add_job(
            self._analyze_daily_profiles,
            trigger=CronTrigger(hour=3, minute=15),
            id="analyze_daily_profiles",
            name="Analyze Daily User Profiles",
            replace_existing=True
        )

        # 每周日凌晨 4:00 深度分析用户画像（基于过去7天日记）
        self.scheduler.add_job(
            self._analyze_weekly_profiles,
            trigger=CronTrigger(day_of_week='sun', hour=4, minute=0),
            id="analyze_weekly_profiles",
            name="Analyze Weekly User Profiles",
            replace_existing=True
        )

        # 启动调度器
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

    async def _generate_daily_diaries(self):
        """
        每日日记生成任务

        为所有有前一天对话的用户生成日记
        """
        print(f"[Scheduler] Running daily diary generation at {datetime.now()}")

        try:
            # 获取目标日期（昨天）
            target_date = date.today() - timedelta(days=1)

            # TODO: 获取所有有前一天对话的用户列表
            # 当前简化实现：使用固定用户ID列表
            # 实际应该从 conversations 表查询有对话的用户
            user_ids = self._get_active_users_for_date(target_date)

            generated_count = 0
            skipped_count = 0
            failed_count = 0

            for user_id in user_ids:
                try:
                    result = await daily_diary_generator.generate_daily_diary(
                        user_id=user_id,
                        target_date=target_date
                    )

                    if result.get("success"):
                        if result.get("skipped"):
                            skipped_count += 1
                        else:
                            generated_count += 1
                            print(f"[Scheduler] Generated diary for user {user_id} on {target_date}")
                    else:
                        failed_count += 1
                        print(f"[Scheduler] Failed to generate diary for user {user_id}: {result.get('reason')}")

                except Exception as e:
                    failed_count += 1
                    print(f"[Scheduler] Error generating diary for user {user_id}: {e}")

            print(f"[Scheduler] Daily diary generation completed: "
                  f"{generated_count} generated, {skipped_count} skipped, {failed_count} failed")

        except Exception as e:
            print(f"[Scheduler] Error in daily diary generation task: {e}")

    async def _analyze_daily_profiles(self):
        """
        每日画像分析任务

        分析前一天的日记，更新用户画像
        """
        print(f"[Scheduler] Running daily profile analysis at {datetime.now()}")

        try:
            # 获取目标日期（昨天）
            target_date = date.today() - timedelta(days=1)

            # 获取所有有前一天日记的用户
            user_ids = self._get_users_with_diary(target_date)

            analyzed_count = 0
            failed_count = 0

            for user_id in user_ids:
                try:
                    log = await profile_refinement_service.analyze_daily_profile(
                        user_id=user_id,
                        target_date=target_date
                    )

                    if log.status.value == "completed":
                        analyzed_count += 1
                        print(f"[Scheduler] Analyzed profile for user {user_id}")
                    else:
                        failed_count += 1
                        print(f"[Scheduler] Failed to analyze profile for user {user_id}: {log.error_message}")

                except Exception as e:
                    failed_count += 1
                    print(f"[Scheduler] Error analyzing profile for user {user_id}: {e}")

            print(f"[Scheduler] Daily profile analysis completed: "
                  f"{analyzed_count} analyzed, {failed_count} failed")

        except Exception as e:
            print(f"[Scheduler] Error in daily profile analysis task: {e}")

    async def _analyze_weekly_profiles(self):
        """
        每周画像深度分析任务

        分析过去7天的日记，进行全面的画像更新
        """
        print(f"[Scheduler] Running weekly profile analysis at {datetime.now()}")

        try:
            # 获取结束日期（昨天）
            end_date = date.today() - timedelta(days=1)

            # 获取所有有过去7天日记的用户
            start_date = end_date - timedelta(days=6)
            user_ids = self._get_users_with_diaries_in_period(start_date, end_date)

            analyzed_count = 0
            failed_count = 0

            for user_id in user_ids:
                try:
                    log = await profile_refinement_service.analyze_weekly_profile(
                        user_id=user_id,
                        end_date=end_date
                    )

                    if log.status.value == "completed":
                        analyzed_count += 1
                        print(f"[Scheduler] Weekly profile analyzed for user {user_id}")
                    else:
                        failed_count += 1
                        print(f"[Scheduler] Failed weekly analysis for user {user_id}: {log.error_message}")

                except Exception as e:
                    failed_count += 1
                    print(f"[Scheduler] Error in weekly analysis for user {user_id}: {e}")

            print(f"[Scheduler] Weekly profile analysis completed: "
                  f"{analyzed_count} analyzed, {failed_count} failed")

        except Exception as e:
            print(f"[Scheduler] Error in weekly profile analysis task: {e}")

    def _get_active_users_for_date(self, target_date: date) -> list[str]:
        """
        获取指定日期有对话的用户列表

        TODO: 实际应该从 conversations 表查询
        """
        # 简化实现：从数据库查询
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

    def _get_users_with_diary(self, target_date: date) -> list[str]:
        """获取指定日期有日记的用户列表"""
        from sqlalchemy import create_engine, text
        from app.config import settings

        db_path = settings.database_url.replace("sqlite:///", "")
        engine = create_engine(f"sqlite:///{db_path}")

        with engine.connect() as conn:
            result = conn.execute(
                text("""SELECT DISTINCT user_id FROM user_diaries
                       WHERE diary_date = :date"""),
                {"date": target_date.isoformat()}
            ).fetchall()

            return [row[0] for row in result]

    def _get_users_with_diaries_in_period(self, start_date: date, end_date: date) -> list[str]:
        """获取指定时间段有日记的用户列表"""
        from sqlalchemy import create_engine, text
        from app.config import settings

        db_path = settings.database_url.replace("sqlite:///", "")
        engine = create_engine(f"sqlite:///{db_path}")

        with engine.connect() as conn:
            result = conn.execute(
                text("""SELECT DISTINCT user_id FROM user_diaries
                       WHERE diary_date >= :start AND diary_date <= :end"""),
                {"start": start_date.isoformat(), "end": end_date.isoformat()}
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
