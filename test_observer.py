import asyncio
import os
import sys

# 确保能找到 app 模块
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from app.scheduler.background_tasks import BackgroundTaskScheduler
from app.agents.observer import observer_agent

original_write = observer_agent.write_daily_diary
async def wrapped_write(*args, **kwargs):
    print(f"--> [DEBUG] calling write_daily_diary({args}, {kwargs})")
    res = await original_write(*args, **kwargs)
    print(f"<-- [DEBUG] write_daily_diary result: {res}")
    return res

observer_agent.write_daily_diary = wrapped_write

async def main():
    scheduler = BackgroundTaskScheduler()
    print("\nTesting Daily Diary Writing...")
    await scheduler._write_daily_diaries()

if __name__ == "__main__":
    asyncio.run(main())
