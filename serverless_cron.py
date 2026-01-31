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


def daily_profile_analyzer(event, context):
    """
    每日偏好分析任务

    触发时间：每日凌晨 3:00
    Cron 表达式：0 0 3 * * * *

    功能：分析有对话记录的用户，更新偏好设置
    """
    import asyncio

    print(f"[Cron] Daily profile analysis started at {datetime.now()}")

    try:
        target_date = date.today() - 1
        user_ids = task_scheduler._get_active_users_for_date(target_date)

        print(f"[Cron] Found {len(user_ids)} users with conversations on {target_date}")

        analyzed_count = 0
        failed_count = 0

        for user_id in user_ids:
            try:
                # 触发 Observer 分析（简化版只更新偏好）
                conversations = task_scheduler._get_user_conversations(user_id, target_date)
                for conv_id in conversations[:5]:  # 最多分析5个对话
                    asyncio.run(observer_agent.analyze_conversation_batch(
                        conversation_id=conv_id,
                        user_id=user_id
                    ))
                analyzed_count += 1

            except Exception as e:
                failed_count += 1
                print(f"[Cron] Error analyzing user {user_id}: {e}")

        summary = {
            "task": "daily_profile_analysis",
            "target_date": target_date.isoformat(),
            "total_users": len(user_ids),
            "analyzed": analyzed_count,
            "failed": failed_count,
            "timestamp": datetime.now().isoformat()
        }

        print(f"[Cron] {summary}")
        return json_response(summary)

    except Exception as e:
        print(f"[Cron] Error in daily profile analysis: {e}")
        return json_response({
            "task": "daily_profile_analysis",
            "status": "error",
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        }, status_code=500)


# 保留旧函数名作为别名，保证兼容性
daily_diary_generator = daily_profile_analyzer
weekly_profile_analyzer = daily_profile_analyzer


# ==================== 本地测试入口 ====================

if __name__ == "__main__":
    print("=== 定时任务云函数本地测试 ===\n")
    print("测试：每日偏好分析...")

    mock_event = {}
    mock_context = {}

    result = daily_profile_analyzer(mock_event, mock_context)
    print(json.dumps(result, indent=2, ensure_ascii=False))
