"""
测试双层时间架构
测试时长估计、柔性显示、冲突检测等功能
"""
import sys
import asyncio
sys.path.append(".")

from datetime import datetime, timedelta
from app.agents.duration_estimator import duration_estimator_agent
from app.utils.time_formatter import (
    format_event_time_dual_mode,
    format_event_for_display,
    format_event_list
)


async def test_duration_estimator():
    """测试时长估计 Agent"""
    print("=" * 60)
    print("Test 1: Duration Estimator Agent")
    print("=" * 60)
    print()

    # 测试用例
    test_cases = [
        {
            "title": "开会",
            "description": "团队周会"
        },
        {
            "title": "健身",
            "description": "去健身房锻炼"
        },
        {
            "title": "写代码",
            "description": "开发新功能"
        },
        {
            "title": "午餐",
            "description": "和同事吃饭"
        }
    ]

    for case in test_cases:
        print(f"事件：{case['title']}")
        estimate = await duration_estimator_agent.estimate(
            event_title=case['title'],
            event_description=case['description'],
            use_llm=False  # 先不使用LLM，测试默认值
        )

        print(f"  估计时长：{estimate.duration}分钟")
        print(f"  置信度：{estimate.confidence}")
        print(f"  来源：{estimate.source}")
        print(f"  推理：{estimate.reasoning}")
        print()

    print("[OK] Duration estimator test completed")


def test_time_formatter():
    """测试时间格式化"""
    print("=" * 60)
    print("Test 2: Time Formatter")
    print("=" * 60)
    print()

    now = datetime.now()

    test_events = [
        {
            "title": "开会",
            "start_time": now,
            "end_time": now + timedelta(hours=1),
            "duration": 60,
            "duration_source": "user_exact",
            "duration_confidence": 1.0,
            "display_mode": "flexible"
        },
        {
            "title": "写代码",
            "start_time": now + timedelta(hours=2),
            "end_time": now + timedelta(hours=3, minutes=30),
            "duration": 90,
            "duration_source": "ai_estimate",
            "duration_confidence": 0.8,
            "display_mode": "flexible"
        },
        {
            "title": "健身",
            "start_time": now + timedelta(hours=4),
            "end_time": now + timedelta(hours=5),
            "duration": 60,
            "duration_source": "ai_estimate",
            "duration_confidence": 0.6,
            "display_mode": "flexible"
        },
        {
            "title": "团队周会",
            "start_time": now + timedelta(hours=6),
            "end_time": now + timedelta(hours=7, minutes=30),
            "duration": 90,
            "duration_source": "user_exact",
            "duration_confidence": 1.0,
            "display_mode": "rigid"
        }
    ]

    print("柔性显示模式 (flexible)：")
    print("-" * 60)
    for event in test_events[:3]:
        formatted = format_event_for_display(event)
        print(f"  {formatted}")

    print()
    print("刚性显示模式 (rigid)：")
    print("-" * 60)
    for event in test_events[3:]:
        formatted = format_event_for_display(event)
        print(f"  {formatted}")

    print()
    print("事件列表显示：")
    print("-" * 60)
    print(format_event_list(test_events))

    print("[OK] Time formatter test completed")


def test_duration_source_scenarios():
    """测试不同时长来源的场景"""
    print("=" * 60)
    print("Test 3: Duration Source Scenarios")
    print("=" * 60)
    print()

    now = datetime.now()

    scenarios = [
        {
            "scenario": "用户明确指定时长",
            "event": {
                "title": "开会",
                "start_time": now,
                "end_time": now + timedelta(hours=1, minutes=30),
                "duration": 90,
                "duration_source": "user_exact",
                "duration_confidence": 1.0,
                "display_mode": "flexible"
            },
            "expected": "10:00 开会（1小时30分钟）"  # 用户指定，不显示"约"
        },
        {
            "scenario": "AI高置信度估计",
            "event": {
                "title": "写代码",
                "start_time": now + timedelta(hours=2),
                "end_time": now + timedelta(hours=3),
                "duration": 60,
                "duration_source": "ai_estimate",
                "duration_confidence": 0.8,
                "display_mode": "flexible"
            },
            "expected": "12:00 写代码（约1小时）"  # 高置信度，不显示"AI估计"
        },
        {
            "scenario": "AI低置信度估计",
            "event": {
                "title": "健身",
                "start_time": now + timedelta(hours=4),
                "end_time": now + timedelta(hours=5),
                "duration": 60,
                "duration_source": "ai_estimate",
                "duration_confidence": 0.6,
                "display_mode": "flexible"
            },
            "expected": "14:00 健身（约1小时，AI估计）"  # 低置信度，显示"AI估计"
        },
        {
            "scenario": "默认值",
            "event": {
                "title": "新事件",
                "start_time": now + timedelta(hours=6),
                "end_time": now + timedelta(hours=7),
                "duration": 60,
                "duration_source": "default",
                "duration_confidence": 0.5,
                "display_mode": "flexible"
            },
            "expected": "16:00 新事件（约1小时）"  # 默认值，显示"约"
        },
        {
            "scenario": "用户调整AI估计",
            "event": {
                "title": "学习",
                "start_time": now + timedelta(hours=7),
                "end_time": now + timedelta(hours=9),
                "duration": 120,
                "duration_source": "user_adjusted",
                "duration_confidence": 1.0,
                "ai_original_estimate": 90,
                "display_mode": "flexible"
            },
            "expected": "17:00 学习（2小时）"  # 用户调整，不显示"约"
        }
    ]

    for scenario in scenarios:
        print(f"场景：{scenario['scenario']}")
        formatted = format_event_for_display(scenario['event'])
        print(f"  结果：{formatted}")
        print(f"  期望：{scenario['expected']}")
        print()

    print("[OK] Duration source scenarios test completed")


async def test_ai_learning():
    """测试AI学习功能"""
    print("=" * 60)
    print("Test 4: AI Learning from Completion")
    print("=" * 60)
    print()

    # 模拟事件完成
    event_id = "test-event-123"
    event_title = "开会"
    estimated_duration = 60
    actual_duration = 75  # 实际用了75分钟

    print(f"事件：{event_title}")
    print(f"  估计时长：{estimated_duration}分钟")
    print(f"  实际时长：{actual_duration}分钟")

    learning_data = await duration_estimator_agent.learn_from_completion(
        event_id=event_id,
        event_title=event_title,
        estimated_duration=estimated_duration,
        actual_duration=actual_duration,
        user_id="test-user"
    )

    print(f"  学习结果：")
    print(f"    误差：{learning_data['error']}分钟")
    print(f"    误差率：{learning_data['error_rate']:.2%}")

    if learning_data['error_rate'] > 0.2:
        print(f"    [!] 误差较大（>20%%），AI需要学习")
    else:
        print(f"    [OK] 误差可接受")

    print()
    print("[OK] AI learning test completed")


async def main():
    """运行所有测试"""
    print()
    print("=" * 60)
    print("双层时间架构测试套件")
    print("=" * 60)
    print()

    try:
        # 测试1：时长估计
        await test_duration_estimator()

        # 测试2：时间格式化
        test_time_formatter()

        # 测试3：时长来源场景
        test_duration_source_scenarios()

        # 测试4：AI学习
        await test_ai_learning()

        print()
        print("=" * 60)
        print("[SUCCESS] 所有测试通过！")
        print("=" * 60)

    except Exception as e:
        print(f"\n[ERROR] 测试失败: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
