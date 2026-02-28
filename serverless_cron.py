"""
定时任务云函数 (简化版)

适用平台：
- 腾讯云 SCF
- 阿里云 FC
- AWS Lambda
"""
import os
import json
from datetime import date, datetime

# 设置 Serverless 环境标识
os.environ["SERVERLESS"] = "true"

from app.scheduler.background_tasks import task_scheduler
from app.agents.observer import observer_agent


def json_response(data: dict, status_code: int = 200) -> dict:
    """构造 API 网关响应"""
    return {
        "statusCode": status_code,
        "headers": {
            "Content-Type": "application/json",
            "Access-Control-Allow-Origin": "*"
        },
        "body": json.dumps(data, ensure_ascii=False, default=str)
    }


def daily_observer_review(event, context):
    """
    每日观察者复盘任务

    触发时间：每日凌晨 3:00
    Cron 表达式：0 0 3 * * * *

    功能：分析有对话记录的用户，写日记并可能更新认知
    """
    import asyncio
    
    print(f"[Cron] Daily observer review started at {datetime.now()}")
    
    try:
        from datetime import timedelta
        target_date = date.today() - timedelta(days=1)
        user_ids = task_scheduler._get_active_users_for_date(target_date)

        print(f"[Cron] Found {len(user_ids)} users with conversations on {target_date}")

        reviewed_count = 0
        failed_count = 0

        for user_id in user_ids:
            try:
                # 触发统一的 Observer 复盘
                asyncio.run(observer_agent.daily_review(
                    user_id=user_id,
                    date_str=target_date.strftime("%Y-%m-%d")
                ))
                reviewed_count += 1
            except Exception as e:
                failed_count += 1
                print(f"[Cron] Error reviewing user {user_id}: {e}")

        summary = {
            "task": "daily_observer_review",
            "target_date": target_date.strftime("%Y-%m-%d"),
            "total_users": len(user_ids),
            "reviewed": reviewed_count,
            "failed": failed_count,
            "timestamp": datetime.now().isoformat()
        }

        print(f"[Cron] {summary}")
        return json_response(summary)

    except Exception as e:
        print(f"[Cron] Error in daily observer review: {e}")
        return json_response({
            "task": "daily_observer_review",
            "status": "error",
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        }, status_code=500)


def weekly_profile_analyzer(event, context):
    """每周记忆精炼任务"""
    import asyncio
    print(f"[Cron] Weekly memory consolidation started at {datetime.now()}")
    try:
        user_ids = task_scheduler._get_all_active_users()
        consolidated = 0
        failed = 0
        for user_id in user_ids:
            try:
                asyncio.run(observer_agent.consolidate_memory(user_id))
                consolidated += 1
            except Exception as e:
                failed += 1
                print(f"[Cron] Error consolidating memory for user {user_id}: {e}")

        summary = {
            "task": "weekly_memory_consolidation",
            "total_users": len(user_ids),
            "consolidated": consolidated,
            "failed": failed,
            "timestamp": datetime.now().isoformat()
        }
        print(f"[Cron] {summary}")
        return json_response(summary)
    except Exception as e:
        print(f"[Cron] Error in weekly memory consolidation: {e}")
        return json_response({
            "task": "weekly_memory_consolidation",
            "status": "error",
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        }, status_code=500)

# ==================== 本地测试入口 ====================

if __name__ == "__main__":
    print("=== 定时任务云函数本地测试 ===\n")
    print("测试：每日偏好分析...")

    mock_event = {}
    mock_context = {}

    result = daily_profile_analyzer(mock_event, mock_context)
    print(json.dumps(result, indent=2, ensure_ascii=False))
