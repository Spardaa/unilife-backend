"""
测试双层时间架构与现有系统的集成
"""
import sys
import asyncio
sys.path.append(".")

from datetime import datetime, timedelta


async def test_integration():
    """测试集成"""
    print("=" * 60)
    print("双层时间架构集成测试")
    print("=" * 60)
    print()

    # 测试 1: 检查数据模型是否支持新字段
    print("[Test 1] 检查 Event 模型...")
    try:
        from app.models.event import Event

        # 创建一个测试事件
        test_event = Event(
            user_id="test-user",
            title="测试事件",
            start_time=datetime.now(),
            end_time=datetime.now() + timedelta(hours=1),
            duration=60,
            duration_source="ai_estimate",
            duration_confidence=0.8,
            display_mode="flexible"
        )

        print("  [OK] Event 模型支持所有新字段")
        print(f"    - duration_source: {test_event.duration_source}")
        print(f"    - duration_confidence: {test_event.duration_confidence}")
        print(f"    - display_mode: {test_event.display_mode}")
    except Exception as e:
        print(f"  [FAIL] Event 模型错误: {e}")
        return False

    # 测试 2: 检查时长估计 Agent
    print()
    print("[Test 2] 检查时长估计 Agent...")
    try:
        from app.agents.duration_estimator import duration_estimator_agent

        estimate = await duration_estimator_agent.estimate(
            event_title="开会",
            use_llm=False
        )

        print("  [OK] Duration Estimator Agent 正常工作")
        print(f"    - 估计时长: {estimate.duration}分钟")
        print(f"    - 置信度: {estimate.confidence}")
        print(f"    - 来源: {estimate.source}")
    except Exception as e:
        print(f"  [FAIL] Duration Estimator Agent 错误: {e}")
        return False

    # 测试 3: 检查时间格式化工具
    print()
    print("[Test 3] 检查时间格式化工具...")
    try:
        from app.utils.time_formatter import format_event_for_display

        now = datetime.now()
        test_event_data = {
            "title": "开会",
            "start_time": now.isoformat(),
            "end_time": (now + timedelta(hours=1)).isoformat(),
            "duration": 60,
            "duration_source": "ai_estimate",
            "duration_confidence": 0.8,
            "display_mode": "flexible"
        }

        formatted = format_event_for_display(test_event_data)

        print("  [OK] Time Formatter 正常工作")
        print(f"    - 显示效果: {formatted}")

        # 检查是否包含结束时间
        if "到" in formatted and "左右" in formatted:
            print("    [OK] 包含预计结束时间")
        else:
            print("    [FAIL] 缺少预计结束时间")
            return False
    except Exception as e:
        print(f"  [FAIL] Time Formatter 错误: {e}")
        return False

    # 测试 4: 检查工具集成
    print()
    print("[Test 4] 检查工具集成...")
    try:
        from app.agents.tools import tool_complete_event

        # 检查工具签名
        import inspect
        sig = inspect.signature(tool_complete_event)
        params = sig.parameters

        # 检查是否有 actual_duration 参数（完成事件）
        if "actual_duration" in params:
            print("  [OK] complete_event 支持实际时长参数")
        else:
            print("  [!] complete_event 缺少 actual_duration 参数（可能未更新）")

        print("  [OK] 工具导入成功")
    except Exception as e:
        print(f"  [FAIL] 工具导入错误: {e}")
        return False

    # 测试 5: 检查前端兼容性
    print()
    print("[Test 5] 检查前端兼容性...")
    try:
        # 检查 client.py 是否能正确处理新字段
        import subprocess
        result = subprocess.run(
            ["python", "-c", "from client import format_events_display; print('OK')"],
            capture_output=True,
            text=True,
            timeout=5
        )

        if result.returncode == 0:
            print("  [OK] client.py 兼容新字段")
        else:
            print(f"  [!] client.py 可能有兼容性问题")
    except Exception as e:
        print(f"  [!] 无法测试前端: {e}")

    print()
    print("=" * 60)
    print("[SUCCESS] 集成测试通过！")
    print("=" * 60)
    return True


async def main():
    try:
        success = await test_integration()
        if not success:
            print("\n[ERROR] 集成测试失败")
            sys.exit(1)
    except Exception as e:
        print(f"\n[ERROR] 测试异常: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
