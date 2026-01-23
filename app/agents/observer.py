"""
Observer Agent - 观察者
负责从用户行为中学习和更新用户画像
"""
from typing import Dict, Any, Optional, List
from datetime import datetime, date, timedelta
import json

from app.services.llm import llm_service
from app.services.prompt import prompt_service
from app.services.profile_service import profile_service
from app.services.diary_service import diary_service
from app.services.conversation_service import conversation_service
from app.agents.base import (
    BaseAgent, ConversationContext, AgentResponse
)
from app.models.diary import KeyInsights, ExtractedSignal


class ObserverAgent(BaseAgent):
    """
    Observer Agent - 观察者

    特点：
    - 异步分析，不阻塞主流程
    - 从对话和操作中提取行为模式
    - 更新用户画像（人格画像 + 决策偏好）
    - 支持事件触发和定时分析
    """

    name = "observer"

    def __init__(self):
        self.llm = llm_service

    async def process(self, context: ConversationContext) -> AgentResponse:
        """
        分析对话，更新用户画像

        注意：这个方法通常异步调用，不阻塞主流程

        Args:
            context: 对话上下文（包含完整的对话历史和操作结果）

        Returns:
            AgentResponse: 包含分析结果和更新记录
        """
        # 构建分析请求
        analysis_prompt = self._build_analysis_prompt(context)

        # 调用 LLM 分析
        messages = [{"role": "user", "content": analysis_prompt}]
        response = await self.llm.chat_completion(
            messages=messages,
            temperature=0.4  # 较低温度，保证分析的一致性
        )

        content = response.get("content", "")

        # 解析分析结果
        try:
            result = self._parse_analysis_response(content)

            # 应用更新
            if result.get("success"):
                await self._apply_updates(context.user_id, result)

                return AgentResponse(
                    content=f"[观察] 完成分析，提取了 {len(result.get('signals_extracted', []))} 个信号",
                    metadata={
                        "observer_result": True,
                        "analysis_summary": result.get("summary", ""),
                        "profile_updates": result.get("profile_updates", {}),
                        "decision_profile_updates": result.get("decision_profile_updates", {}),
                        "signals_extracted": result.get("signals_extracted", [])
                    }
                )
            else:
                return AgentResponse(
                    content=f"[观察] 分析失败: {result.get('error', '未知错误')}",
                    metadata={"observer_result": False, "error": result.get("error")}
                )

        except Exception as e:
            print(f"[Observer Agent] Error: {e}")
            return AgentResponse(
                content=f"[观察] 处理异常: {str(e)}",
                metadata={"observer_result": False, "error": str(e)}
            )

    async def on_conversation_end(self, conversation_id: str, user_id: str, context: Optional[Dict] = None):
        """
        对话结束时的触发分析（已废弃，使用 analyze_conversation_batch）

        Args:
            conversation_id: 对话ID
            user_id: 用户ID
            context: 额外上下文信息
        """
        # 注意：此方法已废弃，请使用 analyze_conversation_batch
        # 保留是为了向后兼容
        await self.analyze_conversation_batch(
            conversation_id=conversation_id,
            user_id=user_id,
            full_context=None
        )

    async def analyze_conversation_batch(
        self,
        conversation_id: str,
        user_id: str,
        full_context: Optional[List[Dict]] = None
    ):
        """
        批量分析对话（新的 Observer 触发方式）

        Args:
            conversation_id: 对话ID
            user_id: 用户ID
            full_context: 完整对话上下文（从追踪器传入）
        """
        # 获取对话历史（如果没有提供）
        if not full_context:
            from app.services.conversation_service import conversation_service
            messages = conversation_service.get_messages(conversation_id, limit=50)
            full_context = [msg.to_chat_format() for msg in messages]

        # 构建上下文
        analysis_context = ConversationContext(
            user_id=user_id,
            conversation_id=conversation_id,
            user_message="",  # 批量分析，没有单条消息
            conversation_history=full_context or []
        )

        # 异步分析
        try:
            await self.process(analysis_context)
        except Exception as e:
            print(f"[Observer Agent] Batch analysis error: {e}")

    async def analyze_period(
        self,
        user_id: str,
        period_start: date,
        period_end: date,
        job_type: str = "daily"
    ) -> Dict[str, Any]:
        """
        分析指定时间段的行为（定时任务）

        Args:
            user_id: 用户ID
            period_start: 开始日期
            period_end: 结束日期
            job_type: 任务类型（daily/weekly）

        Returns:
            分析结果
        """
        # 获取时间范围内的对话
        from app.services.conversation_service import conversation_service

        conversations = conversation_service.get_recent_conversations(
            user_id=user_id,
            days=(period_end - period_start).days + 1,
            limit=100
        )

        # 收集所有消息
        all_messages = []
        for conv in conversations:
            messages = conversation_service.get_messages(conv.id, limit=100)
            all_messages.extend([msg.to_chat_format() for msg in messages])

        if not all_messages:
            return {
                "success": True,
                "summary": f"没有找到 {period_start} 到 {period_end} 的对话记录"
            }

        # 构建分析上下文
        analysis_context = ConversationContext(
            user_id=user_id,
            conversation_id="",
            user_message=f"分析 {period_start} 到 {period_end} 的行为模式",
            conversation_history=all_messages[-50:]  # 最近50条
        )

        # 深度分析提示
        depth = "深度" if job_type == "weekly" else "常规"
        analysis_prompt = self._build_analysis_prompt(analysis_context, depth=depth)

        # 调用 LLM
        messages = [{"role": "user", "content": analysis_prompt}]
        response = await self.llm.chat_completion(
            messages=messages,
            temperature=0.4
        )

        content = response.get("content", "")

        # 解析并应用更新
        result = self._parse_analysis_response(content)
        if result.get("success"):
            await self._apply_updates(user_id, result)

        return result

    def _build_analysis_prompt(self, context: ConversationContext, depth: str = "常规") -> str:
        """构建分析提示词"""
        # 获取当前画像
        profile = profile_service.get_or_create_profile(context.user_id)

        # 构建对话摘要
        conversation_summary = self._build_conversation_summary(context)

        # 构建画像摘要
        profile_summary = self._build_profile_summary(profile) if profile else "（暂无画像）"

        # 尝试加载提示词模板
        try:
            base_prompt = prompt_service.load_prompt("agents/observer")
            return base_prompt.format(
                analysis_depth=depth,
                conversation_summary=conversation_summary,
                profile_summary=profile_summary
            )
        except:
            # 使用默认提示词
            return self._get_default_analysis_prompt(depth, conversation_summary, profile_summary)

    def _build_conversation_summary(self, context: ConversationContext) -> str:
        """构建对话摘要"""
        if not context.conversation_history:
            return "无对话记录"

        summary_parts = []

        for msg in context.conversation_history[-20:]:  # 最近20条
            role = msg.get("role", "")
            content = msg.get("content", "")

            if role == "user":
                summary_parts.append(f"用户: {content}")
            elif role == "assistant":
                # 只显示前100字符
                short_content = content[:100] + "..." if len(content) > 100 else content
                summary_parts.append(f"助手: {short_content}")

            # 如果有工具调用，简要记录
            if msg.get("tool_calls"):
                tools = [tc["function"]["name"] for tc in msg["tool_calls"]]
                summary_parts.append(f"[调用工具: {', '.join(tools)}]")

        return "\n\n".join(summary_parts)

    def _build_profile_summary(self, profile: Any) -> str:
        """构建画像摘要"""
        if hasattr(profile, "model_dump"):
            profile_dict = profile.model_dump()
        elif isinstance(profile, dict):
            profile_dict = profile
        else:
            return "无法解析画像格式"

        parts = []

        # 关系状态
        relationships = profile_dict.get("relationships", {})
        if relationships.get("confidence", 0) > 0.5:
            parts.append(f"关系状态: {relationships.get('status', 'unknown')} (置信度: {relationships.get('confidence', 0)})")

        # 用户身份
        identity = profile_dict.get("identity", {})
        if identity.get("confidence", 0) > 0.5:
            parts.append(f"职业: {identity.get('occupation', 'unknown')}")

        # 个人喜好
        preferences = profile_dict.get("preferences", {})
        activities = preferences.get("activity_types", [])
        if activities:
            parts.append(f"喜欢的活动: {', '.join(activities[:5])}")

        # 个人习惯
        habits = profile_dict.get("habits", {})
        sleep = habits.get("sleep_schedule", "")
        if sleep:
            parts.append(f"作息: {sleep}")

        return "\n".join(parts) if parts else "暂无高置信度信息"

    def _get_default_analysis_prompt(self, depth: str, conversation_summary: str, profile_summary: str) -> str:
        """默认分析提示词"""
        return f"""你是 Observer（观察者），负责从用户行为中学习。

请进行{depth}分析，更新用户画像。

## 对话内容

{conversation_summary}

## 当前画像

{profile_summary}

## 你的任务

分析对话，提取用户行为信号，提出画像更新建议。

输出 JSON 格式：

{{
    "summary": "本次分析的主要发现（3-5句话）",
    "profile_updates": {{
        "relationships": {{"status": ["has_friends", "dating"], "confidence": 0.8}},
        "identity": {{"occupation": "程序员", "confidence": 0.9}},
        "preferences": {{"activity_types": ["健身", "阅读"]}},
        "habits": {{"sleep_schedule": "night_owl"}}
    }},
    "decision_profile_updates": {{
        "time_preference": {{"start_of_day": "09:00"}},
        "conflict_resolution": {{"strategy": "merge"}}
    }},
    "signals_extracted": [
        {{"type": "relationship", "value": "dating", "confidence": 0.85, "evidence": "提到女朋友"}},
        {{"type": "habit", "value": "night_owl", "confidence": 0.7, "evidence": "经常在晚上安排活动"}}
    ]
}}

只更新有明确证据支持的字段。置信度应该反映证据强度。
"""

    def _parse_analysis_response(self, response: str) -> Dict[str, Any]:
        """解析 LLM 分析响应"""
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
                "profile_updates": data.get("profile_updates", {}),
                "decision_profile_updates": data.get("decision_profile_updates", {}),
                "signals_extracted": data.get("signals_extracted", [])
            }

        except Exception as e:
            print(f"[Observer Agent] Failed to parse response: {e}")
            return {
                "success": False,
                "error": str(e)
            }

    async def _apply_updates(self, user_id: str, result: Dict[str, Any]):
        """应用画像更新"""
        # 获取现有画像
        profile = profile_service.get_or_create_profile(user_id)

        # 应用人格画像更新
        profile_updates = result.get("profile_updates", {})
        for category, updates in profile_updates.items():
            if category == "relationships":
                self._update_relationships(profile, updates)
            elif category == "identity":
                self._update_identity(profile, updates)
            elif category == "preferences":
                self._update_preferences(profile, updates)
            elif category == "habits":
                self._update_habits(profile, updates)

        # 保存更新后的画像
        profile_service.save_profile(user_id, profile)

        # 应用决策偏好更新
        decision_updates = result.get("decision_profile_updates", {})
        if decision_updates:
            try:
                from app.services.decision_profile_service import decision_profile_service
                decision_profile_service.apply_updates(user_id, decision_updates)
            except Exception as e:
                print(f"[Observer Agent] Error applying decision profile updates: {e}")

    def _update_relationships(self, profile: Any, updates: Dict[str, Any]):
        """更新关系状态"""
        if hasattr(profile, "relationships"):
            for key, value in updates.items():
                if key == "status":
                    # 支持添加和移除状态
                    if isinstance(value, list):
                        for s in value:
                            if s not in profile.relationships.status:
                                profile.relationships.status.append(s)
                    elif isinstance(value, str):
                        if value not in profile.relationships.status:
                            profile.relationships.status.append(value)
                elif key == "confidence":
                    profile.relationships.confidence = max(profile.relationships.confidence, value)

    def _update_identity(self, profile: Any, updates: Dict[str, Any]):
        """更新用户身份"""
        if hasattr(profile, "identity"):
            for key, value in updates.items():
                if hasattr(profile.identity, key):
                    setattr(profile.identity, key, value)
                if key == "confidence":
                    profile.identity.confidence = max(profile.identity.confidence, value)

    def _update_preferences(self, profile: Any, updates: Dict[str, Any]):
        """更新个人喜好"""
        if hasattr(profile, "preferences"):
            for key, value in updates.items():
                if key == "activity_types" and isinstance(value, list):
                    for activity in value:
                        if activity not in profile.preferences.activity_types:
                            profile.preferences.activity_types.append(activity)
                elif hasattr(profile.preferences, key):
                    setattr(profile.preferences, key, value)

    def _update_habits(self, profile: Any, updates: Dict[str, Any]):
        """更新个人习惯"""
        if hasattr(profile, "habits"):
            for key, value in updates.items():
                if hasattr(profile.habits, key):
                    setattr(profile.habits, key, value)

    async def generate_daily_diary(
        self,
        user_id: str,
        target_date: date
    ) -> Dict[str, Any]:
        """
        生成每日观察日记

        Args:
            user_id: 用户ID
            target_date: 目标日期

        Returns:
            {
                "success": bool,
                "diary": UserDiary (if successful),
                "skipped": bool,
                "reason": str (if skipped)
            }
        """
        try:
            # 检查日记是否已存在
            existing = diary_service.get_diary_by_date(user_id, target_date)
            if existing:
                return {
                    "success": True,
                    "diary": existing,
                    "skipped": True,
                    "reason": "Diary already exists for this date"
                }

            # 获取当天的对话
            conversations = conversation_service.get_recent_conversations(
                user_id=user_id,
                days=1,  # 只获取当天的对话
                limit=100
            )

            # 如果没有对话，跳过
            if not conversations:
                return {
                    "success": True,
                    "diary": None,
                    "skipped": True,
                    "reason": "No conversations found for this date"
                }

            # 收集所有消息
            all_messages = []
            conversation_count = len(conversations)
            message_count = 0
            tool_calls_count = 0

            for conv in conversations:
                messages = conversation_service.get_messages(conv.id, limit=100)
                message_count += len(messages)
                for msg in messages:
                    all_messages.append(msg.to_chat_format())
                    if msg.get("tool_calls"):
                        tool_calls_count += len(msg["tool_calls"])

            if not all_messages:
                return {
                    "success": True,
                    "diary": None,
                    "skipped": True,
                    "reason": "No messages found for this date"
                }

            # 构建分析提示
            prompt = self._build_diary_generation_prompt(target_date, all_messages, user_id)

            # 调用 LLM 生成日记
            messages_list = [{"role": "user", "content": prompt}]
            response = await self.llm.chat_completion(
                messages=messages_list,
                temperature=0.5
            )

            content = response.get("content", "")

            # 解析日记结果
            diary_data = self._parse_diary_response(content)

            if not diary_data.get("success"):
                return {
                    "success": False,
                    "diary": None,
                    "reason": diary_data.get("error", "Failed to parse diary")
                }

            # 创建日记
            diary = diary_service.create_daily_diary(
                user_id=user_id,
                diary_date=target_date,
                summary=diary_data["summary"],
                key_insights=diary_data["key_insights"],
                extracted_signals=diary_data.get("extracted_signals", []),
                conversation_count=conversation_count,
                message_count=message_count,
                tool_calls_count=tool_calls_count
            )

            return {
                "success": True,
                "diary": diary,
                "skipped": False
            }

        except Exception as e:
            print(f"[Observer Agent] Error generating diary: {e}")
            return {
                "success": False,
                "diary": None,
                "reason": str(e)
            }

    def _build_diary_generation_prompt(
        self,
        target_date: date,
        messages: List[Dict[str, Any]],
        user_id: str
    ) -> str:
        """构建日记生成提示"""
        # 构建对话摘要
        conversation_parts = []
        for msg in messages[-50:]:  # 最多50条消息
            role = msg.get("role", "")
            content = msg.get("content", "")[:200]  # 限制长度

            if role == "user":
                conversation_parts.append(f"用户: {content}")
            elif role == "assistant":
                conversation_parts.append(f"助手: {content}")

        conversation_summary = "\n".join(conversation_parts)

        return f"""你是观察者，需要为用户生成每日观察日记。

日期: {target_date.isoformat()}
用户ID: {user_id}

## 今天的对话记录

{conversation_summary}

## 你的任务

基于以上对话，生成一份每日观察日记。日记应该包含：

1. **summary**: 今天的活动摘要（2-3句话）
2. **key_insights**: 关键洞察
   - activities: 用户提到的主要活动（列表）
   - emotions: 情绪状态（列表）
   - patterns: 行为模式（列表）
   - time_preference: 时间偏好（早/中/晚）
   - decision_style: 决策风格（果断/犹豫/依赖）

3. **extracted_signals**: 提取的信号（可选）
   - type: 信号类型（relationship/identity/preference/habit）
   - value: 信号值
   - confidence: 置信度 (0.0-1.0)

输出 JSON 格式：

{{
    "summary": "今天用户主要...",
    "key_insights": {{
        "activities": ["开会", "健身"],
        "emotions": ["平静", "忙碌"],
        "patterns": ["倾向于下午安排会议"],
        "time_preference": "afternoon",
        "decision_style": "decisive"
    }},
    "extracted_signals": [
        {{"type": "habit", "value": "prefers_afternoon_meetings", "confidence": 0.7}}
    ]
}}

只根据对话内容生成，不要编造信息。
"""

    def _parse_diary_response(self, response: str) -> Dict[str, Any]:
        """解析日记生成响应"""
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
                "key_insights": data.get("key_insights", {}),
                "extracted_signals": data.get("extracted_signals", [])
            }

        except Exception as e:
            print(f"[Observer Agent] Failed to parse diary response: {e}")
            return {
                "success": False,
                "error": str(e)
            }


# 全局 Observer Agent 实例
observer_agent = ObserverAgent()
