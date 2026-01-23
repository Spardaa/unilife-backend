"""
数据库迁移脚本 - 添加 Routine 三层数据模型表
"""
import sqlite3
import os
from datetime import datetime

# 数据库路径
DB_PATH = "unilife.db"
BACKUP_PATH = "unilife.db.backup"

def backup_database():
    """备份数据库"""
    if not os.path.exists(BACKUP_PATH):
        import shutil
        shutil.copy2(DB_PATH, BACKUP_PATH)
        print(f"[OK] Database backed up to {BACKUP_PATH}")
    else:
        print(f"[INFO] Backup already exists at {BACKUP_PATH}")

def check_table_exists(cursor, table_name):
    """检查表是否存在"""
    cursor.execute(
        f"SELECT name FROM sqlite_master WHERE type='table' AND name='{table_name}'"
    )
    return cursor.fetchone() is not None

def create_routine_templates_table(cursor):
    """创建 routine_templates 表"""
    if check_table_exists(cursor, "routine_templates"):
        print("[INFO] routine_templates table already exists")
        return

    print("[INFO] Creating routine_templates table...")
    cursor.execute("""
        CREATE TABLE routine_templates (
            id VARCHAR PRIMARY KEY,
            user_id VARCHAR NOT NULL,
            name VARCHAR NOT NULL,
            description TEXT,
            category VARCHAR,
            repeat_rule JSON NOT NULL,
            sequence JSON,
            sequence_position INTEGER DEFAULT 0,
            is_flexible BOOLEAN DEFAULT 1,
            preferred_time_slots JSON,
            makeup_strategy VARCHAR,
            active BOOLEAN DEFAULT 1,
            created_at DATETIME,
            updated_at DATETIME,
            total_instances INTEGER DEFAULT 0,
            completed_instances INTEGER DEFAULT 0
        )
    """)

    # 创建索引
    cursor.execute(
        "CREATE INDEX idx_routine_templates_user_id ON routine_templates (user_id)"
    )
    cursor.execute(
        "CREATE INDEX idx_routine_templates_active ON routine_templates (active)"
    )
    cursor.execute(
        "CREATE INDEX idx_routine_templates_user_active ON routine_templates (user_id, active)"
    )

    print("[OK] routine_templates table created")

def create_routine_instances_table(cursor):
    """创建 routine_instances 表"""
    if check_table_exists(cursor, "routine_instances"):
        print("[INFO] routine_instances table already exists")
        return

    print("[INFO] Creating routine_instances table...")
    cursor.execute("""
        CREATE TABLE routine_instances (
            id VARCHAR PRIMARY KEY,
            template_id VARCHAR NOT NULL,
            scheduled_date VARCHAR NOT NULL,
            scheduled_time VARCHAR,
            sequence_item VARCHAR,
            status VARCHAR DEFAULT 'pending',
            generated_event_id VARCHAR,
            created_at DATETIME,
            updated_at DATETIME,
            FOREIGN KEY (template_id) REFERENCES routine_templates (id),
            FOREIGN KEY (generated_event_id) REFERENCES events (id)
        )
    """)

    # 创建索引
    cursor.execute(
        "CREATE INDEX idx_routine_instances_template_id ON routine_instances (template_id)"
    )
    cursor.execute(
        "CREATE INDEX idx_routine_instances_scheduled_date ON routine_instances (scheduled_date)"
    )
    cursor.execute(
        "CREATE INDEX idx_routine_instances_template_date ON routine_instances (template_id, scheduled_date)"
    )
    cursor.execute(
        "CREATE INDEX idx_routine_instances_date_status ON routine_instances (scheduled_date, status)"
    )

    print("[OK] routine_instances table created")

def create_routine_executions_table(cursor):
    """创建 routine_executions 表"""
    if check_table_exists(cursor, "routine_executions"):
        print("[INFO] routine_executions table already exists")
        return

    print("[INFO] Creating routine_executions table...")
    cursor.execute("""
        CREATE TABLE routine_executions (
            id VARCHAR PRIMARY KEY,
            instance_id VARCHAR NOT NULL,
            action VARCHAR NOT NULL,
            actual_date VARCHAR,
            actual_time VARCHAR,
            reason VARCHAR,
            notes TEXT,
            sequence_advanced BOOLEAN DEFAULT 1,
            created_at DATETIME,
            FOREIGN KEY (instance_id) REFERENCES routine_instances (id)
        )
    """)

    # 创建索引
    cursor.execute(
        "CREATE INDEX idx_routine_executions_instance_id ON routine_executions (instance_id)"
    )
    cursor.execute(
        "CREATE INDEX idx_routine_executions_created_at ON routine_executions (created_at)"
    )
    cursor.execute(
        "CREATE INDEX idx_routine_executions_instance_created ON routine_executions (instance_id, created_at)"
    )

    print("[OK] routine_executions table created")

def create_routine_memories_table(cursor):
    """创建 routine_memories 表"""
    if check_table_exists(cursor, "routine_memories"):
        print("[INFO] routine_memories table already exists")
        return

    print("[INFO] Creating routine_memories table...")
    cursor.execute("""
        CREATE TABLE routine_memories (
            id VARCHAR PRIMARY KEY,
            template_id VARCHAR NOT NULL,
            memory_type VARCHAR NOT NULL,
            pattern JSON NOT NULL,
            hit_count INTEGER DEFAULT 0,
            applied_count INTEGER DEFAULT 0,
            created_at DATETIME,
            updated_at DATETIME,
            last_triggered_at DATETIME,
            FOREIGN KEY (template_id) REFERENCES routine_templates (id)
        )
    """)

    # 创建索引
    cursor.execute(
        "CREATE INDEX idx_routine_memories_template_id ON routine_memories (template_id)"
    )
    cursor.execute(
        "CREATE INDEX idx_routine_memories_memory_type ON routine_memories (memory_type)"
    )
    cursor.execute(
        "CREATE INDEX idx_routine_memories_template_type ON routine_memories (template_id, memory_type)"
    )

    print("[OK] routine_memories table created")

def main():
    print("=" * 60)
    print("Routine Three-Layer Model Migration")
    print("=" * 60)
    print()

    # 检查数据库文件
    if not os.path.exists(DB_PATH):
        print(f"[ERROR] Database file not found: {DB_PATH}")
        return

    # 备份数据库
    backup_database()

    # 连接数据库
    print(f"[INFO] Connecting to database: {DB_PATH}")
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    try:
        # 创建表
        create_routine_templates_table(cursor)
        create_routine_instances_table(cursor)
        create_routine_executions_table(cursor)
        create_routine_memories_table(cursor)

        # 提交更改
        conn.commit()
        print()
        print("[SUCCESS] Migration completed successfully!")
        print()
        print("New tables created:")
        print("  - routine_templates: Routine 模板（规则层）")
        print("  - routine_instances: Routine 实例（实例层）")
        print("  - routine_executions: 执行记录（执行层）")
        print("  - routine_memories: 智能记忆（记忆层）")
        print()
        print("Features enabled:")
        print("  - 长期重复日程管理")
        print("  - 序列循环支持（如健身计划：胸→肩→背）")
        print("  - 实例级别的灵活调整")
        print("  - 执行历史追踪")
        print("  - 智能模式学习")

    except Exception as e:
        conn.rollback()
        print(f"[ERROR] Migration failed: {e}")
        import traceback
        traceback.print_exc()
    finally:
        conn.close()

    print()
    print("=" * 60)

if __name__ == "__main__":
    main()
