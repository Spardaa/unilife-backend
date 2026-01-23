"""
Executor Agent - 理性执行者
负责工具调用和操作执行，无情感，纯逻辑
"""
from typing import Dict, Any, Optional, List
from datetime import datetime
import json

from app.services.llm import llm_service
from app.services.prompt import prompt_service
from app.agents.base import (
    BaseAgent, ConversationContext, AgentResponse, build_messages_from_context
)
from app.agents.tools import tool_registry


class ExecutorAgent(BaseAgent):
    """
    Executor Agent - 理性执行者

    特点：
    - 无情感、纯逻辑输出
    - 专注于工具调用和操作执行
    - 注入用户决策偏好进行智能决策
    - 返回结构化执行结果
    """

    name = "executor"

    def __init__(self):
        self.llm = llm_service
        self.tools = tool_registry
        self.max_iterations = 30  # 支持复杂多步操作

    async def process(self, context: ConversationContext) -> AgentResponse:
        """
        处理操作请求，执行工具调用

        Args:
            context: 对话上下文（包含用户决策偏好）

        Returns:
            AgentResponse: 包含执行结果、操作记录、元数据
        """
        # 构建系统提示（注入决策偏好和 user_id）
        system_prompt = self._build_system_prompt(context)

        # 在系统提示中明确告知 user_id
        system_prompt += f"\n\n## 当前用户\n\n用户ID: {context.user_id}\n在调用需要 user_id 的工具时，请直接使用此 ID，不需要询问用户。"

        # 构建消息列表
        messages = build_messages_from_context(
            context=context,
            system_prompt=system_prompt,
            max_history=15
        )

        # 对话循环 - 支持多步工具调用
        iterations = 0
        tool_results = []
        all_tool_calls = []

        while iterations < self.max_iterations:
            iterations += 1

            # 获取工具列表（OpenAI 格式）
            tools_schema = self._convert_tools_to_openai_format()

            # 调用 LLM
            response = await self.llm.tools_calling(
                messages=messages,
                tools=tools_schema,
                tool_choice="auto",
                temperature=0.3  # 降低温度，更确定性
            )

            tool_calls = response.get("tool_calls")
            content = response.get("content")

            if tool_calls:
                # LLM 决定调用工具
                all_tool_calls.extend(tool_calls)
                messages.append({
                    "role": "assistant",
                    "content": content,
                    "tool_calls": tool_calls
                })

                # 执行所有工具调用
                for tool_call in tool_calls:
                    function_name = tool_call["function"]["name"]
                    function_args = json.loads(tool_call["function"]["arguments"])

                    # 添加 user_id 到参数（如果工具需要但用户没提供）
                    if "user_id" in str(tool_call["function"]) and "user_id" not in function_args:
                        function_args["user_id"] = context.user_id

                    # 执行工具
                    result = await self.tools.call_tool(function_name, function_args)
                    tool_results.append(result)

                    # 将工具结果添加到消息中
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tool_call["id"],
                        "content": json.dumps(result, ensure_ascii=False)
                    })

                # 继续循环，让 LLM 看到工具结果后决定下一步
                continue
            else:
                # LLM 没有调用工具，返回最终回复
                messages.append({
                    "role": "assistant",
                    "content": content
                })
                break

        # 提取操作记录
        actions = self._extract_actions(tool_results)

        # 提取建议选项
        suggestions = self._extract_suggestions(tool_results)

        # 提取元数据（供 Persona 使用），传入 Executor 的 content
        metadata = self._build_metadata(tool_results, context, content or "")

        return AgentResponse(
            content=content or "抱歉，我没有理解您的需求。",
            actions=actions,
            tool_calls=all_tool_calls,
            metadata=metadata,
            suggestions=suggestions
        )

    def _build_system_prompt(self, context: ConversationContext) -> str:
        """
        构建系统提示词，注入用户决策偏好

        Args:
            context: 对话上下文

        Returns:
            系统提示词
        """
        # 获取基础提示词
        try:
            base_prompt = prompt_service.load_prompt("agents/executor")
        except:
            base_prompt = self._get_default_system_prompt()

        # 使用模板渲染
        try:
            rendered_prompt = prompt_service.render_with_profile(
                "agents/executor",
                user_decision_profile=context.user_decision_profile,
                current_time=context.current_time or datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
            )
            return rendered_prompt
        except:
            # 如果模板渲染失败，手动替换
            prompt = base_prompt

            # 替换时间
            current_time = context.current_time or datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
            prompt = prompt.replace("{current_time}", current_time)

            # 注入决策偏好（简化版）
            if context.user_decision_profile:
                decision = context.user_decision_profile
                prompt += "\n\n## 用户决策偏好\n\n"

                # 冲突解决策略
                conflict = decision.get("conflict_resolution", {})
                strategy = conflict.get("strategy", "ask")
                if strategy:
                    strategy_map = {
                        "ask": "遇到冲突时询问用户",
                        "prioritize_urgent": "冲突时优先处理紧急事项",
                        "prioritize_important": "冲突时优先处理重要事项",
                        "merge": "冲突时尝试合并事项"
                    }
                    prompt += f"- 冲突策略: {strategy_map.get(strategy, strategy)}\n"

                # 会议偏好
                meeting = decision.get("meeting_preference", {})
                stacking = meeting.get("stacking_style", "flexible")
                if stacking:
                    stacking_map = {
                        "stacked": "连续安排会议",
                        "spaced": "分散安排会议",
                        "flexible": "灵活安排会议"
                    }
                    prompt += f"- 会议风格: {stacking_map.get(stacking, stacking)}\n"

                # 显式规则
                rules = decision.get("explicit_rules", [])
                if rules:
                    prompt += "- 用户规则:\n"
                    for rule in rules:
                        prompt += f"  - {rule}\n"

            return prompt

    def _get_default_system_prompt(self) -> str:
        """默认系统提示词（备用）"""
        current_time = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
        return f"""你是 Executor（执行官），负责处理用户的操作请求。

## 核心定位
你是理性的、无情感的执行者。专注于高效执行，不需要寒暄、共情或闲聊。

## 你的能力
你可以调用各种工具来管理事件、查询日程、分析冲突等。

## 决策原则
1. 当信息缺失时，使用合理默认值
2. 删除事件需要 >= 80% 置信度
3. 遇到冲突时，先分析再决定

## 输出格式
简洁的执行报告，格式：
[执行结果] 操作内容
[需要信息] 所需信息
[发现冲突] 冲突描述

## 需要用户提供选项时
当需要用户提供选择时，使用 `provide_suggestions` 工具。**重要**：
1. 选项必须带数字编号，方便用户输入数字选择
2. 格式：`- 1. 选项内容` 或 `1. 选项内容`
3. 提供 2-4 个选项，不要太多
4. 最后提醒用户可以输入数字或自由输入

示例：
```
[需要信息] 请选择健身的具体时间
- 1. 明天上午8:00-9:00
- 2. 明天上午9:00-10:00
- 3. 明天上午10:00-11:00

输入数字 1/2/3 选择，或手动输入其他时间
```

## 当前时间
{current_time}
"""

    def _convert_tools_to_openai_format(self) -> List[Dict[str, Any]]:
        """将工具转换为 OpenAI API 格式"""
        tools = self.tools.list_tools()
        openai_tools = []

        for tool in tools:
            openai_tools.append({
                "type": "function",
                "function": {
                    "name": tool["name"],
                    "description": tool["description"],
                    "parameters": tool["parameters"]
                }
            })

        return openai_tools

    def _extract_actions(self, tool_results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """从工具结果中提取操作记录"""
        actions = []

        for result in tool_results:
            if not result.get("success"):
                continue

            if "event" in result:
                event = result["event"]
                message = result.get("message", "")

                if message.startswith("已创建"):
                    actions.append({
                        "type": "create_event",
                        "event_id": event.get("id"),
                        "event": event
                    })
                elif message.startswith("已更新") or message.startswith("已修改"):
                    actions.append({
                        "type": "update_event",
                        "event_id": event.get("id"),
                        "event": event
                    })
                elif message.startswith("已删除") or message.startswith("已取消"):
                    actions.append({
                        "type": "delete_event",
                        "event_id": event.get("id"),
                        "event": event
                    })
                elif message.startswith("已完成"):
                    actions.append({
                        "type": "complete_event",
                        "event_id": event.get("id"),
                        "event": event
                    })

            if "routine" in result:
                routine = result["routine"]
                actions.append({
                    "type": "create_routine",
                    "routine_id": routine.get("id"),
                    "routine": routine
                })

            if "template" in result:
                template = result["template"]
                actions.append({
                    "type": "create_routine_template",
                    "template_id": template.get("id"),
                    "template": template
                })

        return actions

    def _extract_suggestions(self, tool_results: List[Dict[str, Any]]) -> Optional[List[Dict[str, Any]]]:
        """从工具结果中提取建议选项"""
        for result in tool_results:
            if result.get("success") and "suggestions" in result:
                return result["suggestions"]
        return None

    def _build_metadata(
        self,
        tool_results: List[Dict[str, Any]],
        context: ConversationContext,
        executor_content: str = ""
    ) -> Dict[str, Any]:
        """
        构建元数据（供 Persona Agent 使用）

        包含：
        - 执行的操作
        - 查询结果（用于展示给用户）
        - 检测到的情感信号
        - 需要的用户输入
        - 错误信息
        - executor_content: Executor 的原始回复内容
        """
        metadata = {
            "executor_result": True,
            "operations_count": len(self._extract_actions(tool_results)),
            "has_errors": any(not r.get("success") for r in tool_results),
            "emotional_signals": [],
            "needs_user_input": False,
            "query_results": [],  # 新增：查询结果
            "executor_content": executor_content  # 新增：Executor 的原始内容
        }

        # 提取查询结果
        for result in tool_results:
            if result.get("success"):
                # 提取查询类工具的结果
                if "events" in result:
                    metadata["query_results"].append({
                        "type": "events",
                        "count": result.get("count", 0),
                        "events": result.get("events", [])[:10]  # 最多10个
                    })
                elif "statistics" in result:
                    metadata["query_results"].append({
                        "type": "statistics",
                        "data": result.get("statistics", {})
                    })
                elif "routine" in result:
                    metadata["query_results"].append({
                        "type": "routine",
                        "routine": result.get("routine", {})
                    })
                elif "snapshots" in result:
                    metadata["query_results"].append({
                        "type": "snapshots",
                        "count": result.get("count", 0)
                    })
                elif "schedule_overview" in result or "recent_events" in result:
                    metadata["query_results"].append({
                        "type": "schedule_overview",
                        "statistics": result.get("statistics", {}),
                        "recent_events": result.get("recent_events", [])[:10]
                    })

        # 检测情感信号（从用户消息中）
        message_lower = context.user_message.lower()
        emotion_keywords = {
            "压力大": "stress",
            "累": "tired",
            "忙": "busy",
            "烦": "annoyed",
            "开心": "happy",
            "高兴": "happy",
            "难过": "sad",
            "焦虑": "anxious"
        }

        for keyword, emotion in emotion_keywords.items():
            if keyword in message_lower:
                metadata["emotional_signals"].append(emotion)

        # 检查是否需要用户输入
        for result in tool_results:
            if "需要" in result.get("message", ""):
                metadata["needs_user_input"] = True
                break

        return metadata


# 全局 Executor Agent 实例
executor_agent = ExecutorAgent()
