"""
Context Filter Agent - 轻量级上下文筛选器
专门用于在调用 UnifiedAgent 前筛选上下文，减少 Token 消耗

设计目标：
- 仅做上下文筛选，不做路由决策
- 尽可能轻量，快速响应
- 支持降级到关键词匹配
"""
from typing import Dict, Any, Optional, List
import json
import logging

from app.services.llm import llm_service
from app.services.prompt import prompt_service
from app.agents.base import (
    BaseAgent, ConversationContext, AgentResponse, build_messages_from_context
)


logger = logging.getLogger("context_filter")


class ContextFilterAgent(BaseAgent):
    """
    上下文筛选 Agent - 轻量级版本
    
    职责：
    - 分析用户消息，判断需要保留多少条历史上下文
    - 筛选相关上下文传递给 UnifiedAgent
    
    不负责：
    - 意图分类
    - 路由决策
    """
    
    name = "context_filter"
    
    def __init__(self):
        self.llm = llm_service
    
    async def process(self, context: ConversationContext) -> AgentResponse:
        """
        分析用户消息，返回筛选后的上下文
        
        Args:
            context: 对话上下文
        
        Returns:
            AgentResponse: 包含筛选后的上下文
        """
        # 如果历史很短，直接返回全部
        if len(context.conversation_history) <= 3:
            return AgentResponse(
                content=f"[Filter] 历史较短，保留全部 {len(context.conversation_history)} 条",
                metadata={
                    "original_count": len(context.conversation_history),
                    "filtered_count": len(context.conversation_history),
                    "filter_method": "short_history"
                },
                filtered_context=context.conversation_history
            )
        
        # 尝试使用 LLM 智能筛选
        try:
            filtered_context = await self._llm_filter(context)
            return AgentResponse(
                content=f"[Filter] LLM筛选，保留 {len(filtered_context)} 条",
                metadata={
                    "original_count": len(context.conversation_history),
                    "filtered_count": len(filtered_context),
                    "filter_method": "llm"
                },
                filtered_context=filtered_context
            )
        except Exception as e:
            logger.warning(f"LLM filter failed: {e}, using fallback")
            # 降级到关键词匹配
            filtered_context = self._fallback_filter(context)
            return AgentResponse(
                content=f"[Filter] 关键词筛选，保留 {len(filtered_context)} 条",
                metadata={
                    "original_count": len(context.conversation_history),
                    "filtered_count": len(filtered_context),
                    "filter_method": "fallback"
                },
                filtered_context=filtered_context
            )
    
    async def _llm_filter(self, context: ConversationContext) -> List[Dict[str, Any]]:
        """
        使用 LLM 智能判断需要保留多少上下文
        """
        # 构建简化的消息列表（只需要最近几条历史用于判断）
        system_prompt = self._get_system_prompt()
        
        # 只传入最近 10 条历史供 LLM 判断
        recent_history = context.conversation_history[-10:] if len(context.conversation_history) > 10 else context.conversation_history
        
        messages = [
            {"role": "system", "content": system_prompt},
        ]
        
        # 添加历史消息摘要（减少 token）
        if recent_history:
            history_summary = self._summarize_history(recent_history)
            messages.append({
                "role": "system",
                "content": f"最近的对话历史（共 {len(recent_history)} 条）:\n{history_summary}"
            })
        
        # 添加当前用户消息
        messages.append({
            "role": "user",
            "content": context.user_message
        })
        
        # 定义筛选工具
        tools = [
            {
                "type": "function",
                "function": {
                    "name": "filter_context",
                    "description": "决定需要保留多少条历史上下文",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "related_context_count": {
                                "type": "integer",
                                "description": "需要保留的历史消息条数 (0-10)"
                            },
                            "reason": {
                                "type": "string",
                                "description": "简短理由"
                            }
                        },
                        "required": ["related_context_count"]
                    }
                }
            }
        ]
        
        # 调用 LLM
        response = await self.llm.tools_calling(
            messages=messages,
            tools=tools,
            tool_choice="required",
            temperature=0.2  # 低温度，更确定性
        )
        
        # 解析结果
        tool_calls = response.get("tool_calls")
        if tool_calls and len(tool_calls) > 0:
            function_args = json.loads(tool_calls[0]["function"]["arguments"])
            count = function_args.get("related_context_count", 3)
            count = max(0, min(count, 10))  # 限制范围
            
            reason = function_args.get("reason", "")
            logger.debug(f"LLM filter: keep {count} messages, reason: {reason}")
            
            return self._slice_context(context.conversation_history, count)
        
        # 如果没有工具调用，使用默认值
        return self._slice_context(context.conversation_history, 3)
    
    def _summarize_history(self, history: List[Dict[str, Any]]) -> str:
        """
        生成历史消息摘要（减少 token 消耗）
        """
        lines = []
        for i, msg in enumerate(history):
            role = msg.get("role", "unknown")
            content = msg.get("content", "")
            # 截断过长的消息
            if len(content) > 50:
                content = content[:50] + "..."
            lines.append(f"{i+1}. [{role}] {content}")
        return "\n".join(lines)
    
    def _slice_context(self, history: List[Dict[str, Any]], count: int) -> List[Dict[str, Any]]:
        """从历史末尾取指定条数"""
        if count <= 0:
            return []
        return history[-count:]
    
    def _fallback_filter(self, context: ConversationContext) -> List[Dict[str, Any]]:
        """
        降级筛选：使用关键词匹配
        """
        message = context.user_message.lower()
        history = context.conversation_history
        
        # 短回复（可能是回答问题）→ 需要更多上下文
        if len(message) < 10:
            # 纯数字或简短回复
            if message.isdigit() or message in ["好", "好的", "行", "可以", "是", "不", "否"]:
                return self._slice_context(history, 5)
        
        # 引用之前的内容 → 需要较多上下文
        reference_keywords = ["刚才", "之前", "那个", "这个", "上次", "改一下", "取消它"]
        if any(kw in message for kw in reference_keywords):
            return self._slice_context(history, 8)
        
        # 完整的新请求 → 不需要太多上下文
        new_request_patterns = [
            "帮我", "请", "安排", "创建", "添加", "查询", "查看",
            "明天", "今天", "后天", "下周"
        ]
        if any(pattern in message for pattern in new_request_patterns) and len(message) > 15:
            return self._slice_context(history, 2)
        
        # 问候/闲聊 → 保留少量上下文
        chat_keywords = ["你好", "hi", "hello", "谢谢", "再见"]
        if any(kw in message for kw in chat_keywords):
            return self._slice_context(history, 2)
        
        # 默认保留 3 条
        return self._slice_context(history, 3)
    
    def _get_system_prompt(self) -> str:
        """获取系统提示词"""
        try:
            return prompt_service.load_prompt("agents/context_filter")
        except:
            return """你是一个轻量级的上下文筛选器。
判断当前用户消息需要保留多少条历史上下文（0-10条）。

规则：
- 独立新请求（信息完整）→ 0-1 条
- 简单延续对话 → 2-3 条  
- 回答问题/补充信息 → 4-5 条
- 引用/修改之前内容 → 6-10 条

调用 filter_context 工具返回结果。"""


# 全局实例
context_filter_agent = ContextFilterAgent()
