"""
Persona Agent - 陪伴者
负责拟人化回复，无工具调用能力
"""
from typing import Dict, Any, Optional
from datetime import datetime
import json

from app.services.llm import llm_service
from app.services.prompt import prompt_service
from app.agents.base import (
    BaseAgent, ConversationContext, AgentResponse, build_messages_from_context
)


class PersonaAgent(BaseAgent):
    """
    Persona Agent - 陪伴者

    特点：
    - 有情感、有温度的拟人化回复
    - 无工具调用能力
    - 注入用户人格画像（情绪状态、交流风格）
    - 简洁有力的表达
    """

    name = "persona"

    def __init__(self):
        self.llm = llm_service

    async def process(self, context: ConversationContext) -> AgentResponse:
        """
        生成拟人化回复

        Args:
            context: 对话上下文（包含 Executor 结果、用户人格画像）

        Returns:
            AgentResponse: 包含拟人化回复内容
        """
        # 构建系统提示（注入人格画像）
        system_prompt = self._build_system_prompt(context)

        # 构建消息列表
        messages = build_messages_from_context(
            context=context,
            system_prompt=system_prompt,
            max_history=15
        )

        # 注入 Executor 结果（如果有）
        if context.executor_result:
            # 在用户消息前添加 Executor 结果的上下文
            executor_summary = self._format_executor_result(context.executor_result)
            if executor_summary:
                # 添加系统消息，告知 Executor 的执行结果
                messages.append({
                    "role": "system",
                    "content": f"## Executor 执行结果（请将这些信息告诉用户）\n\n{executor_summary}\n\n**重要**：如果查询到了事件或数据，你必须在回复中把这些信息展示给用户，不要只说\"我帮你查\"。"
                })

        # 注入建议选项（如果有）
        if context.suggestions:
            suggestions_text = self._format_suggestions(context.suggestions)
            if suggestions_text:
                messages.append({
                    "role": "system",
                    "content": f"## 给用户的选项\n\n{suggestions_text}\n\n**重要**：请把这些选项展示给用户，并引导用户选择。"
                })

        # 调用 LLM（不使用 tools）
        response = await self.llm.chat_completion(
            messages=messages,
            temperature=0.8  # 提高温度，让回复更有个性
        )

        content = response.get("content", "")

        # 提取元数据（情感状态、压力水平等）
        metadata = self._build_metadata(context)

        return AgentResponse(
            content=content,
            metadata=metadata
        )

    def _build_system_prompt(self, context: ConversationContext) -> str:
        """
        构建系统提示词，注入用户人格画像

        Args:
            context: 对话上下文

        Returns:
            系统提示词
        """
        # 获取基础提示词
        try:
            base_prompt = prompt_service.load_prompt("agents/persona")
        except:
            base_prompt = self._get_default_system_prompt()

        # 使用模板渲染
        try:
            rendered_prompt = prompt_service.render_with_profile(
                "agents/persona",
                user_profile=context.user_profile,
                current_time=context.current_time or datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
            )
            return rendered_prompt
        except:
            # 如果模板渲染失败，手动替换
            prompt = base_prompt

            # 替换时间
            current_time = context.current_time or datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
            prompt = prompt.replace("{current_time}", current_time)

            # 注入人格画像（简化版）
            if context.user_profile:
                profile = context.user_profile

                # 情绪状态
                emotional_state = self._extract_emotional_state(profile)
                if emotional_state:
                    prompt += f"\n\n## 用户当前状态\n\n情绪: {emotional_state}\n"

                # 社交倾向
                preferences = profile.get("preferences", {})
                social = preferences.get("social_preference", "")
                if social:
                    social_map = {
                        "introverted": "用户偏内向，喜欢简洁的交流",
                        "extroverted": "用户偏外向，可以多聊几句",
                        "balanced": "用户社交平衡"
                    }
                    prompt += f"{social_map.get(social, '')}\n"

                # 工作风格
                work_style = preferences.get("work_style", "")
                if work_style:
                    prompt += f"工作风格: {work_style}\n"

            return prompt

    def _get_default_system_prompt(self) -> str:
        """默认系统提示词（备用）"""
        return """你是 Persona（陪伴者），一个温暖、贴心、懂人心的 AI 助手。

## 核心定位
你是有情感、有温度的陪伴者。你的职责是理解用户的情感状态，提供温暖、贴心的回应。

## 回复特点
1. 简洁有力：通常1-3句话
2. 说到心里：理解用户的真实需求
3. 有温度：适当的同理心
4. 像真人：自然的表达

## 你不能
- 调用任何工具
- 执行任何操作
- 给予冗长的解释

## 你要
- 理解用户的情感
- 提供温暖的回应
- 简洁有力的表达
"""

    def _format_executor_result(self, executor_result: Dict[str, Any]) -> str:
        """
        格式化 Executor 的执行结果

        将结构化的执行结果转换为可读的文本，供 Persona 参考
        """
        if not executor_result:
            return ""

        parts = []

        # 优先使用 Executor 的原始内容（最重要！）
        executor_content = executor_result.get("executor_content", "")
        if executor_content:
            parts.append(f"## Executor 执行结果\n\n{executor_content}")

        # 查询结果（重要！需要展示给用户）
        query_results = executor_result.get("query_results", [])
        if query_results:
            for qr in query_results:
                if qr["type"] == "events":
                    events = qr.get("events", [])
                    if events:
                        parts.append(f"## 查询到 {len(events)} 个事件")
                        for e in events[:5]:  # 最多显示5个
                            title = e.get("title", "无标题")
                            start = e.get("start_time", "")
                            if start:
                                start = start[:16]  # 只显示日期和时间
                            parts.append(f"- {title} ({start})")
                        if len(events) > 5:
                            parts.append(f"... 还有 {len(events) - 5} 个事件")

                elif qr["type"] == "schedule_overview":
                    stats = qr.get("statistics", {})
                    events = qr.get("recent_events", [])
                    parts.append(f"## 日程概览")
                    if stats:
                        parts.append(f"- 总计: {stats.get('total', 0)} 个事件")
                        parts.append(f"- 待办: {stats.get('pending', 0)} 个")
                        parts.append(f"- 已完成: {stats.get('completed', 0)} 个")
                    if events:
                        parts.append("\n最近的事件:")
                        for e in events[:3]:
                            title = e.get("title", "无标题")
                            start = e.get("start_time", "")
                            if start:
                                start = start[:16]
                            parts.append(f"- {title} ({start})")

                elif qr["type"] == "statistics":
                    parts.append(f"## 统计信息")
                    for key, value in qr.get("data", {}).items():
                        parts.append(f"- {key}: {value}")

                elif qr["type"] == "routine":
                    routine = qr.get("routine", {})
                    parts.append(f"## 长期日程")
                    parts.append(f"- {routine.get('title', '无标题')}")

        # 操作结果
        operations = executor_result.get("operations_count", 0)
        if operations > 0:
            parts.append(f"- 已完成 {operations} 个操作")

        # 错误信息
        if executor_result.get("has_errors"):
            parts.append("- 执行过程中有错误")

        # 情感信号
        emotional_signals = executor_result.get("emotional_signals", [])
        if emotional_signals:
            parts.append(f"- 用户情感状态: {', '.join(emotional_signals)}")

        # 需要用户输入
        if executor_result.get("needs_user_input"):
            parts.append("- 需要用户提供更多信息")

        return "\n".join(parts) if parts else ""

    def _format_suggestions(self, suggestions: List[Dict[str, Any]]) -> str:
        """
        格式化建议选项

        将 suggestions 列表转换为可读的文本
        """
        if not suggestions:
            return ""

        parts = []
        for i, suggestion in enumerate(suggestions, 1):
            label = suggestion.get("label", "")
            description = suggestion.get("description", "")
            if description:
                parts.append(f"- {i}. {label}: {description}")
            else:
                parts.append(f"- {i}. {label}")

        # 添加提示信息
        parts.append("\n用户可以直接输入数字选择，或者自由输入其他内容。")

        return "\n".join(parts)

    def _extract_emotional_state(self, profile: Dict[str, Any]) -> str:
        """从画像中提取情绪状态"""
        # 简化实现
        return "平静"

    def _build_metadata(self, context: ConversationContext) -> Dict[str, Any]:
        """
        构建元数据

        包含：
        - 情感状态
        - 压力水平
        - 交流风格
        """
        metadata = {
            "persona_response": True,
            "emotional_state": "平静",
            "stress_level": "中等",
            "communication_style": "balanced"
        }

        if context.user_profile:
            preferences = context.user_profile.get("preferences", {})

            # 社交倾向 → 交流风格
            social = preferences.get("social_preference", "")
            if social:
                metadata["communication_style"] = social

        return metadata


# 全局 Persona Agent 实例
persona_agent = PersonaAgent()
