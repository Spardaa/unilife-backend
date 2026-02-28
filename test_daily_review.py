import asyncio
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from datetime import date
from app.agents.observer import observer_agent

async def main():
    user_id = "53aede26-5b5a-49cd-82f4-cc6e587506bc"
    today = date.today().strftime("%Y-%m-%d")
    
    print("Testing diary review logic with mocking...")
    print(f"User: {user_id} on {today}")
    
    # Mock the db calls in daily_review directly
    from app.services.conversation_service import conversation_service
    import app.services.db 
    
    async def mock_get_recent_context(*args, **kwargs):
        return [
            {"role": "user", "content": "今天下班有点晚，赶不上去健身房了。"},
            {"role": "assistant", "content": "辛苦啦！既然太晚了，今晚就在家好好休息吧。需要我帮你把健身计划推迟到明天吗？"},
            {"role": "user", "content": "好吧，推到明天下午吧。然后帮我放点助眠的音乐，我准备睡觉了。"},
            {"role": "assistant", "content": "没问题，已经把健身推到明天下午了。助眠白噪音已经为你准备好，晚安，做个好梦~"}
        ]
        
    async def mock_get_events(*args, **kwargs):
        return [{"title": "健身", "status": "postponed"}]
        
    # Apply monkey patches
    conversation_service.get_recent_context = mock_get_recent_context
    app.services.db.db_service.get_events = mock_get_events
    
    result = await observer_agent.daily_review(user_id, today)
    
    print("\n--- Review JSON Result ---")
    import json
    print(json.dumps(result, indent=2, ensure_ascii=False) if result else "None")

    print("\n--- Current Memory ---")
    memory_path = f"data/users/{user_id}/memory.md"
    if os.path.exists(memory_path):
        with open(memory_path, "r", encoding="utf-8") as f:
            print(f.read())

if __name__ == "__main__":
    asyncio.run(main())
