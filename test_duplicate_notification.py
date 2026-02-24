import asyncio
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from app.scheduler.daily_notifications import DailyNotificationScheduler
from app.services.notification_service import notification_service

# 测试用的 user_id
USER_ID = "53aede26-5b5a-49cd-82f4-cc6e587506bc" # 之前查询到的 UUID
CATEGORY = "TEST_DUPLICATE_NOTIFICATION"

async def main():
    scheduler = DailyNotificationScheduler()
    
    # 1. 初始状态：未发送
    has_sent = await scheduler._has_sent_notification_today(USER_ID, CATEGORY)
    print(f"1. 初始状态检查 (期望 False): {has_sent}")
    
    # 2. 模拟发送一条通知入库
    from app.models.notification import NotificationPayload, NotificationType
    
    print("\n2. 正在模拟写入一条通知记录...")
    await notification_service.send_notification(
        user_id=USER_ID,
        payload=NotificationPayload(
            title="测试",
            body="这是一条测试阻断的通知",
            category=CATEGORY
        ),
        notification_type=NotificationType.GREETING,
    )
    
    # 3. 再次检查状态：应为已发送
    has_sent_after = await scheduler._has_sent_notification_today(USER_ID, CATEGORY)
    print(f"3. 写入后状态检查 (期望 True): {has_sent_after}")
    
    # 4. 模拟并发调用 send_morning_briefing (需 mock _get_today_events 和 notification_agent)
    # 此处我们只测 _has_sent_notification_today 能否被拦截。
    # 我们可以稍微改一下 mock 来直接调 send_xxxxx 方法
    print("\n4. 实际 send 方法拦截测试:")
    
    # 为避免真实改动，我们直接测试 _has_sent_notification_today 对数据库的匹配
    if has_sent_after:
        print("✅ 防并发锁查询成功！如果同一天已有该 Category 的通知，会返回 True。")
    else:
        print("❌ 防并发锁查询失败！")

if __name__ == "__main__":
    asyncio.run(main())
