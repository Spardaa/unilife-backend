"""
Smart Scheduler Agent - 智能日程调度助手
检测不合理的事件组合，提供精力优化建议
"""
from typing import Dict, Any, List, Optional
from datetime import datetime
from app.services.llm import llm_service


class SmartSchedulerAgent:
    """智能日程调度 Agent"""

    def __init__(self):
        self.name = "smart_scheduler_agent"
        self.llm = llm_service

    async def analyze_schedule(
        self,
        events: List[Dict[str, Any]],
        user_context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        分析日程安排的合理性

        Args:
            events: 事件列表（每个事件包含 energy_consumption 信息）
            user_context: 用户上下文（偏好、习惯等）

        Returns:
            分析结果和建议
        """
        # 构建分析 prompt
        prompt = self._build_analysis_prompt(events, user_context)

        # 调用 LLM
        messages = [{"role": "user", "content": prompt}]
        llm_response = await self.llm.chat_completion(
            messages=messages,
            temperature=0.3
        )

        # 获取内容
        response = llm_response.get("content", "")

        # 解析响应
        analysis = self._parse_analysis(response)

        return analysis

    def _build_analysis_prompt(
        self,
        events: List[Dict[str, Any]],
        user_context: Optional[Dict[str, Any]]
    ) -> str:
        """构建分析 prompt"""

        # 格式化事件列表
        events_str = ""
        for i, event in enumerate(events, 1):
            title = event.get("title", "未知")
            time_info = event.get("start_time", "未知时间")

            # 获取精力消耗信息
            energy = event.get("energy_consumption")
            if energy:
                physical = energy["physical"]
                mental = energy["mental"]
                energy_str = f"  体力: {physical['level']}({physical['score']}分) - {physical['description']}\n"
                energy_str += f"  精神: {mental['level']}({mental['score']}分) - {mental['description']}"
            else:
                energy_str = "  精力消耗: 未评估"

            events_str += f"\n[事件{i}] {title}\n"
            events_str += f"  时间: {time_info}\n"
            events_str += f"{energy_str}\n"

        # 用户偏好（如果有）
        preferences_str = ""
        if user_context and "preferences" in user_context:
            prefs = user_context["preferences"]
            preferences_str = f"""
用户偏好：
- 精力管理模式：{prefs.get('energy_mode', '平衡')}
- 工作节奏：{prefs.get('work_rhythm', '未知')}
- 休息偏好：{prefs.get('break_preference', '未知')}
"""

        prompt = f"""你是日程优化专家。请分析以下连续事件的体力/精神分配是否合理。

事件列表：
{events_str}
{preferences_str}

请检查以下问题：

1. **连续高强度体力消耗**
   - 是否连续3个以上高体力活动（physical.score >= 7）
   - 如果有，提示用户体力透支风险

2. **连续高强度精神工作**
   - 是否连续3个以上高精神活动（mental.score >= 7）
   - 如果有，提示用户精神疲劳风险

3. **单一维度过度集中**
   - 是否全天都是体力活，没有脑力休息？
   - 是否全天都是脑力工作，没有体力活动？
   - 如果有，建议平衡搭配

4. **缺乏休息或调节**
   - 长时间工作后是否安排了休息？
   - 高压力任务后是否安排了放松活动？

5. **总体评估**
   - 日程安排的合理性评分（0-10分）
   - 主要问题总结
   - 具体优化建议

请以JSON格式返回分析结果：
{{
    "overall_score": 0-10的整数,
    "has_issues": true/false,
    "issues": [
        {{
            "type": "连续体力消耗" | "连续精神工作" | "单一维度集中" | "缺乏休息",
            "severity": "high" | "medium" | "low",
            "description": "问题描述",
            "affected_events": ["事件1", "事件2"],
            "suggestion": "具体建议"
        }}
    ],
    "summary": "总体评价",
    "recommendations": ["建议1", "建议2"]
}}

如果日程安排很合理，has_issues 为 false，issues 为空数组，overall_score >= 8。
"""

        return prompt

    def _parse_analysis(self, response: str) -> Dict[str, Any]:
        """解析 LLM 响应"""
        import json

        try:
            # 提取 JSON
            if "```json" in response:
                json_str = response.split("```json")[1].split("```")[0].strip()
            elif "```" in response:
                json_str = response.split("```")[1].split("```")[0].strip()
            else:
                json_str = response.strip()

            data = json.loads(json_str)

            return {
                "success": True,
                "analysis": data,
                "message": self._format_message(data)
            }

        except Exception as e:
            print(f"[Smart Scheduler] Failed to parse response: {e}")
            return {
                "success": False,
                "error": str(e),
                "message": "日程分析失败，请稍后重试"
            }

    def _format_message(self, analysis: Dict[str, Any]) -> str:
        """格式化分析结果为用户友好的消息"""

        if not analysis.get("has_issues", False):
            return f"✅ 日程安排合理！评分：{analysis.get('overall_score', 8)}/10"

        issues = analysis.get("issues", [])
        message = f"⚠️ 检测到日程安排问题（评分：{analysis.get('overall_score', 5)}/10）\n\n"

        for i, issue in enumerate(issues, 1):
            severity_icon = {
                "high": "🔴",
                "medium": "🟡",
                "low": "🟢"
            }.get(issue.get("severity", "medium"), "⚪")

            message += f"{severity_icon} {issue.get('type', '')}: {issue.get('description', '')}\n"
            message += f"   建议：{issue.get('suggestion', '')}\n\n"

        # 添加总体建议
        recommendations = analysis.get("recommendations", [])
        if recommendations:
            message += "💡 总体建议：\n"
            for rec in recommendations:
                message += f"   • {rec}\n"

        return message

    async def quick_check(
        self,
        events: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        快速检查（不调用 LLM，使用规则）

        Args:
            events: 事件列表

        Returns:
            快速检查结果
        """
        issues = []

        # 规则1：连续高体力
        high_physical_count = 0
        for event in events:
            energy = event.get("energy_consumption")
            if energy and energy["physical"]["score"] >= 7:
                high_physical_count += 1
                if high_physical_count >= 3:
                    issues.append({
                        "type": "连续体力消耗",
                        "severity": "high",
                        "description": f"连续{high_physical_count}个高体力活动",
                        "suggestion": "建议在中间插入休息或轻度脑力活动"
                    })
                    break
            else:
                high_physical_count = 0

        # 规则2：连续高精神
        high_mental_count = 0
        for event in events:
            energy = event.get("energy_consumption")
            if energy and energy["mental"]["score"] >= 7:
                high_mental_count += 1
                if high_mental_count >= 3:
                    issues.append({
                        "type": "连续精神工作",
                        "severity": "high",
                        "description": f"连续{high_mental_count}个高精神活动",
                        "suggestion": "建议在中间安排休息或体力活动放松"
                    })
                    break
            else:
                high_mental_count = 0

        if issues:
            return {
                "success": True,
                "has_issues": True,
                "issues": issues,
                "overall_score": max(10 - len(issues) * 2, 3),
                "message": "检测到日程安排问题"
            }
        else:
            return {
                "success": True,
                "has_issues": False,
                "issues": [],
                "overall_score": 9,
                "message": "日程安排基本合理"
            }


# 全局实例
smart_scheduler_agent = SmartSchedulerAgent()
