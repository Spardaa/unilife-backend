"""
Observer Agent - 观察者 (简化版)
负责从用户行为中学习核心偏好
"""
from typing import Dict, Any, Optional, List
from datetime import datetime
import json

from app.services.llm import llm_service
from app.services.prompt import prompt_service
from app.services.profile_service import profile_service
from app.services.decision_profile_service import decision_profile_service
from app.services.conversation_service import conversation_service
from app.agents.base import (
    BaseAgent, ConversationContext, AgentResponse
)


class ObserverAgent(BaseAgent):
    """
    Observer Agent - 观察者（简化版）

    核心功能：
    - 学习用户冲突解决偏好
    - 提取用户显式规则
    - 记录场景决策模式

    移除的功能：
    - 日记生成
    - 细分画像更新（关系/身份/喜好/习惯）
    """

    name = "observer"

    def __init__(self):
        self.llm = llm_service

    async def process(self, context: ConversationContext) -> AgentResponse:
        """
        分析对话，提取核心偏好

        Args:
            context: 对话上下文

        Returns:
            AgentResponse: 分析结果
        """
        # 构建分析请求
        analysis_prompt = self._build_analysis_prompt(context)

        # 调用 LLM 分析
        messages = [{"role": "user", "content": analysis_prompt}]
        response = await self.llm.chat_completion(
            messages=messages,
            temperature=0.3
        )

        content = response.get("content", "")

        try:
            result = self._parse_response(content)

            if result.get("success"):
                await self._apply_updates(context.user_id, result)

                return AgentResponse(
                    content=f"[观察] 分析完成",
                    metadata={
                        "observer_result": True,
                        "updates": result.get("updates", {})
                    }
                )
            else:
                return AgentResponse(
                    content=f"[观察] 无需更新",
                    metadata={"observer_result": False}
                )

        except Exception as e:
            print(f"[Observer Agent] Error: {e}")
            return AgentResponse(
                content=f"[观察] 处理异常: {str(e)}",
                metadata={"observer_result": False, "error": str(e)}
            )

    async def analyze_conversation_batch(
        self,
        conversation_id: str,
        user_id: str,
        full_context: Optional[List[Dict]] = None
    ):
        """批量分析对话（主要触发方式）"""
        if not full_context:
            messages = conversation_service.get_messages(conversation_id, limit=50)
            full_context = [msg.to_chat_format() for msg in messages]

        analysis_context = ConversationContext(
            user_id=user_id,
            conversation_id=conversation_id,
            user_message="",
            conversation_history=full_context or []
        )

        try:
            await self.process(analysis_context)
        except Exception as e:
            print(f"[Observer Agent] Batch analysis error: {e}")

    def _build_analysis_prompt(self, context: ConversationContext) -> str:
        """构建分析提示词（简化版）"""
        conversation_summary = self._build_conversation_summary(context)

        return f"""分析以下对话，提取用户的决策偏好。

## 对话内容

{conversation_summary}

## 提取目标

1. **冲突策略**: 用户遇到时间冲突时的处理方式
   - ask: 询问用户
   - prioritize_urgent: 优先紧急事项
   - merge: 尝试合并

2. **显式规则**: 用户明确表达的规则（如"晚上不工作"）

3. **场景偏好**: 用户在特定场景下的选择模式

## 输出格式

只有当发现明确的偏好信号时才输出 JSON，否则返回 "无更新"：

```json
{{
    "has_updates": true,
    "conflict_strategy": "merge",
    "explicit_rules": ["周五晚上不工作"],
    "scenarios": {{
        "reschedule": {{"action": "next_available", "confidence": 0.7}}
    }}
}}
```

如果对话中没有明确的偏好信号，返回：
```json
{{"has_updates": false}}
```
"""

    def _build_conversation_summary(self, context: ConversationContext) -> str:
        """构建对话摘要"""
        if not context.conversation_history:
            return "无对话记录"

        parts = []
        for msg in context.conversation_history[-15:]:
            role = msg.get("role", "")
            content = msg.get("content", "")

            if role == "user":
                parts.append(f"用户: {content}")
            elif role == "assistant":
                short = content[:80] + "..." if len(content) > 80 else content
                parts.append(f"助手: {short}")

        return "\n\n".join(parts)

    def _parse_response(self, response: str) -> Dict[str, Any]:
        """解析 LLM 响应"""
        try:
            if "```json" in response:
                json_str = response.split("```json")[1].split("```")[0].strip()
            elif "```" in response:
                json_str = response.split("```")[1].split("```")[0].strip()
            else:
                json_str = response.strip()

            data = json.loads(json_str)

            if not data.get("has_updates"):
                return {"success": False}

            return {
                "success": True,
                "updates": {
                    "conflict_strategy": data.get("conflict_strategy"),
                    "explicit_rules": data.get("explicit_rules", []),
                    "scenarios": data.get("scenarios", {})
                }
            }

        except Exception as e:
            print(f"[Observer Agent] Parse error: {e}")
            return {"success": False}

    async def _apply_updates(self, user_id: str, result: Dict[str, Any]):
        """应用更新到决策偏好"""
        updates = result.get("updates", {})

        # 更新冲突策略
        if updates.get("conflict_strategy"):
            decision_profile_service.update_conflict_strategy(
                user_id,
                updates["conflict_strategy"]
            )

        # 添加显式规则
        for rule in updates.get("explicit_rules", []):
            decision_profile_service.add_explicit_rule(user_id, rule)
            profile_service.add_rule(user_id, rule)

        # 更新场景偏好
        for scenario_type, data in updates.get("scenarios", {}).items():
            decision_profile_service.update_scenario(
                user_id,
                scenario_type,
                data.get("action", ""),
                data.get("confidence", 0.5)
            )


# 全局 Observer Agent 实例
observer_agent = ObserverAgent()
