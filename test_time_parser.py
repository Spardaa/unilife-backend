"""
测试智能时间解析功能
"""
from datetime import datetime
from app.services.time_parser import parse_time_expression

def test_time_parser():
    """测试各种时间表达"""
    print("=" * 60)
    print("Smart Time Parser Test")
    print("=" * 60)
    print()

    test_cases = [
        # 精确时间
        "明天下午3点",
        "后天15:30",
        "3点半",
        "上午9点",

        # 相对日期
        "今天",
        "明天",
        "后天",
        "大后天",

        # 星期几
        "下周三",
        "本周五",
        "这周三",
        "下周一",

        # 模糊时间
        "傍晚",
        "凌晨",
        "晚上",
        "上午晚些时候",
        "下午早",

        # 复合表达
        "明天傍晚",
        "下周三上午",
        "周五晚上",

        # 时间范围
        "本周三到周五",
        "下周一开始连续三天",
    ]

    for text in test_cases:
        print(f"\nTest: '{text}'")
        print("-" * 40)

        result = parse_time_expression(text)

        if result["success"]:
            print(f"[OK] Success")
            print(f"   Type: {result.get('type')}")
            print(f"   Explanation: {result.get('explanation')}")
            if result.get("start_time"):
                print(f"   Start: {result.get('start_time')}")
            if result.get("end_time"):
                print(f"   End: {result.get('end_time')}")
            if result.get("time_range"):
                print(f"   Range: {result.get('time_range')}")
            if result.get("ambiguity"):
                print(f"   Ambiguity: {result.get('ambiguity')}")
            print(f"   Confidence: {result.get('confidence')}")
        else:
            print(f"[FAIL] {result.get('error')}")
            if result.get("suggestions"):
                print(f"   Suggestions: {result.get('suggestions')}")

    print()
    print("=" * 60)


if __name__ == "__main__":
    test_time_parser()
