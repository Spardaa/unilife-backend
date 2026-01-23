"""
Router Agent - Intent recognition and routing with context filtering
重构版：实现 BaseAgent 接口，使用新的 tools_calling API
支持智能上下文筛选
"""
from typing import Dict, Any, Optional, List
from app.services.llm import llm_service
from app.services.prompt import prompt_service
from app.agents.base import (
    BaseAgent, ConversationContext, AgentResponse,
    Intent, IntentConfidence, RoutingDecision,
    build_messages_from_context
)
import json


class RouterAgent(BaseAgent):
    """
    路由器 Agent - 负责意图识别、路由决策和上下文筛选

    判断用户消息应该由哪些 Agent 处理：
    - EXECUTOR: 只需要 Executor（工具调用）
    - PERSONA: 只需要 Persona（聊天）
    - BOTH: 需要先 Executor 后 Persona（混合意图）

    同时筛选相关的上下文传递给下游 Agent
    """

    name = "router"

    def __init__(self):
        self.llm = llm_service

    async def process(self, context: ConversationContext) -> AgentResponse:
        """
        处理用户消息，返回路由决策和筛选后的上下文

        Args:
            context: 对话上下文

        Returns:
            AgentResponse: 包含意图分类、路由决策和筛选后的上下文
        """
        # 获取最近的对话历史（用于路由决策）
        messages = build_messages_from_context(
            context=context,
            system_prompt=self._get_system_prompt(),
            max_history=15
        )

        # 定义路由工具
        tools = [
            {
                "type": "function",
                "function": {
                    "name": "route_and_filter",
                    "description": "分析用户消息的意图、决定路由策略，并筛选相关的对话上下文",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "intent": {
                                "type": "string",
                                "enum": [i.value for i in Intent],
                                "description": "用户意图类型"
                            },
                            "routing": {
                                "type": "string",
                                "enum": [r.value for r in RoutingDecision],
                                "description": "路由决策：executor(需要工具), persona(纯聊天), both(混合)"
                            },
                            "confidence": {
                                "type": "number",
                                "description": "置信度 (0.0 - 1.0)"
                            },
                            "reasoning": {
                                "type": "string",
                                "description": "判断理由"
                            },
                            "related_context_count": {
                                "type": "integer",
                                "description": "需要保留的连续相关上下文条数（从最新往回数），不包括当前用户消息。默认3-5条，如果上下文不相关则为0"
                            }
                        },
                        "required": ["intent", "routing", "confidence", "reasoning", "related_context_count"]
                    }
                }
            }
        ]

        try:
            # 调用 LLM
            response = await self.llm.tools_calling(
                messages=messages,
                tools=tools,
                tool_choice="required",  # 必须调用工具
                temperature=0.3
            )

            # 解析结果
            tool_calls = response.get("tool_calls")
            if tool_calls and len(tool_calls) > 0:
                function_args = json.loads(tool_calls[0]["function"]["arguments"])

                intent = Intent.from_string(function_args.get("intent", Intent.UNKNOWN))
                routing = RoutingDecision(function_args.get("routing", "persona"))
                confidence = function_args.get("confidence", 0.5)
                reasoning = function_args.get("reasoning", "")
                related_context_count = function_args.get("related_context_count", 3)

                # 筛选相关上下文
                filtered_context = self._filter_context(
                    context.conversation_history,
                    related_context_count
                )

                # 构建响应
                return AgentResponse(
                    content=f"[路由] 意图: {intent.value}, 路由: {routing.value}, 置信度: {confidence:.2f}, 保留上下文: {len(filtered_context)}条",
                    metadata={
                        "intent": intent.value,
                        "routing": routing.value,
                        "confidence": confidence,
                        "reasoning": reasoning,
                        "original_context_count": len(context.conversation_history),
                        "filtered_context_count": len(filtered_context)
                    },
                    should_route_to=routing,
                    filtered_context=filtered_context
                )

            # Fallback: 如果没有工具调用，使用关键词匹配
            return self._fallback_routing(context)

        except Exception as e:
            print(f"[Router Agent] Error: {e}")
            # 降级到关键词匹配
            return self._fallback_routing(context)

    def _filter_context(
        self,
        conversation_history: List[Dict[str, Any]],
        count: int
    ) -> List[Dict[str, Any]]:
        """
        筛选相关的上下文

        从最新的消息开始，保留连续的count条消息

        Args:
            conversation_history: 完整的对话历史
            count: 需要保留的消息条数

        Returns:
            筛选后的上下文列表
        """
        if count <= 0 or not conversation_history:
            return []

        # 从最新往回取count条消息
        return conversation_history[-count:]

    def _get_system_prompt(self) -> str:
        """获取系统提示词"""
        try:
            return prompt_service.load_prompt("agents/router")
        except:
            # 备用提示词
            return """你是智能路由器，负责分析用户意图、决定路由策略，并筛选相关的对话上下文。

## 核心任务
1. 分析用户消息，判断意图类型
2. 决定路由策略（executor/persona/both）
3. 筛选与当前消息相关的对话上下文

## 路由选项
- executor: 需要调用工具（创建、查询、修改事件等）
- persona: 纯聊天（问候、闲聊、感谢等）
- both: 混合意图（既需要操作工具，也需要情感化回复）

## 上下文筛选规则

你需要判断需要保留多少条历史上下文（related_context_count）：

**规则1：回答问题/补全信息** → 保留3-5条
- 用户消息简短（如时间、数字、yes/no）
- 上一条助手消息在询问或提供选项
- 需要保留之前的对话轮次以便理解上下文

**规则2：独立新请求** → 保留0-2条
- 用户明确表达了新的完整意图
- 之前的话题与此请求无关
- 减少token消耗，提高响应速度

**规则3：修改/查询之前的内容** → 保留5-8条
- 用户提到"刚才"、"之前"、"那个"
- 需要引用之前创建/讨论的内容
- 需要更多上下文来定位具体对象

**规则4：纯聊天** → 保留2-3条
- 问候、闲聊等
- 保留最近几条以维持对话连贯性

## 判断示例

示例1: "明天上午健身"
- intent: CREATE_EVENT, routing: executor
- related_context_count: 0（独立新请求，不需要历史）

示例2: "上午10点"（上下文：助手刚问了"请选择健身时间"）
- intent: CREATE_EVENT, routing: executor
- related_context_count: 4（需要包含之前的问答）

示例3: "刚才说的会议改到下午"
- intent: UPDATE_EVENT, routing: executor
- related_context_count: 6（需要找到之前创建的会议）

示例4: "你好"
- intent: GREETING, routing: persona
- related_context_count: 2（保留最近对话即可）

示例5: "帮我查明天的日程"
- intent: QUERY_EVENT, routing: executor
- related_context_count: 0（独立查询请求）

## 意图类型
- CREATE_EVENT, QUERY_EVENT, UPDATE_EVENT, DELETE_EVENT
- GREETING, THANKS, GOODBYE, CHITCHAT
- CHECK_ENERGY, SUGGEST_SCHEDULE
- MIXED (混合意图)

调用 route_and_filter 函数返回你的判断。"""

    def _fallback_routing(self, context: ConversationContext) -> AgentResponse:
        """
        降级路由：使用关键词匹配

        当 LLM 调用失败时使用
        """
        message_lower = context.user_message.lower()

        # 检查是否是聊天类
        if any(kw in message_lower for kw in ["你好", "hi", "hello", "早上好", "下午好", "晚上好"]):
            return AgentResponse(
                content="[路由] 问候 → persona",
                metadata={"intent": Intent.GREETING.value, "routing": "persona", "confidence": 0.9},
                should_route_to=RoutingDecision.PERSONA,
                filtered_context=self._filter_context(context.conversation_history, 2)
            )

        if any(kw in message_lower for kw in ["谢谢", "感谢", "thanks", "thank"]):
            return AgentResponse(
                content="[路由] 感谢 → persona",
                metadata={"intent": Intent.THANKS.value, "routing": "persona", "confidence": 0.9},
                should_route_to=RoutingDecision.PERSONA,
                filtered_context=self._filter_context(context.conversation_history, 2)
            )

        if any(kw in message_lower for kw in ["再见", "拜拜", "goodbye", "bye"]):
            return AgentResponse(
                content="[路由] 告别 → persona",
                metadata={"intent": Intent.GOODBYE.value, "routing": "persona", "confidence": 0.9},
                should_route_to=RoutingDecision.PERSONA,
                filtered_context=self._filter_context(context.conversation_history, 2)
            )

        # 检查是否有情感表达
        emotion_keywords = ["压力大", "累", "忙", "烦", "开心", "高兴", "难过", "焦虑"]
        has_emotion = any(kw in message_lower for kw in emotion_keywords)

        # 检查是否有操作意图
        action_keywords = ["安排", "计划", "创建", "添加", "查询", "查看", "修改", "更新", "删除", "取消"]
        has_action = any(kw in message_lower for kw in action_keywords)

        # 判断路由和上下文数量
        if has_emotion and has_action:
            # 混合意图，保留较少上下文
            return AgentResponse(
                content="[路由] 混合意图 → both",
                metadata={"intent": Intent.MIXED.value, "routing": "both", "confidence": 0.7},
                should_route_to=RoutingDecision.BOTH,
                filtered_context=self._filter_context(context.conversation_history, 3)
            )
        elif has_action:
            # 操作意图
            if "安排" in message_lower or "创建" in message_lower or "添加" in message_lower:
                intent = Intent.CREATE_EVENT
                context_count = 0  # 新建通常不需要历史
            elif "查询" in message_lower or "查看" in message_lower:
                intent = Intent.QUERY_EVENT
                context_count = 0  # 查询通常不需要历史
            elif "修改" in message_lower or "更新" in message_lower:
                intent = Intent.UPDATE_EVENT
                context_count = 6  # 修改需要更多上下文定位
            elif "删除" in message_lower or "取消" in message_lower:
                intent = Intent.DELETE_EVENT
                context_count = 6  # 删除需要更多上下文定位
            else:
                intent = Intent.UNKNOWN
                context_count = 3

            return AgentResponse(
                content=f"[路由] 操作意图 → executor",
                metadata={"intent": intent.value, "routing": "executor", "confidence": 0.7},
                should_route_to=RoutingDecision.EXECUTOR,
                filtered_context=self._filter_context(context.conversation_history, context_count)
            )
        else:
            # 默认为聊天
            return AgentResponse(
                content="[路由] 默认聊天 → persona",
                metadata={"intent": Intent.CHITCHAT.value, "routing": "persona", "confidence": 0.5},
                should_route_to=RoutingDecision.PERSONA,
                filtered_context=self._filter_context(context.conversation_history, 2)
            )


# 全局 Router Agent 实例
router_agent = RouterAgent()
