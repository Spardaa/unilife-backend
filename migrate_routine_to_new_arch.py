"""
将 events 表中的 HABIT 类型数据迁移到 routine_templates 表

这是 Phase 3 的数据迁移脚本，将旧系统数据迁移到新三层架构。

使用方法：
    python migrate_routine_to_new_arch.py

功能：
1. 读取 events 表中所有 HABIT 类型的记录
2. 检查是否已经迁移过（通过 parent_routine_id 字段）
3. 为未迁移的记录创建 routine_templates 表记录
4. 更新 events 表记录，关联到新模板
"""
import sqlite3
import json
import uuid
from datetime import datetime

DB_PATH = "unilife.db"


def get_connection():
    """获取数据库连接"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def check_table_exists(conn, table_name):
    """检查表是否存在"""
    cursor = conn.cursor()
    cursor.execute(f"""
        SELECT name FROM sqlite_master
        WHERE type='table' AND name='{table_name}'
    """)
    return cursor.fetchone() is not None


def migrate():
    """执行迁移"""
    print("=" * 60)
    print("UniLife Routine 数据迁移脚本")
    print("将 events 表的 HABIT 数据迁移到 routine_templates 表")
    print("=" * 60)
    print()

    conn = get_connection()
    cursor = conn.cursor()

    # 检查 routine_templates 表是否存在
    if not check_table_exists(conn, "routine_templates"):
        print("❌ routine_templates 表不存在，请先运行 migrate_routine.py")
        conn.close()
        return

    # 1. 读取所有 HABIT 类型的事件
    print("📖 正在读取 events 表中的 HABIT 数据...")
    cursor.execute("""
        SELECT id, user_id, title, description, repeat_rule, category,
               is_flexible, preferred_time_slots, makeup_strategy, parent_routine_id
        FROM events
        WHERE event_type = 'HABIT' AND repeat_rule IS NOT NULL
    """)
    habits = cursor.fetchall()

    if not habits:
        print("✅ 没有需要迁移的数据")
        conn.close()
        return

    print(f"📋 找到 {len(habits)} 条 HABIT 记录")
    print()

    # 统计
    migrated_count = 0
    skipped_count = 0
    error_count = 0

    for habit in habits:
        habit_dict = dict(habit)
        id_ = habit_dict["id"]
        user_id = habit_dict["user_id"]
        title = habit_dict["title"]
        description = habit_dict["description"]
        repeat_rule = habit_dict["repeat_rule"]
        category = habit_dict["category"]
        is_flexible = habit_dict["is_flexible"] if habit_dict["is_flexible"] else True
        preferred_time_slots = habit_dict["preferred_time_slots"]
        makeup_strategy = habit_dict["makeup_strategy"] or "skip"
        parent_routine_id = habit_dict["parent_routine_id"]

        # 2. 检查是否已迁移
        if parent_routine_id:
            # 验证关联的模板是否存在
            cursor.execute("""
                SELECT id FROM routine_templates WHERE id = ?
            """, (parent_routine_id,))
            if cursor.fetchone():
                print(f"⏭️  跳过已迁移: {title}")
                skipped_count += 1
                continue

        # 3. 检查是否已有同名模板
        cursor.execute("""
            SELECT id FROM routine_templates
            WHERE user_id = ? AND name = ?
        """, (user_id, title))

        existing = cursor.fetchone()
        if existing:
            template_id = existing["id"]
            print(f"🔄 找到同名模板，关联现有模板: {title}")
            # 更新 events 表，关联到现有模板
            cursor.execute("""
                UPDATE events
                SET parent_routine_id = ?
                WHERE id = ?
            """, (template_id, id_))
            migrated_count += 1
            continue

        # 4. 解析 repeat_rule（可能是字符串或字典）
        if isinstance(repeat_rule, str):
            try:
                repeat_rule = json.loads(repeat_rule)
            except:
                print(f"❌ 无法解析 repeat_rule，跳过: {title}")
                error_count += 1
                continue

        # 5. 创建 routine_templates 记录
        template_id = str(uuid.uuid4())
        now = datetime.now().isoformat()

        cursor.execute("""
            INSERT INTO routine_templates (
                id, user_id, name, description, category,
                repeat_rule, sequence, sequence_position,
                is_flexible, preferred_time_slots, makeup_strategy,
                active, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            template_id, user_id, title, description, category,
            json.dumps(repeat_rule), None, 0,
            1 if is_flexible else 0,
            json.dumps(preferred_time_slots) if preferred_time_slots else None,
            makeup_strategy,
            1, now, now
        ))

        # 6. 更新 events 表，关联到新模板
        cursor.execute("""
            UPDATE events
            SET parent_routine_id = ?
            WHERE id = ?
        """, (template_id, id_))

        print(f"✅ 已迁移: {title} -> {template_id}")
        migrated_count += 1

    # 提交更改
    conn.commit()
    conn.close()

    print()
    print("=" * 60)
    print("📊 迁移完成！统计：")
    print(f"   ✅ 成功迁移: {migrated_count} 条")
    print(f"   ⏭️  跳过已迁移: {skipped_count} 条")
    if error_count > 0:
        print(f"   ❌ 错误: {error_count} 条")
    print("=" * 60)


if __name__ == "__main__":
    migrate()
