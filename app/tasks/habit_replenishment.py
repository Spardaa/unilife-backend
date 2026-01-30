"""
Habit Replenishment Scheduled Task

This module handles automatic replenishment of habit instances to maintain
20 pending instances per active habit batch.
"""
import logging
from datetime import datetime
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.services.db import db_service
from app.config import settings

logger = logging.getLogger(__name__)

# Global scheduler instance
scheduler = AsyncIOScheduler()


async def replenish_habits():
    """
    Scheduled task to replenish habit instances

    Runs daily (default: 2 AM) to check all active habit batches
    and replenish instances that fall below 20.
    """
    logger.info("Starting habit replenishment task...")

    try:
        # Get all active habit batches that need replenishment
        active_batches = await db_service.get_active_habit_batches()

        replenished_count = 0

        for batch in active_batches:
            user_id = batch["user_id"]
            batch_id = batch["batch_id"]
            pending_count = batch["pending_count"]

            if pending_count < 20:
                # Get batch details
                batches = await db_service.get_habit_batches(user_id, active_only=True)
                batch_detail = next((b for b in batches if b["batch_id"] == batch_id), None)

                if not batch_detail:
                    logger.warning(f"Batch {batch_id} not found for user {user_id}")
                    continue

                # Get template event
                template = batch_detail["template"]

                # Calculate how many new instances we need
                needed = 20 - pending_count

                # Get the last event date to continue from
                events = await db_service.get_events(user_id=user_id, limit=1000)
                batch_events = [e for e in events if e.get("routine_batch_id") == batch_id]

                if batch_events:
                    # Find the last date
                    last_date = None
                    for event in sorted(batch_events, key=lambda e: e.get("event_date", ""), reverse=True):
                        if event.get("event_date"):
                            last_date = event["event_date"]
                            if isinstance(last_date, str):
                                from datetime import datetime
                                last_date = datetime.fromisoformat(last_date.replace('Z', '+00:00'))
                            break

                    if last_date:
                        # Calculate next dates
                        interval = template.get("habit_interval", 1)
                        from datetime import timedelta
                        next_dates = [last_date + timedelta(days=interval * (i + 1)) for i in range(needed)]

                        # Create new instances
                        template_data = {
                            "title": template.get("title"),
                            "description": template.get("description"),
                            "event_type": "habit",
                            "category": template.get("category"),
                            "duration": template.get("duration"),
                            "tags": template.get("tags", []),
                            "location": template.get("location"),
                            "participants": template.get("participants", []),
                            "energy_consumption": template.get("energy_consumption"),
                            "is_physically_demanding": template.get("is_physically_demanding", False),
                            "is_mentally_demanding": template.get("is_mentally_demanding", False),
                        }

                        new_instances = await db_service.create_habit_instances(
                            batch_id=batch_id,
                            dates=next_dates,
                            user_id=user_id,
                            template_event=template_data
                        )

                        logger.info(f"Replenished {len(new_instances)} instances for batch {batch_id}")
                        replenished_count += 1

        logger.info(f"Habit replenishment completed. Replenished {replenished_count} batches.")

    except Exception as e:
        logger.error(f"Error in habit replenishment: {str(e)}")


def start_scheduler():
    """Start the habit replenishment scheduler"""
    # Schedule to run daily at 2 AM
    scheduler.add_job(
        replenish_habits,
        'cron',
        hour=2,
        minute=0,
        id='habit_replenishment',
        replace_existing=True
    )

    scheduler.start()
    logger.info("Habit replenishment scheduler started (runs daily at 2 AM)")


def stop_scheduler():
    """Stop the habit replenishment scheduler"""
    if scheduler.running:
        scheduler.shutdown()
        logger.info("Habit replenishment scheduler stopped")
