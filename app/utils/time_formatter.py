"""
Time Formatter - 双层时间架构显示辅助函数
支持柔性显示和刚性显示两种模式
"""
from typing import Optional
from datetime import datetime, timedelta


def format_duration_minutes(minutes: int) -> str:
    """
    将分钟数转换为友好的时长显示

    Args:
        minutes: 分钟数

    Returns:
        友好的时长字符串（如 "1小时"、"1小时30分钟"、"45分钟"）
    """
    if minutes < 60:
        return f"{minutes}分钟"
    elif minutes % 60 == 0:
        hours = minutes // 60
        return f"{hours}小时"
    else:
        hours = minutes // 60
        mins = minutes % 60
        return f"{hours}小时{mins}分钟"


def format_event_time_dual_mode(
    start_time: Optional[datetime],
    end_time: Optional[datetime],
    duration: Optional[int],
    title: str,
    duration_source: str = "default",
    duration_confidence: float = 1.0,
    display_mode: str = "flexible",
    show_end_time_if_rigid: bool = True
) -> str:
    """
    双层时间架构的显示格式化

    Args:
        start_time: 开始时间
        end_time: 结束时间
        duration: 时长（分钟）
        title: 事件标题
        duration_source: 时长来源 (user_exact, ai_estimate, default, user_adjusted)
        duration_confidence: 置信度 (0.0-1.0)
        display_mode: 显示模式 (flexible, rigid, auto)
        show_end_time_if_rigid: 刚性模式下是否显示结束时间

    Returns:
        格式化后的时间字符串
    """

    # 缺少时间信息
    if not start_time:
        if duration:
            return f"{title}（{format_duration_minutes(duration)}）"
        return title

    # 提取时间部分
    time_str = start_time.strftime("%H:%M")

    # 计算预计结束时间
    estimated_end = None
    if duration:
        estimated_end = start_time + timedelta(minutes=duration)
    elif end_time:
        estimated_end = end_time

    # 刚性显示模式
    if display_mode == "rigid" or display_mode == "auto":
        # 刚性显示：10:00-11:00 标题
        if end_time and show_end_time_if_rigid:
            end_str = end_time.strftime("%H:%M")
            return f"{time_str}-{end_str} {title}"
        elif duration:
            return f"{time_str} {title}（{format_duration_minutes(duration)}）"
        else:
            return f"{time_str} {title}"

    # 柔性显示模式
    if display_mode == "flexible":
        duration_text = format_duration_minutes(duration) if duration else "时长待定"

        # 构建基础部分
        base_parts = [time_str, title]

        # 添加时长信息
        if duration:
            # 判断是否显示"AI估计"标注
            # 置信度阈值：0.7
            show_ai_note = (
                duration_source == "ai_estimate" and
                duration_confidence < 0.7
            )

            if show_ai_note:
                base_parts.append(f"约{duration_text}，AI估计")
            elif duration_source == "ai_estimate":
                # 高置信度的AI估计，不显示标注
                base_parts.append(f"约{duration_text}")
            elif duration_source == "default":
                base_parts.append(f"约{duration_text}")
            else:
                # user_exact 或 user_adjusted
                base_parts.append(f"{duration_text}")

        # 添加预计结束时间
        if estimated_end:
            end_str = estimated_end.strftime("%H:%M")
            if duration_source == "ai_estimate" and duration_confidence < 0.7:
                # AI低置信度，使用"预计"
                base_parts.append(f"预计到{end_str}左右")
            else:
                # 其他情况，使用"到"
                base_parts.append(f"到{end_str}左右")

        # 组合显示
        result = " ".join(base_parts[:2])  # 时间 + 标题
        if len(base_parts) > 2:  # 有时长和/或结束时间
            info = "，".join(base_parts[2:])  # 时长，结束时间
            result += f"（{info}）"

        return result

    # 兜底
    return f"{time_str} {title}"


def format_event_for_display(event: dict, display_mode_override: Optional[str] = None) -> str:
    """
    格式化事件对象用于显示

    Args:
        event: 事件字典（从数据库或API获取）
        display_mode_override: 强制覆盖显示模式

    Returns:
        格式化后的字符串
    """
    start_time = event.get("start_time")
    end_time = event.get("end_time")
    duration = event.get("duration")
    title = event.get("title", "未命名事件")
    duration_source = event.get("duration_source", "default")
    duration_confidence = event.get("duration_confidence", 1.0)

    # 解析时间字符串
    if start_time and isinstance(start_time, str):
        start_time = datetime.fromisoformat(start_time)
    if end_time and isinstance(end_time, str):
        end_time = datetime.fromisoformat(end_time)

    # 确定显示模式
    display_mode = display_mode_override or event.get("display_mode", "flexible")

    return format_event_time_dual_mode(
        start_time=start_time,
        end_time=end_time,
        duration=duration,
        title=title,
        duration_source=duration_source,
        duration_confidence=duration_confidence,
        display_mode=display_mode
    )


def format_event_list(events: list, display_mode: str = "flexible") -> str:
    """
    格式化事件列表用于显示

    Args:
        events: 事件列表
        display_mode: 显示模式

    Returns:
        格式化后的多行字符串
    """
    if not events:
        return "暂无事件"

    lines = []
    for i, event in enumerate(events, 1):
        formatted = format_event_for_display(event, display_mode)

        # 添加状态图标
        status = event.get("status", "PENDING")
        status_icon = "✓" if status == "COMPLETED" else "○"

        lines.append(f"{status_icon} {i}. {formatted}")

    return "\n".join(lines)


# 示例用法
if __name__ == "__main__":
    from datetime import timedelta

    # 测试用例
    now = datetime.now()

    test_cases = [
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

    print("=" * 60)
    print("双层时间架构显示测试")
    print("=" * 60)

    for event in test_cases:
        formatted = format_event_for_display(event)
        print(formatted)

    print("\n" + "=" * 60)
    print("事件列表测试")
    print("=" * 60)

    print(format_event_list(test_cases))
