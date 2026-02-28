import asyncio
from datetime import datetime
import serverless_cron

print("Testing daily_diary_generator...")
result = serverless_cron.daily_diary_generator({}, {})
print("Result:", result)

print("\nTesting daily_profile_analyzer...")
result2 = serverless_cron.daily_profile_analyzer({}, {})
print("Result:", result2)

print("\nTesting weekly_profile_analyzer...")
result3 = serverless_cron.weekly_profile_analyzer({}, {})
print("Result:", result3)
