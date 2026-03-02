#!/usr/bin/env python
"""
迁移脚本：将 soul.md 中的用户观察迁移到 memory.md

背景：
- 早期版本的 observer.txt 可能把用户观察写入了 soul.md
- 正确的边界应该是：
  - soul.md: AI 的价值观、性格、自我认知（「我是谁」）
  - memory.md: 用户画像、日记、周报（「用户是谁」）

本脚本会：
1. 扫描所有用户的 soul.md
2. 检查是否包含用户观察相关区块（如「我对用户的观察」）
3. 如果有，提取内容并迁移到 memory.md 的「关于用户」区块
4. 从 soul.md 中移除该区块

使用方法：
    python migrations/migrate_soul_to_memory.py [--dry-run]

    --dry-run: 只显示将要迁移的内容，不实际修改文件
"""
import argparse
import re
import sys
from pathlib import Path
from datetime import datetime

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.services.soul_service import soul_service
from app.services.memory_service import memory_service
from app.services.user_data_service import user_data_service


# 要从 soul.md 迁移到 memory.md 的区块标题模式
USER_OBSERVATION_PATTERNS = [
    r"## 我对用户的观察",
    r"## 用户观察",
    r"## 对用户的了解",
    r"## 关于用户",
    r"## UniLife 眼中的用户",
]


def find_user_observation_block(soul_content: str) -> tuple[str, str] | None:
    """
    在 soul.md 中查找用户观察区块。

    Returns:
        (block_header, block_content) 或 None
    """
    for pattern in USER_OBSERVATION_PATTERNS:
        # 匹配区块标题和内容（直到下一个 ##、--- 或特定的结束标记）
        match = re.search(
            rf"({pattern}[^\n]*\n)(.*?)(?=\n## |\n---|\n这个文件是我的|\Z)",
            soul_content,
            re.DOTALL
        )
        if match:
            header = match.group(1).strip()
            content = match.group(2).strip()
            # 过滤掉不应该被迁移的内容（soul 文件的结尾标记）
            content = re.sub(r"\n*这个文件是我的，由我来进化。.*$", "", content, flags=re.DOTALL)
            if content and not content.startswith("_（"):  # 忽略空占位符
                return header, content
    return None


def migrate_user(user_id: str, dry_run: bool = False) -> bool:
    """
    迁移单个用户的用户观察区块。

    Returns:
        是否进行了迁移
    """
    # 读取 soul.md
    soul_content = soul_service.get_soul(user_id)

    # 查找用户观察区块
    observation = find_user_observation_block(soul_content)
    if not observation:
        print(f"  ℹ️  无需迁移：未找到用户观察区块")
        return False

    header, content = observation
    print(f"  📦 发现用户观察区块：{header}")
    print(f"     内容预览：{content[:100]}{'...' if len(content) > 100 else ''}")

    if dry_run:
        print(f"  🔍 [DRY-RUN] 将迁移到 memory.md 的「关于用户」区块")
        return True

    # 迁移到 memory.md
    today = datetime.now().strftime("%Y-%m-%d")
    memory_service.update_user_perception(user_id, content)
    print(f"  ✅ 已迁移到 memory.md")

    # 从 soul.md 中移除该区块
    # 匹配整个区块（包括标题和内容）
    new_soul = soul_content
    for pattern in USER_OBSERVATION_PATTERNS:
        new_soul = re.sub(
            rf"\n*{pattern}[^\n]*\n.*?(?=\n## |\n---|\Z)",
            "",
            new_soul,
            flags=re.DOTALL
        )

    # 清理多余的空行
    new_soul = re.sub(r"\n{3,}", "\n\n", new_soul).strip()

    if new_soul != soul_content:
        soul_service.update_soul(user_id, new_soul)
        print(f"  ✅ 已从 soul.md 中移除用户观察区块")
    else:
        print(f"  ⚠️  soul.md 内容未变化（可能是格式问题）")

    return True


def main():
    parser = argparse.ArgumentParser(description="迁移 soul.md 中的用户观察到 memory.md")
    parser.add_argument("--dry-run", action="store_true", help="只显示将要迁移的内容，不实际修改")
    args = parser.parse_args()

    print("=" * 60)
    print("📦 soul.md → memory.md 迁移脚本")
    print("=" * 60)

    if args.dry_run:
        print("\n🔍 DRY-RUN 模式：只显示将要迁移的内容\n")

    # 获取所有用户
    data_dir = Path("data/users")
    if not data_dir.exists():
        print("❌ 未找到 data/users 目录")
        return

    user_dirs = [d for d in data_dir.iterdir() if d.is_dir()]
    if not user_dirs:
        print("❌ 未找到任何用户目录")
        return

    print(f"📂 找到 {len(user_dirs)} 个用户目录\n")

    migrated_count = 0
    for user_dir in user_dirs:
        user_id = user_dir.name
        print(f"👤 处理用户：{user_id}")

        try:
            if migrate_user(user_id, dry_run=args.dry_run):
                migrated_count += 1
        except Exception as e:
            print(f"  ❌ 迁移失败：{e}")

        print()

    print("=" * 60)
    if args.dry_run:
        print(f"🔍 DRY-RUN 完成：{migrated_count} 个用户需要迁移")
    else:
        print(f"✅ 迁移完成：{migrated_count} 个用户已迁移")
    print("=" * 60)


if __name__ == "__main__":
    main()
