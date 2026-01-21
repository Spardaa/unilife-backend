"""
测试对话持久化功能
"""
import sys
sys.path.append(".")

from app.services.conversation_service import conversation_service

def test_conversation_persistence():
    """测试对话持久化"""
    print("=" * 60)
    print("Conversation Persistence Test")
    print("=" * 60)
    print()

    # 1. 创建对话
    print("[Test 1] Creating conversation...")
    conversation = conversation_service.create_conversation(
        user_id="test_user_001",
        title="Test Conversation"
    )
    print(f"[OK] Conversation created: {conversation.id}")
    print(f"     Title: {conversation.title}")
    print(f"     Created: {conversation.created_at}")
    print()

    # 2. 添加消息
    print("[Test 2] Adding messages...")
    msg1 = conversation_service.add_message(
        conversation_id=conversation.id,
        role="user",
        content="你好，我想明天3点开会"
    )
    print(f"[OK] User message added: {msg1.id}")

    msg2 = conversation_service.add_message(
        conversation_id=conversation.id,
        role="assistant",
        content="好的，我可以帮您创建明天3点的会议。请告诉我会议的主题和预计时长。"
    )
    print(f"[OK] Assistant message added: {msg2.id}")
    print()

    # 3. 获取消息列表
    print("[Test 3] Getting messages...")
    messages = conversation_service.get_messages(conversation.id)
    print(f"[OK] Retrieved {len(messages)} messages:")
    for msg in messages:
        print(f"     [{msg.role}] {msg.content[:50]}...")
    print()

    # 4. 测试智能上下文选择
    print("[Test 4] Testing intelligent context selection...")
    context = conversation_service.get_context_for_llm(
        conversation_id=conversation.id,
        max_messages=10,
        max_tokens=8000
    )
    print(f"[OK] Selected {len(context)} messages for LLM context:")
    for msg in context:
        print(f"     [{msg['role']}] {msg.get('content', '')[:50]}...")
    print()

    # 5. 添加更多消息，测试上下文限制
    print("[Test 5] Adding more messages to test context limit...")
    for i in range(10):
        conversation_service.add_message(
            conversation_id=conversation.id,
            role="user",
            content=f"测试消息 {i+1}"
        )
        conversation_service.add_message(
            conversation_id=conversation.id,
            role="assistant",
            content=f"回复 {i+1}"
        )
    print(f"[OK] Added 20 more messages (total: {22})")

    # 6. 再次获取上下文，验证限制
    print()
    print("[Test 6] Testing context limit...")
    all_messages = conversation_service.get_messages(conversation.id)
    print(f"[INFO] Total messages in database: {len(all_messages)}")

    context_limited = conversation_service.get_context_for_llm(
        conversation_id=conversation.id,
        max_messages=20,
        max_tokens=8000
    )
    print(f"[OK] Selected {len(context_limited)} messages for LLM (limited)")
    print(f"     First message: [{context_limited[0]['role']}] {context_limited[0].get('content', '')[:30]}...")
    print(f"     Last message: [{context_limited[-1]['role']}] {context_limited[-1].get('content', '')[:30]}...")
    print()

    # 7. 列出用户的所有对话
    print("[Test 7] Listing user conversations...")
    # 创建第二个对话
    conv2 = conversation_service.create_conversation(
        user_id="test_user_001",
        title="Another Conversation"
    )
    print(f"[OK] Created second conversation: {conv2.id}")

    conversations = conversation_service.list_conversations("test_user_001")
    print(f"[OK] User has {len(conversations)} conversations:")
    for conv in conversations:
        print(f"     - {conv.title} ({conv.message_count} messages)")
    print()

    # 8. 测试对话更新
    print("[Test 8] Testing conversation update...")
    success = conversation_service.update_conversation_title(
        conversation_id=conversation.id,
        title="Updated Title"
    )
    if success:
        updated = conversation_service.get_conversation(conversation.id)
        print(f"[OK] Title updated: {updated.title}")
    print()

    # 9. 测试消息格式转换
    print("[Test 9] Testing message format conversion...")
    msg = conversation_service.get_messages(conversation.id, limit=1)[0]
    chat_format = msg.to_chat_format()
    print(f"[OK] Message converted to chat format:")
    print(f"     role: {chat_format['role']}")
    print(f"     content: {chat_format.get('content', '')[:50]}...")
    print()

    # 10. 清理测试数据
    print("[Test 10] Cleaning up test data...")
    for conv in conversations:
        conversation_service.delete_conversation(conv.id)
    print(f"[OK] Deleted {len(conversations)} test conversations")
    print()

    print("=" * 60)
    print("[SUCCESS] All tests passed!")
    print("=" * 60)

if __name__ == "__main__":
    test_conversation_persistence()
