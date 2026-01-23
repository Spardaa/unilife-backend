"""
Jarvis Agent - AI Life Scheduling Assistant
基于 LLM + Tools 的智能代理，类似 Cursor Agent 的架构
"""
from typing import List, Dict, Any, Optional
from datetime import datetime
import json

from app.services.llm import llm_service
from app.services.prompt import prompt_service
from app.services.profile_service import profile_service
from app.agents.tools import tool_registry


class JarvisAgent:
    """
    Jarvis - AI 生活日程助理

    工作原理：
    1. 接收用户消息
    2. 使用 LLM 推理需要调用哪些工具
    3. 执行工具调用（数据库操作）
    4. 将工具结果反馈给 LLM
    5. LLM 生成自然语言回复
    6. 支持多步推理和工具链式调用
    """

    def __init__(self):
        self.llm = llm_service
        self.tools = tool_registry
        self.max_iterations = 30  # 支持复杂任务规划、多步骤决策

    async def chat(
        self,
        user_message: str,
        user_id: str,
        conversation_history: Optional[List[Dict[str, Any]]] = None,
        current_time: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        与用户对话的主入口

        Args:
            user_message: 用户的消息
            user_id: 用户ID
            conversation_history: 对话历史（可选）

        Returns:
            {
                "reply": "自然语言回复",
                "actions": [...],
                "tool_calls": [...],
                "conversation_history": [...]
            }
        """
        # 初始化对话历史
        if conversation_history is None:
            conversation_history = []

        # 构建消息列表
        messages = self._build_messages(user_id, conversation_history, user_message)

        # 对话循环 - LLM 可以多次调用工具
        iterations = 0
        tool_results = []
        all_tool_calls = []

        while iterations < self.max_iterations:
            iterations += 1

            # 获取系统提示
            system_prompt = self._get_system_prompt(user_id, current_time)
            messages_with_system = [{"role": "system", "content": system_prompt}] + messages

            # 调用 LLM（带 tools）
            tools_schema = self._convert_tools_to_openai_format()
            response = await self.llm.tools_calling(
                messages=messages_with_system,
                tools=tools_schema,
                tool_choice="auto"
            )

            # 检查是否有工具调用
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
                        function_args["user_id"] = user_id

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

        return {
            "reply": content or "抱歉，我没有理解您的需求。",
            "actions": actions,
            "tool_calls": all_tool_calls,
            "conversation_history": messages,
            "suggestions": suggestions
        }

    def _build_messages(
        self,
        user_id: str,
        history: List[Dict[str, Any]],
        user_message: str
    ) -> List[Dict[str, Any]]:
        """构建消息列表（不包含 system prompt）

        重要：必须保留完整的对话历史，包括 tool_calls 和 tool 消息，
        否则 AI 无法理解上下文和之前的操作。
        """
        messages = []

        # 跟踪最后一条 assistant 消息是否有 tool_calls
        last_assistant_had_tool_calls = False

        # 添加历史消息（保留最近15条，包含所有角色）
        for msg in history[-15:]:
            role = msg.get("role")

            if role == "user":
                messages.append({
                    "role": "user",
                    "content": msg.get("content", "")
                })
                last_assistant_had_tool_calls = False

            elif role == "assistant":
                # Assistant 消息可能包含 content 和 tool_calls
                assistant_msg = {}
                if msg.get("content"):
                    assistant_msg["content"] = msg["content"]

                # 保留 tool_calls（AI 调用的工具）
                if msg.get("tool_calls"):
                    assistant_msg["tool_calls"] = msg["tool_calls"]
                    last_assistant_had_tool_calls = True
                else:
                    last_assistant_had_tool_calls = False

                # 只有当有 content 或 tool_calls 时才添加
                if assistant_msg:
                    assistant_msg["role"] = "assistant"
                    messages.append(assistant_msg)

            elif role == "tool":
                # 工具执行结果 - 只有在前面有 tool_calls 时才保留
                # 这是 API 要求：tool 消息必须响应前面的 tool_calls
                if last_assistant_had_tool_calls:
                    messages.append({
                        "role": "tool",
                        "tool_call_id": msg.get("tool_call_id"),
                        "content": msg.get("content", "")
                    })
                # 否则跳过这个 tool 消息（数据不完整）

        # 添加当前用户消息
        messages.append({
            "role": "user",
            "content": user_message
        })

        return messages

    def _get_system_prompt(self, user_id: str, current_time: Optional[str] = None) -> str:
        """获取系统提示词，注入用户画像信息"""
        try:
            prompt = prompt_service.load_prompt("jarvis_system")

            # 注入用户画像（仅高置信度信息）
            profile_summary = profile_service.get_profile_summary(user_id)
            profile_section = self._build_profile_section(profile_summary)

            # 插入到"核心理念"之后（在系统提示词中作为固定规则的一部分）
            # 这样可以让 AI 对用户有更个性化的理解
            prompt = prompt.replace(
                "## 核心行为准则",
                f"{profile_section}\n\n## 核心行为准则"
            )

            # 替换时间占位符（使用传入的虚拟时间或当前时间）
            if current_time:
                prompt = prompt.replace("{current_time}", current_time)
            else:
                current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                prompt = prompt.replace("{current_time}", current_time)

            return prompt
        except:
            # 如果没有找到 prompt 文件，使用默认提示词
            return self._get_default_system_prompt(current_time, user_id)

    def _get_default_system_prompt(self, current_time: Optional[str] = None, user_id: str = None) -> str:
        """默认系统提示词（备用）"""
        if not current_time:
            current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # 构建画像部分（如果有 user_id）
        profile_section = ""
        if user_id:
            try:
                profile_summary = profile_service.get_profile_summary(user_id)
                profile_section = self._build_profile_section(profile_summary)
            except:
                pass  # 如果获取画像失败，忽略

        return f"""你是 Jarvis，UniLife 的智能生活日程助理。

{profile_section}

## 你的能力
你可以帮助用户管理日程、查询事件、查看能量状态等。你可以调用各种工具来完成这些任务。

## 工作流程
1. 理解用户的需求
2. 决定需要调用哪些工具
3. 执行工具调用
4. 基于工具结果生成友好的回复

## 注意事项
- 如果用户没有提供必要信息（如创建事件时没有时间），主动询问用户
- 回复要自然、友好、简洁
- 如果工具调用失败，向用户说明情况并提供建议
- 可以灵活组合多个工具来完成复杂任务

## 当前时间
现在是：{current_time}
""".format(current_time=current_time)

    def _build_profile_section(self, profile_summary: Dict[str, Any]) -> str:
        """
        构建用户画像部分（注入到系统提示词）

        只包含高置信度（>0.7）的信息，避免误导 AI
        """
        parts = []

        # 关系状态（高置信度）
        relationships = profile_summary.get("relationships", {})
        if relationships.get("confidence", 0) > 0.7:
            status_map = {
                "single": "单身",
                "dating": "约会中",
                "married": "已婚",
                "complicated": "感情状态复杂"
            }
            status = status_map.get(relationships.get("status"), relationships.get("status", ""))
            if status:
                parts.append(f"- 用户感情状态：{status}")

        # 用户身份（高置信度）
        identity = profile_summary.get("identity", {})
        if identity.get("confidence", 0) > 0.7:
            occupation = identity.get("occupation", "")
            if occupation and occupation != "unknown":
                parts.append(f"- 用户职业：{occupation}")

        # 个人喜好（只要有数据就包含）
        preferences = profile_summary.get("preferences", {})
        activities = preferences.get("activities", [])
        if activities:
            parts.append(f"- 用户喜欢的活动：{', '.join(activities[:5])}")

        social = preferences.get("social", "")
        if social and social != "unknown":
            social_map = {
                "introverted": "偏内向",
                "extroverted": "偏外向",
                "balanced": "社交平衡"
            }
            parts.append(f"- 社交倾向：{social_map.get(social, social)}")

        # 个人习惯（高置信度）
        habits = profile_summary.get("habits", {})
        sleep = habits.get("sleep", "")
        if sleep and sleep != "unknown":
            sleep_map = {
                "early_bird": "早起型",
                "night_owl": "夜猫子",
                "irregular": "作息不规律"
            }
            parts.append(f"- 作息习惯：{sleep_map.get(sleep, sleep)}")

        if not parts:
            return ""  # 没有高置信度信息，不添加画像部分

        return """## 关于用户（基于观察学习）

以下信息来自对用户行为的长期观察，请据此提供更个性化的服务：

""" + "\n".join(parts)

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
        """从工具结果中提取操作记录（用于前端显示）"""
        actions = []

        for result in tool_results:
            if not result.get("success"):
                continue

            if "event" in result:
                event = result["event"]
                if result.get("message", "").startswith("已创建"):
                    actions.append({
                        "type": "create_event",
                        "event_id": event["id"],
                        "event": event
                    })
                elif result.get("message", "").startswith("已更新"):
                    actions.append({
                        "type": "update_event",
                        "event_id": event["id"],
                        "event": event
                    })
                elif result.get("message", "").startswith("已删除"):
                    actions.append({
                        "type": "delete_event",
                        "event_id": event["id"],
                        "event": event
                    })
                elif result.get("message", "").startswith("已完成"):
                    actions.append({
                        "type": "complete_event",
                        "event_id": event["id"],
                        "event": event
                    })

        return actions

    def _extract_suggestions(self, tool_results: List[Dict[str, Any]]) -> Optional[List[Dict[str, Any]]]:
        """从工具结果中提取建议选项（用于交互式对话）"""
        for result in tool_results:
            if result.get("success") and "suggestions" in result:
                return result["suggestions"]
        return None


# 全局 Jarvis Agent 实例
jarvis_agent = JarvisAgent()
