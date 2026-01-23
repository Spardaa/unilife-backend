"""
数据库迁移脚本 - 增强功能的新字段
包括精力评估、用户画像、增量快照等
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


def check_column_exists(cursor, table_name: str, column_name: str) -> bool:
    """检查列是否存在"""
    cursor.execute(f"PRAGMA table_info({table_name})")
    columns = [col[1] for col in cursor.fetchall()]
    return column_name in columns


def migrate_events_table(cursor):
    """迁移 events 表，添加新字段"""
    print("[INFO] Checking events table for new columns...")

    new_columns = [
        ("energy_consumption", "TEXT"),  # JSON string
        ("ai_description", "TEXT"),
        ("extracted_points", "TEXT")  # JSON string
    ]

    for column_name, column_type in new_columns:
        if check_column_exists(cursor, "events", column_name):
            print(f"[INFO] Column '{column_name}' already exists in events table")
        else:
            print(f"[INFO] Adding column '{column_name}' to events table...")
            try:
                cursor.execute(f"ALTER TABLE events ADD COLUMN {column_name} {column_type}")
                print(f"[OK] Column '{column_name}' added")
            except Exception as e:
                print(f"[ERROR] Failed to add column '{column_name}': {e}")


def create_database_snapshots_table(cursor):
    """创建 database_snapshots 表"""
    cursor.execute("""
        SELECT name FROM sqlite_master WHERE type='table' AND name='database_snapshots'
    """)
    if cursor.fetchone():
        print("[INFO] database_snapshots table already exists")
        return

    print("[INFO] Creating database_snapshots table...")
    cursor.execute("""
        CREATE TABLE database_snapshots (
            id VARCHAR PRIMARY KEY,
            user_id VARCHAR NOT NULL,
            trigger VARCHAR NOT NULL,
            trigger_time DATETIME,
            table_snapshots TEXT,
            is_reverted BOOLEAN DEFAULT 0,
            reverted_at DATETIME,
            created_at DATETIME,
            expires_at DATETIME
        )
    """)

    # 创建索引
    cursor.execute("CREATE INDEX idx_db_snapshots_user_id ON database_snapshots (user_id)")
    cursor.execute("CREATE INDEX idx_db_snapshots_created_at ON database_snapshots (created_at)")

    print("[OK] database_snapshots table created")


def create_user_profiles_table(cursor):
    """创建 user_profiles 表"""
    cursor.execute("""
        SELECT name FROM sqlite_master WHERE type='table' AND name='user_profiles'
    """)
    if cursor.fetchone():
        print("[INFO] user_profiles table already exists")
        return

    print("[INFO] Creating user_profiles table...")
    cursor.execute("""
        CREATE TABLE user_profiles (
            id VARCHAR PRIMARY KEY,
            user_id VARCHAR NOT NULL,
            profile_data TEXT,
            updated_at DATETIME,
            created_at DATETIME,
            UNIQUE(user_id)
        )
    """)

    # 创建索引
    cursor.execute("CREATE INDEX idx_user_profiles_user_id ON user_profiles (user_id)")

    print("[OK] user_profiles table created")


def main():
    print("=" * 60)
    print("Enhanced Features Migration")
    print("=" * 60)
    print()
    print("This migration adds:")
    print("  - Energy consumption evaluation (体力 + 精神)")
    print("  - AI-generated descriptions")
    print("  - User profile extraction (关系/身份/喜好/习惯)")
    print("  - Incremental database snapshots")
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
        # 迁移 events 表
        migrate_events_table(cursor)

        # 创建新表
        create_database_snapshots_table(cursor)
        create_user_profiles_table(cursor)

        # 提交更改
        conn.commit()
        print()
        print("[SUCCESS] Migration completed successfully!")
        print()
        print("New features enabled:")
        print("  ✅ Energy consumption evaluation")
        print("  ✅ User profile extraction")
        print("  ✅ Incremental database snapshots")
        print("  ✅ AI-generated descriptions")

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
