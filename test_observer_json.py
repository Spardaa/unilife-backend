import asyncio
from app.agents.observer import observer_agent
from app.agents.base import ConversationContext

uid = "53aede26-5b5a-49cd-82f4-cc6e587506bc"

print("\n--- Testing Prompt Generation ---")
ctx = ConversationContext(user_id=uid, conversation_id="test", user_message="测试", conversation_history=[])
prompt = observer_agent._build_analysis_prompt(ctx)
print(prompt[:500] + "\n...\n" + prompt[-200:])

print("\n--- Testing JSON Parsing (without pattern_notes) ---")
mock_response = """
```json
{
  "has_updates": true,
  "user_perception": "我发现她喜欢简化流程，倾向于自由设定目标。"
}
```
"""
result = observer_agent._parse_response(mock_response)
print("Parse Result:", result)

