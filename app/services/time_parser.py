"""
智能时间解析服务
支持多种自然语言时间表达方式的解析
"""
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta
import re
from calendar import day_name

class TimeParser:
    """智能时间解析器"""

    def __init__(self):
        # 星期映射（中文→数字）
        self.weekday_map = {
            "周一": 0, "星期一": 0, "一": 0,
            "周二": 1, "星期二": 1, "二": 1,
            "周三": 2, "星期三": 2, "三": 2,
            "周四": 3, "星期四": 3, "四": 3,
            "周五": 4, "星期五": 4, "五": 4,
            "周六": 5, "星期六": 5, "六": 5,
            "周日": 6, "星期日": 6, "日": 6,
            "monday": 0, "mon": 0,
            "tuesday": 1, "tue": 1,
            "wednesday": 2, "wed": 2,
            "thursday": 3, "thu": 3,
            "friday": 4, "fri": 4,
            "saturday": 5, "sat": 5,
            "sunday": 6, "sun": 6,
        }

        # 模糊时间映射
        self.fuzzy_time_map = {
            "凌晨": (0, 6),
            "早上": (6, 9),
            "早晨": (6, 9),
            "上午": (9, 12),
            "中午": (11, 14),
            "下午": (14, 18),
            "傍晚": (17, 20),
            "晚上": (18, 23),
            "深夜": (22, 24),
            "午夜": (23, 2),
            "凌晨早": (4, 6),
            "凌晨晚": (2, 4),
            "上午早": (9, 10),
            "上午晚": (11, 12),
            "下午早": (14, 16),
            "下午晚": (16, 18),
            "晚上早": (18, 21),
            "晚上晚": (21, 23),
        }

    def parse(
        self,
        text: str,
        reference_date: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """
        解析时间文本

        Args:
            text: 时间文本（如"明天下午3点"、"下周三"）
            reference_date: 参考日期（默认为当前时间）

        Returns:
            {
                "success": true/false,
                "type": "exact"/"range"/"fuzzy",
                "start_time": "2026-01-21T15:00:00",
                "end_time": "2026-01-21T16:00:00",
                "date": "2026-01-21",
                "time": "15:00",
                "duration": 60,
                "confidence": "high"/"medium"/"low",
                "explanation": "解析说明",
                "ambiguity": []  # 模糊点列表
            }
        """
        if reference_date is None:
            reference_date = datetime.now()

        text = text.strip().lower()

        # 尝试各种解析模式
        result = self._parse_exact_time(text, reference_date)
        if result["success"]:
            return result

        result = self._parse_relative_date(text, reference_date)
        if result["success"]:
            return result

        result = self._parse_weekday(text, reference_date)
        if result["success"]:
            return result

        result = self._parse_fuzzy_time(text, reference_date)
        if result["success"]:
            return result

        result = self._parse_time_range(text, reference_date)
        if result["success"]:
            return result

        return {
            "success": False,
            "error": "无法识别时间表达",
            "suggestions": self._get_time_suggestions()
        }

    def _parse_exact_time(
        self,
        text: str,
        reference_date: datetime
    ) -> Dict[str, Any]:
        """解析精确时间（如"下午3点"、"15:30"）"""
        # 匹配 "3点"、"3:30"、"15:00" 等格式
        time_pattern = r'(\d{1,2})[点：:](\d{2})?(?:半|30)?'
        match = re.search(time_pattern, text)

        if not match:
            return {"success": False}

        hour = int(match.group(1))
        minute = 0

        if match.group(2):
            minute = int(match.group(2))
        elif "半" in text[match.start():match.end()+5]:
            minute = 30

        # 判断是上午还是下午
        if "上午" in text or "早上" in text or "早晨" in text:
            if hour == 12:
                hour = 0
        elif "下午" in text or "晚上" in text or "中午" in text:
            if hour < 12:
                hour += 12

        # 判断日期
        target_date = reference_date.date()
        if "明天" in text:
            target_date = (reference_date + timedelta(days=1)).date()
        elif "后天" in text:
            target_date = (reference_date + timedelta(days=2)).date()

        start_time = datetime.combine(target_date, datetime.min.time()).replace(
            hour=hour, minute=minute
        )

        return {
            "success": True,
            "type": "exact",
            "start_time": start_time.isoformat(),
            "date": target_date.isoformat(),
            "time": f"{hour:02d}:{minute:02d}",
            "confidence": "high",
            "explanation": f"解析为精确时间：{target_date} {hour:02d}:{minute:02d}"
        }

    def _parse_relative_date(
        self,
        text: str,
        reference_date: datetime
    ) -> Dict[str, Any]:
        """解析相对日期（如"明天"、"后天"、"大后天"）"""
        day_map = {
            "今天": 0,
            "明日": 0,
            "明天": 1,
            "次日": 1,
            "后天": 2,
            "大后天": 3,
        }

        for day_str, offset in day_map.items():
            if day_str in text:
                target_date = (reference_date + timedelta(days=offset)).date()
                return {
                    "success": True,
                    "type": "exact",
                    "date": target_date.isoformat(),
                    "confidence": "high",
                    "explanation": f"解析为：{day_str}（{target_date}）"
                }

        return {"success": False}

    def _parse_weekday(
        self,
        text: str,
        reference_date: datetime
    ) -> Dict[str, Any]:
        """解析星期几（如"下周三"、"本周五"）"""
        # 提取周几
        matched_weekday = None
        for weekday_name, weekday_num in self.weekday_map.items():
            if weekday_name in text:
                matched_weekday = weekday_num
                break

        if matched_weekday is None:
            return {"success": False}

        # 判断是本周还是下周
        current_weekday = reference_date.weekday()
        days_ahead = matched_weekday - current_weekday

        if "下周" in text or "下个" in text:
            days_ahead += 7
        elif "上周" in text or "上个" in text:
            days_ahead -= 7
        elif days_ahead < 0:
            # 如果本周的这一天已经过去，默认指下周
            days_ahead += 7

        target_date = (reference_date + timedelta(days=days_ahead)).date()

        return {
            "success": True,
            "type": "exact",
            "date": target_date.isoformat(),
            "weekday": matched_weekday,
            "weekday_name": list(day_name)[matched_weekday],
            "days_ahead": days_ahead,
            "confidence": "high",
            "explanation": f"解析为：{list(day_name)[matched_weekday]}（{target_date}）"
        }

    def _parse_fuzzy_time(
        self,
        text: str,
        reference_date: datetime
    ) -> Dict[str, Any]:
        """解析模糊时间（如"傍晚"、"上午晚些时候"）"""
        best_match = None
        match_length = 0

        for fuzzy_name, (start_hour, end_hour) in self.fuzzy_time_map.items():
            if fuzzy_name in text:
                if len(fuzzy_name) > match_length:
                    match_length = len(fuzzy_name)
                    best_match = (fuzzy_name, start_hour, end_hour)

        if best_match:
            fuzzy_name, start_hour, end_hour = best_match
            target_date = reference_date.date()

            # 判断日期
            if "明天" in text:
                target_date = (reference_date + timedelta(days=1)).date()
                fuzzy_name = "明天" + fuzzy_name

            start_time = datetime.combine(target_date, datetime.min.time()).replace(
                hour=start_hour
            )
            end_time = datetime.combine(target_date, datetime.min.time()).replace(
                hour=end_hour % 24
            )

            # 跨天处理
            if end_hour < start_hour:
                end_time = end_time + timedelta(days=1)

            duration = int((end_time - start_time).total_seconds() / 60)

            return {
                "success": True,
                "type": "fuzzy",
                "start_time": start_time.isoformat(),
                "end_time": end_time.isoformat(),
                "date": target_date.isoformat(),
                "time_range": f"{start_hour:02d}:00-{end_hour % 24:02d}:00",
                "duration": duration,
                "confidence": "medium",
                "explanation": f"解析为模糊时段：{fuzzy_name}（{start_hour:02d}:00-{end_hour % 24:02d}:00）",
                "ambiguity": ["具体时间需要确认"]
            }

        return {"success": False}

    def _parse_time_range(
        self,
        text: str,
        reference_date: datetime
    ) -> Dict[str, Any]:
        """解析时间范围（如"本周三到周五"、"下周一开始连续三天"）"""
        # 检测"X到Y"、"从X到Y"等模式
        if "到" in text or "至" in text or "到" in text:
            # 提取两个时间点
            parts = re.split(r'[到至]', text)

            if len(parts) == 2:
                # 尝试解析每个部分
                part1_result = self.parse(parts[0].strip(), reference_date)
                part2_result = self.parse(parts[1].strip(), reference_date)

                if part1_result["success"] and part2_result["success"]:
                    return {
                        "success": True,
                        "type": "range",
                        "start_time": part1_result.get("start_time") or part1_result.get("date"),
                        "end_time": part2_result.get("start_time") or part2_result.get("date"),
                        "confidence": "medium",
                        "explanation": f"解析为时间范围：{parts[0]} 至 {parts[1]}",
                        "ambiguity": ["范围内的具体时间需要确认"]
                    }

        return {"success": False}

    def _get_time_suggestions(self) -> List[str]:
        """获取时间建议"""
        now = datetime.now()
        suggestions = []

        # 今天剩余时间
        if now.hour < 18:
            suggestions.append(f"今天 {now.hour + 1}:00")

        # 明天
        suggestions.append(f"明天 9:00")
        suggestions.append(f"明天 14:00")

        # 本周剩余日期
        for i in range(1, 8):
            target_date = now + timedelta(days=i)
            if target_date.weekday() >= now.weekday():
                weekday_name = list(day_name)[target_date.weekday()]
                suggestions.append(f"本周{weekday_name} 9:00")

        return suggestions[:8]  # 返回最多8个建议


# 全局时间解析器实例
time_parser = TimeParser()


def parse_time_expression(
    text: str,
    reference_date: Optional[datetime] = None
) -> Dict[str, Any]:
    """
    解析时间表达式（工具接口）

    Args:
        text: 时间文本
        reference_date: 参考日期（默认当前时间）

    Returns:
        解析结果字典
    """
    return time_parser.parse(text, reference_date)
