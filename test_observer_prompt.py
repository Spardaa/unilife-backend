import asyncio
from app.services.soul_service import soul_service
from app.agents.observer import observer_agent
from app.agents.base import ConversationContext

uid = "53aede26-5b5a-49cd-82f4-cc6e587506bc"
soul_service.update_soul(uid, "你是一个性格有些傲娇但依然关心用户的AI。")

print("Building Analysis Prompt...")
ctx = ConversationContext(user_id=uid, conversation_id="test", user_message="测试", conversation_history=[])
prompt = observer_agent._build_analysis_prompt(ctx)

print("----- GENERATED PROMPT START -----")
print(prompt)
print("----- GENERATED PROMPT END -----")
