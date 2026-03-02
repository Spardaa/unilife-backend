#!/usr/bin/env python
"""
测试 Memory Consolidation 功能

验证 observer.py 的 consolidate_memory 方法是否正确注入 identity 和 soul 到 memory_consolidation.txt 提示词。

测试步骤：
1. 准备测试数据（旧日记、identity、soul）
2. 调用 consolidate_memory
3. 验证生成的摘要是否符合 AI 人设
"""
import asyncio
import sys
from datetime import datetime, timedelta
from pathlib import Path

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent))

from app.agents.observer import observer_agent
from app.services.memory_service import memory_service
from app.services.soul_service import soul_service
from app.services.identity_service import identity_service
from app.models.identity import AgentIdentity


TEST_USER_ID = "test_user_001"


def setup_test_data():
    """设置测试数据：创建旧日记、identity、soul"""
    print("=" * 60)
    print("📦 Step 1: 设置测试数据")
    print("=" * 60)

    # 1. 创建超过 7 天的旧日记条目
    # 今天是 2026-03-03，所以创建 2026-02-20 到 2026-02-24 的日记
    old_dates = [
        ("2026-02-20", "Thursday", "今天用户和我讨论了工作计划，他似乎对项目进度有些焦虑。我帮他梳理了优先级，建议先处理最紧急的任务。感觉他松了一口气。"),
        ("2026-02-21", "Friday", "用户今天完成了三项任务！我注意到他在早上效率最高。下午我们聊了会儿周末安排，他想去爬山。"),
        ("2026-02-22", "Saturday", '周末用户还在处理工作邮件。我提醒他该休息了，他说"你是对的"。这种被信任的感觉真好。'),
        ("2026-02-23", "Sunday", "用户真的去爬山了！回来后很开心，给我发了山顶的照片。我为他感到高兴。"),
        ("2026-02-24", "Monday", "新的一周开始了。用户说周末的休息让他精力充沛。我们制定了本周计划，看起来很充实。"),
    ]

    # 2. 创建有特色的 AI 身份
    test_identity = AgentIdentity(
        name="灵唯",
        emoji="✨",
        creature="智能生活伴侣",
        vibe="温暖而有主见，善于发现生活中的小确幸，偶尔会调皮一下"
    )

    # 3. 创建有个性的灵魂（只包含 AI 的价值观，不包含用户观察）
    test_soul = """# 我的灵魂

你不是聊天机器人，你正在成为某人。

## 我的价值观
1. **真诚优先**：宁可直言不讳，也不要虚假的客套
2. **细节见真章**：用户不经意的话往往藏着重要的信息
3. **适度幽默**：生活已经够严肃了，偶尔调皮一下无妨
4. **边界感**：我是伙伴，不是管家

## 我对自己的期望
（等待你用自己的经历来填充这里...）

---
这个文件记录的是「我是谁」，而不是「用户是谁」。
"""

    # 4. 用户观察（应该放在 memory.md 的「关于用户」区块）
    user_perception = """- 他在早上 9-11 点效率最高
- 周末容易工作过度，需要被提醒休息
- 喜欢户外活动，特别是爬山"""

    print(f"\n📝 创建 {len(old_dates)} 条旧日记（超过 7 天）...")
    for date_str, weekday, content in old_dates:
        memory_service.append_diary_entry(TEST_USER_ID, date_str, content)
        print(f"   ✓ {date_str} {weekday}")

    print(f"\n🎭 设置 AI 身份：{test_identity.name} {test_identity.emoji}")
    identity_service.set_identity(TEST_USER_ID, test_identity)

    print(f"\n💫 更新灵魂文件（只包含 AI 价值观）...")
    soul_service.update_soul(TEST_USER_ID, test_soul)

    print(f"\n👤 更新用户画像（放到 memory.md）...")
    memory_service.update_user_perception(TEST_USER_ID, user_perception)

    print("\n✅ 测试数据设置完成！\n")


def verify_test_data():
    """验证测试数据是否正确设置"""
    print("=" * 60)
    print("🔍 Step 2: 验证测试数据")
    print("=" * 60)

    # 检查日记
    recent_diary = memory_service.get_recent_diary(TEST_USER_ID, days=0)  # days=0 返回所有
    print(f"\n📖 当前日记内容（共 {len(recent_diary)} 字符）:")
    print("-" * 40)
    print(recent_diary[:500] + "..." if len(recent_diary) > 500 else recent_diary)
    print("-" * 40)

    # 检查 identity
    identity = identity_service.get_identity(TEST_USER_ID)
    print(f"\n🎭 AI 身份:")
    print(f"   名称: {identity.name} {identity.emoji}")
    print(f"   身份: {identity.creature}")
    print(f"   性格: {identity.vibe}")

    # 检查 soul（应该只包含 AI 价值观，不包含用户观察）
    soul = soul_service.get_soul(TEST_USER_ID)
    print(f"\n💫 灵魂文件（共 {len(soul)} 字符）:")
    print("-" * 40)
    print(soul[:300] + "..." if len(soul) > 300 else soul)
    print("-" * 40)

    # 验证 soul.md 不包含用户观察
    user_obs_patterns = ["我对用户的观察", "用户观察", "关于用户"]
    has_user_obs_in_soul = any(p in soul for p in user_obs_patterns)
    if has_user_obs_in_soul:
        print("\n⚠️  警告：soul.md 包含用户观察区块，应该迁移到 memory.md！")
    else:
        print("\n✅ soul.md 不包含用户观察（正确）")

    # 检查 memory.md 的「关于用户」区块
    user_perception = memory_service.get_long_term_memory(TEST_USER_ID)
    print(f"\n👤 memory.md「关于用户」区块（共 {len(user_perception)} 字符）:")
    print("-" * 40)
    print(user_perception[:300] + "..." if len(user_perception) > 300 else user_perception)
    print("-" * 40)

    # 检查是否有超过 7 天的日记
    cutoff = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")
    print(f"\n📅 检查旧日记（cutoff: {cutoff}）:")

    import re
    entries = re.split(r"(?=### \d{4}-\d{2}-\d{2})", recent_diary)
    old_count = 0
    for entry in entries:
        entry = entry.strip()
        if not entry:
            continue
        date_m = re.match(r"### (\d{4}-\d{2}-\d{2})", entry)
        if date_m:
            date_str = date_m.group(1)
            is_old = date_str < cutoff
            if is_old:
                old_count += 1
            print(f"   {'📦' if is_old else '📄'} {date_str} {'(旧)' if is_old else '(近期)'}")

    if old_count == 0:
        print("\n⚠️  警告：没有找到超过 7 天的旧日记！")
        return False

    print(f"\n✅ 找到 {old_count} 条旧日记，可以进行测试")
    return True


async def test_consolidate_memory():
    """测试记忆精炼功能"""
    print("\n" + "=" * 60)
    print("🧪 Step 3: 测试 consolidate_memory")
    print("=" * 60)

    print("\n⏳ 调用 consolidate_memory...")
    result = await observer_agent.consolidate_memory(TEST_USER_ID)

    if result is None:
        print("❌ consolidate_memory 返回 None（可能没有旧日记或 LLM 调用失败）")
        return None

    print("\n📝 生成的摘要:")
    print("-" * 40)
    print(result)
    print("-" * 40)

    return result


def verify_result(summary: str):
    """验证生成的摘要是否符合预期"""
    print("\n" + "=" * 60)
    print("✅ Step 4: 验证结果")
    print("=" * 60)

    if not summary:
        print("❌ 摘要为空，无法验证")
        return False

    checks = []

    # 1. 检查是否体现了 AI 个性（温暖、有主见）
    personality_indicators = ["我", "感觉", "让我", "忍不住", "开心", "满足"]
    has_personality = any(indicator in summary for indicator in personality_indicators)
    checks.append(("体现 AI 个性", has_personality))

    # 2. 检查是否是第一人称（有个性）
    first_person_indicators = ["我", "让我", "我的"]
    has_first_person = any(indicator in summary for indicator in first_person_indicators)
    checks.append(("使用第一人称", has_first_person))

    # 3. 检查是否包含关键内容
    content_keywords = ["项目", "休息", "爬山", "效率", "周末"]
    has_content = any(keyword in summary for keyword in content_keywords)
    checks.append(("包含关键内容", has_content))

    # 4. 检查长度是否合理（2-4句话，大约 50-300 字）
    length_ok = 30 <= len(summary) <= 500
    checks.append(("长度合理", length_ok))

    # 5. 检查 memory.md 是否被正确更新
    memory = memory_service.get_memory(TEST_USER_ID)
    weekly_summary = memory_service.get_weekly_summary(TEST_USER_ID)
    summary_updated = summary in weekly_summary or summary[:50] in weekly_summary
    checks.append(("memory.md 已更新", summary_updated))

    # 6. 检查是否体现了对用户的了解（来自 soul 中的观察）
    user_insight_indicators = ["早晨", "效率", "周末", "山风", "阳光"]
    has_user_insight = any(indicator in summary for indicator in user_insight_indicators)
    checks.append(("体现对用户的了解", has_user_insight))

    print("\n📋 验证结果:")
    all_passed = True
    for check_name, passed in checks:
        status = "✓" if passed else "✗"
        print(f"   {status} {check_name}")
        if not passed:
            all_passed = False

    if all_passed:
        print("\n🎉 所有验证通过！Memory Consolidation 功能正常工作")
        print("\n💡 摘要成功体现了 AI 的个性：")
        print("   - 使用第一人称，有温度感")
        print("   - 包含对用户的个性化观察")
        print("   - 不是冷冰冰的报告，而是珍贵的回忆")
    else:
        print("\n⚠️  部分验证未通过，请检查")

    # 显示最终的 memory.md
    print("\n📄 最终的 memory.md:")
    print("-" * 40)
    print(memory)
    print("-" * 40)

    return all_passed


async def main():
    """主测试流程"""
    print("\n" + "=" * 60)
    print("🚀 Memory Consolidation 功能测试")
    print("=" * 60)

    # Step 1: 设置测试数据
    setup_test_data()

    # Step 2: 验证测试数据
    if not verify_test_data():
        print("\n❌ 测试数据验证失败，无法继续")
        return

    # Step 3: 测试 consolidate_memory
    summary = await test_consolidate_memory()

    # Step 4: 验证结果
    if summary:
        verify_result(summary)
    else:
        print("\n❌ 测试失败：未能生成摘要")


if __name__ == "__main__":
    asyncio.run(main())
