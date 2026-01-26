"""
定时任务云函数

将原有的后台任务调度器改为独立的云函数，
使用云平台的定时触发器来执行。

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
from app.services.profile_refinement_service import profile_refinement_service


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


def daily_diary_generator(event, context):
    """
    每日日记生成任务

    触发时间：每日凌晨 3:00
    Cron 表达式：0 0 3 * * * *

    功能：为有前一天对话的用户生成日记
    """
    import asyncio

    print(f"[Cron] Daily diary generation started at {datetime.now()}")

    try:
        # 获取目标日期（昨天）
        target_date = date.today() - 1

        # 获取有对话的用户列表
        user_ids = task_scheduler._get_active_users_for_date(target_date)

        print(f"[Cron] Found {len(user_ids)} users with conversations on {target_date}")

        generated_count = 0
        skipped_count = 0
        failed_count = 0
        results = []

        for user_id in user_ids:
            try:
                result = asyncio.run(observer_agent.generate_daily_diary(
                    user_id=user_id,
                    target_date=target_date
                ))

                if result.get("success"):
                    if result.get("skipped"):
                        skipped_count += 1
                    else:
                        generated_count += 1
                        results.append({"user_id": user_id, "status": "generated"})
                else:
                    failed_count += 1
                    results.append({"user_id": user_id, "status": "failed", "reason": result.get("reason")})

            except Exception as e:
                failed_count += 1
                print(f"[Cron] Error generating diary for user {user_id}: {e}")
                results.append({"user_id": user_id, "status": "error", "error": str(e)})

        summary = {
            "task": "daily_diary_generation",
            "target_date": target_date.isoformat(),
            "total_users": len(user_ids),
            "generated": generated_count,
            "skipped": skipped_count,
            "failed": failed_count,
            "timestamp": datetime.now().isoformat()
        }

        print(f"[Cron] {summary}")

        return json_response(summary)

    except Exception as e:
        print(f"[Cron] Error in daily diary generation: {e}")
        return json_response({
            "task": "daily_diary_generation",
            "status": "error",
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        }, status_code=500)


def daily_profile_analyzer(event, context):
    """
    每日画像分析任务

    触发时间：每日凌晨 3:15
    Cron 表达式：0 15 3 * * * *

    功能：分析前一天的日记，更新用户画像
    """
    import asyncio

    print(f"[Cron] Daily profile analysis started at {datetime.now()}")

    try:
        # 获取目标日期（昨天）
        target_date = date.today() - 1

        # 获取有日记的用户列表
        user_ids = task_scheduler._get_users_with_diary(target_date)

        print(f"[Cron] Found {len(user_ids)} users with diaries on {target_date}")

        analyzed_count = 0
        failed_count = 0
        results = []

        for user_id in user_ids:
            try:
                log = asyncio.run(profile_refinement_service.analyze_daily_profile(
                    user_id=user_id,
                    target_date=target_date
                ))

                if log.status.value == "completed":
                    analyzed_count += 1
                    results.append({"user_id": user_id, "status": "analyzed"})
                else:
                    failed_count += 1
                    results.append({"user_id": user_id, "status": "failed", "error": log.error_message})

            except Exception as e:
                failed_count += 1
                print(f"[Cron] Error analyzing profile for user {user_id}: {e}")
                results.append({"user_id": user_id, "status": "error", "error": str(e)})

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


def weekly_profile_analyzer(event, context):
    """
    每周画像深度分析任务

    触发时间：每周日凌晨 4:00
    Cron 表达式：0 0 4 ? * 1 *

    功能：分析过去7天的日记，进行全面的画像更新
    """
    import asyncio

    print(f"[Cron] Weekly profile analysis started at {datetime.now()}")

    try:
        # 获取结束日期（昨天）
        end_date = date.today() - 1
        start_date = end_date - 6  # 过去7天

        # 获取有日记的用户列表
        user_ids = task_scheduler._get_users_with_diaries_in_period(start_date, end_date)

        print(f"[Cron] Found {len(user_ids)} users with diaries in the past week")

        analyzed_count = 0
        failed_count = 0
        results = []

        for user_id in user_ids:
            try:
                log = asyncio.run(profile_refinement_service.analyze_weekly_profile(
                    user_id=user_id,
                    end_date=end_date
                ))

                if log.status.value == "completed":
                    analyzed_count += 1
                    results.append({"user_id": user_id, "status": "analyzed"})
                else:
                    failed_count += 1
                    results.append({"user_id": user_id, "status": "failed", "error": log.error_message})

            except Exception as e:
                failed_count += 1
                print(f"[Cron] Error in weekly analysis for user {user_id}: {e}")
                results.append({"user_id": user_id, "status": "error", "error": str(e)})

        summary = {
            "task": "weekly_profile_analysis",
            "period": {
                "start": start_date.isoformat(),
                "end": end_date.isoformat()
            },
            "total_users": len(user_ids),
            "analyzed": analyzed_count,
            "failed": failed_count,
            "timestamp": datetime.now().isoformat()
        }

        print(f"[Cron] {summary}")

        return json_response(summary)

    except Exception as e:
        print(f"[Cron] Error in weekly profile analysis: {e}")
        return json_response({
            "task": "weekly_profile_analysis",
            "status": "error",
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        }, status_code=500)


# ==================== 本地测试入口 ====================

if __name__ == "__main__":
    print("=== 定时任务云函数本地测试 ===\n")

    print("选择要测试的任务:")
    print("1. 每日日记生成 (daily_diary_generator)")
    print("2. 每日画像分析 (daily_profile_analyzer)")
    print("3. 每周画像深度分析 (weekly_profile_analyzer)")

    choice = input("\n请输入选项 (1/2/3): ").strip()

    # 模拟云函数事件和上下文
    mock_event = {}
    mock_context = {}

    if choice == "1":
        print("\n测试：每日日记生成...")
        result = daily_diary_generator(mock_event, mock_context)
        print(json.dumps(result, indent=2, ensure_ascii=False))

    elif choice == "2":
        print("\n测试：每日画像分析...")
        result = daily_profile_analyzer(mock_event, mock_context)
        print(json.dumps(result, indent=2, ensure_ascii=False))

    elif choice == "3":
        print("\n测试：每周画像深度分析...")
        result = weekly_profile_analyzer(mock_event, mock_context)
        print(json.dumps(result, indent=2, ensure_ascii=False))

    else:
        print("无效的选项")
