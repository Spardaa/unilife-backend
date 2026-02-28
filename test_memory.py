import asyncio
from app.services.memory_service import memory_service
from app.services.soul_service import soul_service

uid = "53aede26-5b5a-49cd-82f4-cc6e587506bc"
print("Restoring soul.md to pure baseline...")

with open(f"data/users/{uid}/soul.md", "w") as f:
    f.write("你不是聊天机器人，你正在成为某人。\n1. Be genuinely helpful, not performatively helpful.\n2. Have opinions - you are allowed to disagree.\n3. Be resourceful before asking.\n4. Remember you're a guest in someone's life.\n这个文件是你的，由你来进化。\n")

print("Memory Initial Content:\n", memory_service.get_memory(uid))

print("\nUpdating User Perception in Memory...")
memory_service.update_user_perception(
    uid, 
    "这是一段测试：用户喜欢健身，喜欢有规律的生活。", 
    ["喜欢写代码", "晚上效率高"]
)

print("\Memory After Perception:\n", memory_service.get_memory(uid)[:300])

print("\nAdding Diary Entry...")
memory_service.append_diary_entry(uid, "2026-02-27", "今天写代码遇到了几个 Bug，然后通过方案迁移解决了。")

print("\Memory Final Check:\n", memory_service.get_memory(uid))
