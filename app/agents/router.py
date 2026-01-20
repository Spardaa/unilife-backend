"""
RouterAgent - Intent recognition and routing
"""
from typing import Dict, Any
from app.services.llm import llm_service
from app.services.prompt import prompt_service
from app.agents.intent import Intent, IntentConfidence


class RouterAgent:
    """
    Agent responsible for recognizing user intent and routing to appropriate downstream agents
    """

    def __init__(self):
        self.llm = llm_service
        self._system_prompt_cache = None

    def _get_system_prompt(self) -> str:
        """Get system prompt from external file"""
        if self._system_prompt_cache is None:
            self._system_prompt_cache = prompt_service.load_prompt("router_agent")
        return self._system_prompt_cache

    async def classify_intent(
        self,
        user_message: str,
        user_id: str,
        conversation_history: list = None
    ) -> IntentConfidence:
        """
        Classify user intent from natural language message

        Args:
            user_message: User's natural language input
            user_id: User ID for context
            conversation_history: Optional conversation history

        Returns:
            IntentConfidence with classified intent and confidence score
        """
        # Build system prompt for intent classification
        system_prompt = self._get_system_prompt()

        # Build user messages
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message}
        ]

        # Add conversation history if available
        if conversation_history:
            messages.extend(conversation_history[-5:])  # Keep last 5 messages

        # Define function for intent classification
        functions = [
            {
                "name": "classify_user_intent",
                "description": "Classify the user's intent from their message",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "intent": {
                            "type": "string",
                            "enum": [intent.value for intent in Intent],
                            "description": "The classified intent"
                        },
                        "confidence": {
                            "type": "number",
                            "description": "Confidence score from 0.0 to 1.0"
                        },
                        "reasoning": {
                            "type": "string",
                            "description": "Brief reasoning for the classification"
                        }
                    },
                    "required": ["intent", "confidence", "reasoning"]
                }
            }
        ]

        # Call LLM with function calling
        try:
            response = await self.llm.function_calling(
                messages=messages,
                functions=functions,
                function_call="auto"
            )

            # Parse function call result
            if response.get("function_call"):
                func_args = self._parse_function_args(
                    response["function_call"].get("arguments", "{}")
                )

                return IntentConfidence(
                    intent=Intent.from_string(func_args.get("intent", Intent.UNKNOWN)),
                    confidence=func_args.get("confidence", 0.5),
                    reasoning=func_args.get("reasoning")
                )
            else:
                # Fallback: if no function call was returned, try to parse from content
                return self._fallback_classification(user_message)

        except Exception as e:
            print(f"Error in RouterAgent: {e}")
            return IntentConfidence(
                intent=Intent.UNKNOWN,
                confidence=0.0,
                reasoning=f"Error during classification: {str(e)}"
            )

    def _parse_function_args(self, args_str: str) -> Dict[str, Any]:
        """Parse function arguments string to dictionary"""
        import json
        try:
            return json.loads(args_str)
        except json.JSONDecodeError:
            return {}

    def _fallback_classification(self, user_message: str) -> IntentConfidence:
        """
        Fallback classification using keyword matching

        This is used when LLM function calling fails
        """
        # Simple keyword-based classification
        message_lower = user_message.lower()

        # Simple keyword-based classification
        if any(kw in message_lower for kw in ["安排", "计划", "提醒", "创建", "添加", "schedule", "remind", "create"]):
            return IntentConfidence(
                intent=Intent.CREATE_EVENT,
                confidence=0.6,
                reasoning="Keyword matching: creation intent detected"
            )

        if any(kw in message_lower for kw in ["查询", "有什么", "安排", "查看", "query", "what", "show"]):
            return IntentConfidence(
                intent=Intent.QUERY_EVENT,
                confidence=0.6,
                reasoning="Keyword matching: query intent detected"
            )

        if any(kw in message_lower for kw in ["修改", "改", "更新", "改期", "update", "change", "move"]):
            return IntentConfidence(
                intent=Intent.UPDATE_EVENT,
                confidence=0.6,
                reasoning="Keyword matching: update intent detected"
            )

        if any(kw in message_lower for kw in ["取消", "删除", "不要", "cancel", "delete", "remove"]):
            return IntentConfidence(
                intent=Intent.DELETE_EVENT,
                confidence=0.6,
                reasoning="Keyword matching: delete intent detected"
            )

        if any(kw in message_lower for kw in ["撤销", "回退", "undo", "revert"]):
            return IntentConfidence(
                intent=Intent.UNDO_CHANGE,
                confidence=0.6,
                reasoning="Keyword matching: undo intent detected"
            )

        if any(kw in message_lower for kw in ["你好", "hi", "hello", "早上好", "下午好", "晚上好"]):
            return IntentConfidence(
                intent=Intent.GREETING,
                confidence=0.9,
                reasoning="Keyword matching: greeting detected"
            )

        if any(kw in message_lower for kw in ["谢谢", "感谢", "thanks", "thank"]):
            return IntentConfidence(
                intent=Intent.THANKS,
                confidence=0.9,
                reasoning="Keyword matching: thanks detected"
            )

        if any(kw in message_lower for kw in ["再见", "拜拜", "goodbye", "bye"]):
            return IntentConfidence(
                intent=Intent.GOODBYE,
                confidence=0.9,
                reasoning="Keyword matching: goodbye detected"
            )

        # Default to unknown
        return IntentConfidence(
            intent=Intent.UNKNOWN,
            confidence=0.3,
            reasoning="No clear intent detected"
        )

    async def route_to_agent(
        self,
        intent: Intent,
        user_message: str,
        user_id: str,
        context: Dict[str, Any] = None
    ) -> str:
        """
        Route to the appropriate agent based on intent

        Returns:
            Agent name to handle this request
        """
        intent_agent_mapping = {
            # Event operations -> ScheduleAgent
            Intent.CREATE_EVENT: "ScheduleAgent",
            Intent.QUERY_EVENT: "ScheduleAgent",
            Intent.UPDATE_EVENT: "ScheduleAgent",
            Intent.DELETE_EVENT: "ScheduleAgent",

            # Snapshot operations -> SnapshotManager
            Intent.UNDO_CHANGE: "SnapshotManager",
            Intent.RESTORE_SNAPSHOT: "SnapshotManager",

            # Energy operations -> EnergyAgent
            Intent.CHECK_ENERGY: "EnergyAgent",
            Intent.SUGGEST_SCHEDULE: "EnergyAgent",

            # Stats operations -> StatsAgent (not implemented yet)
            Intent.GET_STATS: "ScheduleAgent",  # Temporary routing

            # User operations -> ScheduleAgent (temporary)
            Intent.UPDATE_PREFERENCES: "ScheduleAgent",
            Intent.UPDATE_ENERGY_PROFILE: "EnergyAgent",

            # Conversation -> Handle directly
            Intent.GREETING: "ConversationHandler",
            Intent.THANKS: "ConversationHandler",
            Intent.GOODBYE: "ConversationHandler",
            Intent.CHITCHAT: "ConversationHandler",

            # Unknown -> Ask for clarification
            Intent.UNKNOWN: "ConversationHandler",
        }

        return intent_agent_mapping.get(intent, "ConversationHandler")


# Global RouterAgent instance
router_agent = RouterAgent()
