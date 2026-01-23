"""
Diary Analyzer Agent - 日记分析器
批量分析日记，提炼并更新用户画像
"""
from typing import Dict, Any, List, Optional
from datetime import datetime, date, timedelta
import json

from app.services.llm import llm_service
from app.services.prompt import prompt_service
from app.services.diary_service import diary_service
from app.services.profile_service import profile_service
from app.models.diary import UserDiary
from app.models.user_profile import UserProfile
from app.models.profile_analysis import JobType


class DiaryAnalyzerAgent:
    """日记分析 Agent"""

    def __init__(self):
        self.name = "diary_analyzer"
        self.llm = llm_service

    async def analyze_period(
        self,
        user_id: str,
        period_start: date,
        period_end: date,
        job_type: JobType = JobType.DAILY
    ) -> Dict[str, Any]:
        """
        分析指定时间段的日记，更新用户画像

        Args:
            user_id: 用户ID
            period_start: 开始日期
            period_end: 结束日期
            job_type: 任务类型（daily/weekly）

        Returns:
            {
                "success": bool,
                "profile_changes": Dict[str, Any],
                "confidence_delta": Dict[str, float],
                "analysis_summary": str
            }
        """
        # 获取时间范围内的日记
        diaries = diary_service.get_diaries_by_period(user_id, period_start, period_end)

        if not diaries:
            return {
                "success": True,
                "profile_changes": {},
                "confidence_delta": {},
                "analysis_summary": "No diaries found for the specified period"
            }

        # 获取当前画像
        current_profile = profile_service.get_or_create_profile(user_id)

        # 构建 prompt
        prompt = self._build_analysis_prompt(
            diaries=diaries,
            current_profile=current_profile,
            job_type=job_type
        )

        # 调用 LLM 分析
        messages = [{"role": "user", "content": prompt}]
        llm_response = await self.llm.chat_completion(
            messages=messages,
            temperature=0.4
        )
        response = llm_response.get("content", "")

        # 解析响应
        result = self._parse_analysis_response(response)

        if not result.get("success"):
            return {
                "success": False,
                "error": result.get("error", "Failed to parse LLM response"),
                "profile_changes": {},
                "confidence_delta": {}
            }

        # 应用画像更新
        profile_changes, confidence_delta = self._apply_profile_updates(
            user_id=user_id,
            current_profile=current_profile,
            updates=result["updates"]
        )

        return {
            "success": True,
            "profile_changes": profile_changes,
            "confidence_delta": confidence_delta,
            "analysis_summary": result.get("summary", "")
        }

    def _build_analysis_prompt(
        self,
        diaries: List[UserDiary],
        current_profile: UserProfile,
        job_type: JobType
    ) -> str:
        """构建分析 prompt"""

        # 构建日记摘要
        diaries_summary = self._build_diaries_summary(diaries)

        # 构建当前画像摘要
        profile_summary = self._build_profile_summary(current_profile)

        # 分析深度
        depth = "深度" if job_type == JobType.WEEKLY else "常规"

        # 尝试加载 prompt 文件
        try:
            base_prompt = prompt_service.load_prompt("diary_analyzer")
            return base_prompt.format(
                analysis_depth=depth,
                diaries_summary=diaries_summary,
                profile_summary=profile_summary
            )
        except:
            # 使用默认 prompt
            return self._get_default_prompt(depth, diaries_summary, profile_summary)

    def _build_diaries_summary(self, diaries: List[UserDiary]) -> str:
        """构建日记摘要"""
        if not diaries:
            return "无日记记录"

        summary_parts = []

        for diary in diaries:
            date_str = diary.diary_date.isoformat() if isinstance(diary.diary_date, date) else diary.diary_date
            summary_parts.append(f"""
## {date_str}
{diary.summary}

活动类型: {', '.join(diary.key_insights.activities)}
情绪状态: {', '.join(diary.key_insights.emotions)}
行为模式: {', '.join(diary.key_insights.patterns)}
时间偏好: {diary.key_insights.time_preference}
决策风格: {diary.key_insights.decision_style}

提取信号:
{self._format_signals(diary.extracted_signals)}
""")

        return "\n".join(summary_parts)

    def _format_signals(self, signals: List) -> str:
        """格式化信号列表"""
        if not signals:
            return "- 无"

        lines = []
        for signal in signals:
            s = signal.model_dump() if hasattr(signal, 'model_dump') else signal
            lines.append(f"- [{s.get('type', 'unknown')}] {s.get('value', '')} (置信度: {s.get('confidence', 0)})")

        return "\n".join(lines)

    def _build_profile_summary(self, profile: UserProfile) -> str:
        """构建当前画像摘要"""
        return f"""
## 当前用户画像

### 关系状态
- 状态: {profile.relationships.status}
- 置信度: {profile.relationships.confidence}
- 证据数: {profile.relationships.evidence_count}

### 用户身份
- 职业: {profile.identity.occupation}
- 行业: {profile.identity.industry}
- 职位: {profile.identity.position}
- 置信度: {profile.identity.confidence}

### 个人喜好
- 活动类型: {', '.join(profile.preferences.activity_types) or '未知'}
- 社交倾向: {profile.preferences.social_preference}
- 工作风格: {profile.preferences.work_style}

### 个人习惯
- 作息: {profile.habits.sleep_schedule}
- 工作时间: {profile.habits.work_hours}
- 运动频率: {profile.habits.exercise_frequency}
"""

    def _get_default_prompt(self, depth: str, diaries_summary: str, profile_summary: str) -> str:
        """默认 prompt（备用）"""
        return f"""你是用户画像分析专家。请进行{depth}分析，根据用户日记更新用户画像。

{diaries_summary}

{profile_summary}

## 你的任务

基于日记分析，提出画像更新建议。每个更新需要：

1. **字段**: 要更新的画像字段
2. **当前值**: 当前画像中的值
3. **建议值**: 基于日记分析的新值
4. **置信度变化**: 置信度应调整为多少（0.0-1.0）
5. **理由**: 为什么这样调整

## 输出格式（JSON）

{{
    "summary": "本次分析的总体说明，描述用户在这段时间的主要变化和特点",
    "updates": [
        {{
            "category": "relationships" | "identity" | "preferences" | "habits",
            "field": "具体字段名",
            "current_value": "当前值",
            "suggested_value": "建议值",
            "confidence": 0.0-1.0,
            "reason": "调整理由，引用日记中的证据"
        }}
    ]
}}

## 注意事项

1. **只建议有明确证据支持的更新**
2. **置信度应该反映证据的强度**
3. **对于冲突信号，选择证据更强的或保持中立**
4. **summary 应该简洁，3-5句话概括主要发现**

请严格遵循JSON格式。
"""

    def _parse_analysis_response(self, response: str) -> Dict[str, Any]:
        """解析 LLM 响应"""
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
                "summary": data.get("summary", ""),
                "updates": data.get("updates", [])
            }

        except Exception as e:
            print(f"[Diary Analyzer] Failed to parse response: {e}")
            print(f"[Diary Analyzer] Response: {response[:500]}")
            return {
                "success": False,
                "error": str(e)
            }

    def _apply_profile_updates(
        self,
        user_id: str,
        current_profile: UserProfile,
        updates: List[Dict[str, Any]]
    ) -> tuple[Dict[str, Any], Dict[str, float]]:
        """
        应用画像更新

        Returns:
            (changes, delta): 变更描述和置信度变化
        """
        from app.models.event import ExtractedPoint

        # 记录变更前的置信度
        confidence_before = {
            "relationships": current_profile.relationships.confidence,
            "identity": current_profile.identity.confidence,
        }

        changes = {}

        # 处理每个更新
        for update in updates:
            category = update.get("category")
            field = update.get("field")
            suggested_value = update.get("suggested_value")
            new_confidence = update.get("confidence", 0.5)

            if category == "relationships":
                changes.update(self._update_relationships(current_profile, update))
            elif category == "identity":
                changes.update(self._update_identity(current_profile, update))
            elif category == "preferences":
                changes.update(self._update_preferences(current_profile, update))
            elif category == "habits":
                changes.update(self._update_habits(current_profile, update))

        # 保存更新后的画像
        profile_service.save_profile(user_id, current_profile)

        # 计算置信度变化
        confidence_after = {
            "relationships": current_profile.relationships.confidence,
            "identity": current_profile.identity.confidence,
        }

        delta = {
            category: confidence_after[category] - confidence_before[category]
            for category in confidence_before
        }

        return changes, delta

    def _update_relationships(self, profile: UserProfile, update: Dict[str, Any]) -> Dict[str, Any]:
        """更新关系状态"""
        field = update.get("field")
        suggested_value = update.get("suggested_value", "")
        new_confidence = update.get("confidence", 0.5)

        changes = {}

        if field == "status":
            old_status = profile.relationships.status
            if suggested_value != old_status:
                profile.relationships.status = suggested_value
                profile.relationships.confidence = new_confidence
                changes["relationships"] = {
                    "field": "status",
                    "from": old_status,
                    "to": suggested_value,
                    "confidence": new_confidence
                }

        return changes

    def _update_identity(self, profile: UserProfile, update: Dict[str, Any]) -> Dict[str, Any]:
        """更新用户身份"""
        field = update.get("field")
        suggested_value = update.get("suggested_value", "")
        new_confidence = update.get("confidence", 0.5)

        changes = {}
        identity_key = f"identity.{field}"

        if field == "occupation":
            old_value = profile.identity.occupation
            if suggested_value != old_value:
                profile.identity.occupation = suggested_value
                profile.identity.confidence = max(profile.identity.confidence, new_confidence)
                changes[identity_key] = {
                    "field": "occupation",
                    "from": old_value,
                    "to": suggested_value,
                    "confidence": new_confidence
                }
        elif field == "industry":
            old_value = profile.identity.industry
            if suggested_value != old_value:
                profile.identity.industry = suggested_value
                profile.identity.confidence = max(profile.identity.confidence, new_confidence)
                changes[identity_key] = {
                    "field": "industry",
                    "from": old_value,
                    "to": suggested_value,
                    "confidence": new_confidence
                }

        return changes

    def _update_preferences(self, profile: UserProfile, update: Dict[str, Any]) -> Dict[str, Any]:
        """更新个人喜好"""
        field = update.get("field")
        suggested_value = update.get("suggested_value", "")

        changes = {}

        if field == "activity_types":
            # 添加新的活动类型（如果不存在）
            for activity in suggested_value.split(","):
                activity = activity.strip()
                if activity and activity not in profile.preferences.activity_types:
                    profile.preferences.activity_types.append(activity)

            if suggested_value:
                changes["preferences.activities"] = {
                    "added": suggested_value,
                    "current": profile.preferences.activity_types
                }

        elif field == "social_preference":
            old_value = profile.preferences.social_preference
            if suggested_value != old_value:
                profile.preferences.social_preference = suggested_value
                changes["preferences.social"] = {
                    "from": old_value,
                    "to": suggested_value
                }

        return changes

    def _update_habits(self, profile: UserProfile, update: Dict[str, Any]) -> Dict[str, Any]:
        """更新个人习惯"""
        field = update.get("field")
        suggested_value = update.get("suggested_value", "")

        changes = {}
        habit_key = f"habits.{field}"

        if field == "sleep_schedule":
            old_value = profile.habits.sleep_schedule
            if suggested_value != old_value:
                profile.habits.sleep_schedule = suggested_value
                changes[habit_key] = {
                    "field": "sleep_schedule",
                    "from": old_value,
                    "to": suggested_value
                }
        elif field == "work_hours":
            old_value = profile.habits.work_hours
            if suggested_value != old_value:
                profile.habits.work_hours = suggested_value
                changes[habit_key] = {
                    "field": "work_hours",
                    "from": old_value,
                    "to": suggested_value
                }
        elif field == "exercise_frequency":
            old_value = profile.habits.exercise_frequency
            if suggested_value != old_value:
                profile.habits.exercise_frequency = suggested_value
                changes[habit_key] = {
                    "field": "exercise_frequency",
                    "from": old_value,
                    "to": suggested_value
                }

        return changes


# 全局实例
diary_analyzer = DiaryAnalyzerAgent()
