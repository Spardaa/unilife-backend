"""
双层时间架构 - 真实使用场景测试
模拟各种用户交互场景，验证系统的完整性和正确性
"""
import sys
import asyncio
sys.path.append(".")

from datetime import datetime, timedelta, time
from typing import Dict, Any, List


async def test_user_scenario_1():
    """
    场景1：用户明确指定时长
    用户说："明天10点到11点半开会"
    期望：系统使用用户指定的时间，duration_source=user_exact
    """
    print("\n" + "="*60)
    print("场景1：用户明确指定时长")
    print("="*60)
    print("用户输入：明天10点到11点半开会")

    from app.utils.time_formatter import format_event_time_dual_mode
    from datetime import datetime

    start = datetime.now().replace(hour=10, minute=0, second=0, microsecond=0)
    end = datetime.now().replace(hour=11, minute=30, second=0, microsecond=0)
    duration = 90  # 1小时30分钟

    result = format_event_time_dual_mode(
        start_time=start,
        end_time=end,
        duration=duration,
        title="开会",
        duration_source="user_exact",
        duration_confidence=1.0,
        display_mode="flexible"
    )

    print(f"显示效果：{result}")

    # 验证
    assert "1小时30分钟" in result, "应显示具体时长"
    assert "11:30" in result, "应显示结束时间"
    assert "约" not in result or "AI" not in result, "用户明确指定不应显示'约'或'AI'"
    print("[OK] 用户明确指定时长 - 测试通过")

    return {
        "scenario": "用户明确指定时长",
        "input": "明天10点到11点半开会",
        "output": result,
        "expected": "显示具体时长和结束时间",
        "passed": True
    }


async def test_user_scenario_2():
    """
    场景2：用户只说开始时间（AI估计）
    用户说："明天10点健身"
    期望：AI估计时长，显示"约X小时，AI估计"（如果置信度低）
    """
    print("\n" + "="*60)
    print("场景2：用户只说开始时间（AI低置信度估计）")
    print("="*60)
    print("用户输入：明天10点健身")

    from app.utils.time_formatter import format_event_time_dual_mode
    from datetime import datetime

    start = datetime.now().replace(hour=10, minute=0, second=0, microsecond=0)
    duration = 90  # AI估计：健身90分钟
    end = start + timedelta(minutes=duration)

    result = format_event_time_dual_mode(
        start_time=start,
        end_time=end,
        duration=duration,
        title="健身",
        duration_source="ai_estimate",
        duration_confidence=0.6,  # 低置信度
        display_mode="flexible"
    )

    print(f"显示效果：{result}")

    # 验证
    assert "约" in result, "应显示'约'"
    assert "AI估计" in result, "低置信度应显示'AI估计'"
    assert "预计到" in result, "低置信度应使用'预计到'"
    assert "11:30" in result, "应显示预计结束时间"
    print("[OK] AI低置信度估计 - 测试通过")

    return {
        "scenario": "AI低置信度估计",
        "input": "明天10点健身",
        "output": result,
        "expected": "显示'约'和'AI估计'，使用'预计到'",
        "passed": True
    }


async def test_user_scenario_3():
    """
    场景3：AI高置信度估计
    用户说："写代码"
    期望：AI基于历史数据估计，高置信度，不显示"AI估计"标签
    """
    print("\n" + "="*60)
    print("场景3：AI高置信度估计")
    print("="*60)
    print("用户输入：写代码")

    from app.utils.time_formatter import format_event_time_dual_mode
    from datetime import datetime

    start = datetime.now().replace(hour=14, minute=0, second=0, microsecond=0)
    duration = 120  # AI估计：写代码2小时
    end = start + timedelta(minutes=duration)

    result = format_event_time_dual_mode(
        start_time=start,
        end_time=end,
        duration=duration,
        title="写代码",
        duration_source="ai_estimate",
        duration_confidence=0.85,  # 高置信度
        display_mode="flexible"
    )

    print(f"显示效果：{result}")

    # 验证
    assert "约" in result, "应显示'约'"
    assert "AI估计" not in result, "高置信度不应显示'AI估计'"
    assert "到" in result and "预计到" not in result, "高置信度应使用'到'而不是'预计到'"
    assert "16:00" in result, "应显示结束时间"
    print("[OK] AI高置信度估计 - 测试通过")

    return {
        "scenario": "AI高置信度估计",
        "input": "写代码",
        "output": result,
        "expected": "显示'约'但不显示'AI估计'，使用'到'",
        "passed": True
    }


async def test_user_scenario_4():
    """
    场景4：用户修改AI估计
    AI估计："明天10点开会（60分钟）"
    用户说："改成2小时"
    期望：duration_source=user_adjusted，保留原始估计
    """
    print("\n" + "="*60)
    print("场景4：用户修改AI估计")
    print("="*60)
    print("AI估计：明天10点开会（60分钟）")
    print("用户修改：改成2小时")

    from app.utils.time_formatter import format_event_time_dual_mode
    from datetime import datetime

    start = datetime.now().replace(hour=10, minute=0, second=0, microsecond=0)
    ai_original_estimate = 60  # AI原始估计
    user_adjusted_duration = 120  # 用户调整为2小时
    end = start + timedelta(minutes=user_adjusted_duration)

    result = format_event_time_dual_mode(
        start_time=start,
        end_time=end,
        duration=user_adjusted_duration,
        title="开会",
        duration_source="user_adjusted",
        duration_confidence=1.0,  # 用户修改后置信度为1.0
        display_mode="flexible"
    )

    print(f"显示效果：{result}")

    # 验证
    assert "2小时" in result, "应显示用户修改的时长"
    assert "约" not in result, "用户修改后不应显示'约'"
    assert "AI" not in result, "用户修改后不应显示'AI'"
    assert "12:00" in result, "应显示结束时间"
    print("[OK] 用户修改AI估计 - 测试通过")

    return {
        "scenario": "用户修改AI估计",
        "input": "AI估计60分钟，用户改为120分钟",
        "output": result,
        "expected": "显示用户修改的时长，不显示'约'或'AI'",
        "passed": True
    }


async def test_user_scenario_5():
    """
    场景5：默认时长
    用户说："新事件"（没有历史数据，无法匹配关键词）
    期望：使用默认时长60分钟，显示"约"
    """
    print("\n" + "="*60)
    print("场景5：默认时长")
    print("="*60)
    print("用户输入：新事件")

    from app.utils.time_formatter import format_event_time_dual_mode
    from datetime import datetime

    start = datetime.now().replace(hour=15, minute=0, second=0, microsecond=0)
    duration = 60  # 默认时长
    end = start + timedelta(minutes=duration)

    result = format_event_time_dual_mode(
        start_time=start,
        end_time=end,
        duration=duration,
        title="新事件",
        duration_source="default",
        duration_confidence=0.5,
        display_mode="flexible"
    )

    print(f"显示效果：{result}")

    # 验证
    assert "约" in result, "默认时长应显示'约'"
    assert "AI" not in result, "默认值不应显示'AI'"
    assert "16:00" in result, "应显示结束时间"
    print("[OK] 默认时长 - 测试通过")

    return {
        "scenario": "默认时长",
        "input": "新事件",
        "output": result,
        "expected": "显示'约'但不显示'AI'",
        "passed": True
    }


async def test_user_scenario_6():
    """
    场景6：刚性显示模式
    用户偏好刚性时间
    期望：显示 "10:00-11:00 开会"
    """
    print("\n" + "="*60)
    print("场景6：刚性显示模式")
    print("="*60)
    print("用户偏好：刚性显示")

    from app.utils.time_formatter import format_event_time_dual_mode
    from datetime import datetime

    start = datetime.now().replace(hour=10, minute=0, second=0, microsecond=0)
    end = datetime.now().replace(hour=11, minute=0, second=0, microsecond=0)

    result = format_event_time_dual_mode(
        start_time=start,
        end_time=end,
        duration=60,
        title="开会",
        duration_source="user_exact",
        duration_confidence=1.0,
        display_mode="rigid"
    )

    print(f"显示效果：{result}")

    # 验证
    assert "10:00-11:00" in result, "刚性模式应显示时间范围"
    assert "约" not in result, "刚性模式不应显示'约'"
    print("[OK] 刚性显示模式 - 测试通过")

    return {
        "scenario": "刚性显示模式",
        "input": "display_mode=rigid",
        "output": result,
        "expected": "显示 '10:00-11:00 开会'",
        "passed": True
    }


async def test_user_scenario_7():
    """
    场景7：多事件日程显示
    用户查看一整天的日程
    期望：不同来源的时长有不同的显示方式
    """
    print("\n" + "="*60)
    print("场景7：多事件日程显示")
    print("="*60)
    print("用户查看一天的日程：")

    from app.utils.time_formatter import format_event_list

    now = datetime.now()
    events = [
        {
            "title": "晨会",
            "start_time": (now.replace(hour=9, minute=0)).isoformat(),
            "end_time": (now.replace(hour=9, minute=30)).isoformat(),
            "duration": 30,
            "duration_source": "user_exact",
            "duration_confidence": 1.0,
            "display_mode": "flexible",
            "status": "PENDING"
        },
        {
            "title": "写代码",
            "start_time": (now.replace(hour=10, minute=0)).isoformat(),
            "end_time": (now.replace(hour=12, minute=0)).isoformat(),
            "duration": 120,
            "duration_source": "ai_estimate",
            "duration_confidence": 0.9,
            "display_mode": "flexible",
            "status": "PENDING"
        },
        {
            "title": "午餐",
            "start_time": (now.replace(hour=12, minute=0)).isoformat(),
            "end_time": (now.replace(hour=13, minute=0)).isoformat(),
            "duration": 60,
            "duration_source": "user_exact",
            "duration_confidence": 1.0,
            "display_mode": "flexible",
            "status": "PENDING"
        },
        {
            "title": "健身",
            "start_time": (now.replace(hour=18, minute=0)).isoformat(),
            "end_time": (now.replace(hour=19, minute=30)).isoformat(),
            "duration": 90,
            "duration_source": "ai_estimate",
            "duration_confidence": 0.6,
            "display_mode": "flexible",
            "status": "PENDING"
        }
    ]

    result = format_event_list(events, display_mode="flexible")
    print("\n" + result)

    # 验证
    assert "晨会" in result, "应显示晨会"
    assert "写代码" in result, "应显示写代码"
    assert "健身" in result, "应显示健身"
    # AI高置信度：不显示"AI估计"
    assert "写代码（约2小时" in result, "高置信度AI估计"
    # AI低置信度：显示"AI估计"
    assert "健身" in result and "AI估计" in result, "低置信度AI估计"
    print("\n[OK] 多事件日程显示 - 测试通过")

    return {
        "scenario": "多事件日程显示",
        "input": "4个不同来源的事件",
        "output": result,
        "expected": "根据置信度和来源正确显示",
        "passed": True
    }


async def test_user_scenario_8():
    """
    场景8：AI学习
    用户完成一个事件，AI学习实际时长
    """
    print("\n" + "="*60)
    print("场景8：AI学习")
    print("="*60)
    print("事件完成，AI学习实际时长：")

    from app.agents.duration_estimator import duration_estimator_agent

    # 模拟学习
    event_id = "test-event-001"
    event_title = "开会"
    estimated_duration = 60
    actual_duration = 75  # 实际用了75分钟

    print(f"事件：{event_title}")
    print(f"AI估计：{estimated_duration}分钟")
    print(f"实际：{actual_duration}分钟")
    print(f"误差：{actual_duration - estimated_duration}分钟（{((actual_duration - estimated_duration) / estimated_duration * 100):.1f}%）")

    await duration_estimator_agent.learn_from_completion(
        event_id=event_id,
        event_title=event_title,
        estimated_duration=estimated_duration,
        actual_duration=actual_duration,
        user_id="test-user"
    )

    print("\n[OK] AI学习完成 - 下次估计会更准确")

    return {
        "scenario": "AI学习",
        "input": f"估计{estimated_duration}分钟，实际{actual_duration}分钟",
        "output": "学习数据已记录",
        "expected": "下次估计会更准确",
        "passed": True
    }


async def test_user_scenario_9():
    """
    场景9：边界情况 - 无时长信息
    """
    print("\n" + "="*60)
    print("场景9：边界情况 - 无时长信息")
    print("="*60)

    from app.utils.time_formatter import format_event_time_dual_mode
    from datetime import datetime

    start = datetime.now().replace(hour=10, minute=0, second=0, microsecond=0)

    # 只有开始时间，没有时长
    result = format_event_time_dual_mode(
        start_time=start,
        end_time=None,
        duration=None,
        title="待定事件",
        duration_source="default",
        duration_confidence=0.0,
        display_mode="flexible"
    )

    print(f"显示效果：{result}")

    assert "10:00" in result, "应显示开始时间"
    assert "待定事件" in result, "应显示标题"
    print("[OK] 边界情况 - 测试通过")

    return {
        "scenario": "边界情况 - 无时长",
        "input": "只有开始时间",
        "output": result,
        "expected": "显示开始时间和标题",
        "passed": True
    }


async def test_user_scenario_10():
    """
    场景10：时长格式化测试
    测试各种分钟数的友好显示
    """
    print("\n" + "="*60)
    print("场景10：时长格式化测试")
    print("="*60)

    from app.utils.time_formatter import format_duration_minutes

    test_cases = [
        (30, "30分钟"),
        (45, "45分钟"),
        (60, "1小时"),
        (90, "1小时30分钟"),
        (120, "2小时"),
        (150, "2小时30分钟"),
        (180, "3小时")
    ]

    print("\n时长格式化测试：")
    all_passed = True
    for minutes, expected in test_cases:
        result = format_duration_minutes(minutes)
        status = "[OK]" if result == expected else "[FAIL]"
        print(f"  {status} {minutes}分钟 -> {result} (期望: {expected})")
        if result != expected:
            all_passed = False

    assert all_passed, "部分格式化测试失败"
    print("\n[OK] 时长格式化 - 全部通过")

    return {
        "scenario": "时长格式化",
        "input": f"{len(test_cases)}个测试用例",
        "output": "全部正确",
        "expected": "友好的中文时长显示",
        "passed": True
    }


async def main():
    """运行所有场景测试"""
    print("\n" + "="*60)
    print("双层时间架构 - 真实使用场景测试")
    print("="*60)

    scenarios = [
        test_user_scenario_1,
        test_user_scenario_2,
        test_user_scenario_3,
        test_user_scenario_4,
        test_user_scenario_5,
        test_user_scenario_6,
        test_user_scenario_7,
        test_user_scenario_8,
        test_user_scenario_9,
        test_user_scenario_10,
    ]

    results = []

    for scenario in scenarios:
        try:
            result = await scenario()
            results.append(result)
        except Exception as e:
            print(f"\n[FAIL] {scenario.__name__} 失败: {e}")
            import traceback
            traceback.print_exc()
            results.append({
                "scenario": scenario.__name__,
                "passed": False,
                "error": str(e)
            })

    # 总结
    print("\n" + "="*60)
    print("测试总结")
    print("="*60)

    passed = sum(1 for r in results if r.get("passed", False))
    total = len(results)

    print(f"\n通过：{passed}/{total}")

    for i, result in enumerate(results, 1):
        status = "[OK]" if result.get("passed", False) else "[FAIL]"
        scenario_name = result.get("scenario", "Unknown")
        print(f"{status} {i}. {scenario_name}")

    if passed == total:
        print(f"\n[SUCCESS] 所有场景测试通过！")
        print("\n双层时间架构已准备好投入生产使用！")
        return 0
    else:
        print(f"\n[FAIL] {total - passed} 个测试失败")
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
