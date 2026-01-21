"""
测试增强功能 - 精力评估、用户画像、快照系统
"""
import sys
import asyncio
sys.path.append(".")

from datetime import datetime
from app.agents.energy_evaluator import energy_evaluator_agent
from app.agents.smart_scheduler import smart_scheduler_agent
from app.agents.context_extractor import context_extractor_agent
from app.services.profile_service import profile_service


async def test_energy_system():
    """测试精力评估系统"""
    print("=" * 60)
    print("Test 1: Energy Consumption Evaluation")
    print("=" * 60)
    print()

    events_to_evaluate = [
        {
            "title": "搬运办公室设备",
            "description": "将三楼办公室的电脑、打印机等设备搬运到一楼仓库",
            "duration": "2小时",
            "location": "办公室"
        },
        {
            "title": "编程开发新功能",
            "description": "设计和实现新的用户认证模块",
            "duration": "4小时",
            "location": "工位"
        },
        {
            "title": "团队周会",
            "description": "讨论本周项目进度和下周计划",
            "duration": "1小时",
            "location": "会议室"
        }
    ]

    for event in events_to_evaluate:
        print(f"Evaluating: {event['title']}")
        evaluation = await energy_evaluator_agent.evaluate(event)

        print(f"  Physical: {evaluation.physical.level} ({evaluation.physical.score}/10)")
        print(f"    {evaluation.physical.description}")
        print(f"  Mental: {evaluation.mental.level} ({evaluation.mental.score}/10)")
        print(f"    {evaluation.mental.description}")
        print()

    print("[OK] Energy evaluation test completed")


async def test_smart_scheduler():
    """测试智能调度系统"""
    print("=" * 60)
    print("Test 2: Smart Schedule Analysis")
    print("=" * 60)
    print()

    # 模拟一个不合理的日程安排
    events = [
        {
            "title": "搬家打包",
            "start_time": "09:00",
            "energy_consumption": {
                "physical": {"level": "high", "score": 9, "description": "长时间打包箱子，弯腰搬运"},
                "mental": {"level": "low", "score": 3, "description": "简单重复性工作"}
            }
        },
        {
            "title": "搬运重物",
            "start_time": "11:00",
            "energy_consumption": {
                "physical": {"level": "high", "score": 8, "description": "搬运家具和重物下楼"},
                "mental": {"level": "low", "score": 2, "description": "体力劳动为主"}
            }
        },
        {
            "title": "整理仓库",
            "start_time": "14:00",
            "energy_consumption": {
                "physical": {"level": "high", "score": 7, "description": "站立整理，频繁移动物品"},
                "mental": {"level": "low", "score": 3, "description": "简单的分类整理"}
            }
        }
    ]

    print("Analyzing schedule with continuous high physical activities...")
    result = await smart_scheduler_agent.analyze_schedule(events)

    if result.get("analysis", {}).get("has_issues"):
        print("[ISSUES DETECTED]")
        for issue in result["analysis"]["issues"]:
            print(f"  - {issue['type']}: {issue['description']}")
            print(f"    Suggestion: {issue['suggestion']}")
    else:
        print("[OK] Schedule looks good")

    print()
    print("[OK] Smart scheduler test completed")


async def test_context_extractor():
    """测试上下文提取系统"""
    print("=" * 60)
    print("Test 3: Context Extraction & User Profiling")
    print("=" * 60)
    print()

    user_id = "test_user_profile"

    # 测试事件
    test_events = [
        {
            "title": "周五晚上约会",
            "description": "和对象去餐厅吃饭",
            "start_time": "2026-01-24T19:00:00"
        },
        {
            "title": "写代码",
            "description": "实现新的API接口",
            "start_time": "2026-01-22T10:00:00"
        },
        {
            "title": "早起运动",
            "description": "早上6点去健身房",
            "start_time": "2026-01-23T06:00:00"
        }
    ]

    for event in test_events:
        print(f"Extracting from: {event['title']}")
        result = await context_extractor_agent.extract(event)

        if result["success"]:
            print(f"  Description: {result['description']}")
            print(f"  Points extracted: {result['points_count']}")

            for point in result.get("extracted_points", []):
                print(f"    - [{point.type}] {point.content} (confidence: {point.confidence})")
                print(f"      Evidence: {', '.join(point.evidence)}")

            # 添加到用户画像
            if result["extracted_points"]:
                profile = profile_service.add_extracted_points(
                    user_id,
                    [p.model_dump() for p in result["extracted_points"]]
                )
                print(f"    -> Profile updated (total points: {profile.total_points})")

        print()

    # 查看用户画像摘要
    print("User Profile Summary:")
    summary = profile_service.get_profile_summary(user_id)
    print(f"  Relationship: {summary['relationships']['status']} (confidence: {summary['relationships']['confidence']})")
    print(f"  Occupation: {summary['identity']['occupation']} (confidence: {summary['identity']['confidence']})")
    print(f"  Activities: {', '.join(summary['preferences']['activities']) or 'None'}")
    print(f"  Sleep: {summary['habits']['sleep']}")
    print(f"  Total points: {summary['total_points']}")

    print()
    print("[OK] Context extraction test completed")


async def main():
    """运行所有测试"""
    print()
    print("=" * 60)
    print("Enhanced Features Test Suite")
    print("=" * 60)
    print()

    try:
        # 测试1: 精力评估
        await test_energy_system()

        # 测试2: 智能调度
        await test_smart_scheduler()

        # 测试3: 上下文提取
        await test_context_extractor()

        print()
        print("=" * 60)
        print("[SUCCESS] All tests completed!")
        print("=" * 60)

    except Exception as e:
        print(f"\n[ERROR] Test failed: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
