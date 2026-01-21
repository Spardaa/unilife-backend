"""
数据库迁移脚本 - 添加对话和消息表
用于持久化存储对话历史
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

def create_conversations_table(cursor):
    """创建 conversations 表"""
    if check_table_exists(cursor, "conversations"):
        print("[INFO] conversations table already exists")
        return

    print("[INFO] Creating conversations table...")
    cursor.execute("""
        CREATE TABLE conversations (
            id VARCHAR PRIMARY KEY,
            user_id VARCHAR NOT NULL,
            title VARCHAR,
            created_at DATETIME,
            updated_at DATETIME,
            message_count INTEGER DEFAULT 0,
            extra_metadata TEXT
        )
    """)

    # 创建索引
    cursor.execute(
        "CREATE INDEX idx_conversations_user_id ON conversations (user_id)"
    )
    cursor.execute(
        "CREATE INDEX idx_conversations_created_at ON conversations (created_at)"
    )
    cursor.execute(
        "CREATE INDEX idx_conversations_user_time ON conversations (user_id, created_at)"
    )

    print("[OK] conversations table created")

def create_messages_table(cursor):
    """创建 messages 表"""
    if check_table_exists(cursor, "messages"):
        print("[INFO] messages table already exists")
        return

    print("[INFO] Creating messages table...")
    cursor.execute("""
        CREATE TABLE messages (
            id VARCHAR PRIMARY KEY,
            conversation_id VARCHAR NOT NULL,
            role VARCHAR NOT NULL,
            content TEXT,
            tool_calls TEXT,
            tool_call_id VARCHAR,
            created_at DATETIME,
            tokens_used INTEGER,
            extra_metadata TEXT,
            FOREIGN KEY (conversation_id) REFERENCES conversations (id)
        )
    """)

    # 创建索引
    cursor.execute(
        "CREATE INDEX idx_messages_conversation_id ON messages (conversation_id)"
    )
    cursor.execute(
        "CREATE INDEX idx_messages_created_at ON messages (created_at)"
    )
    cursor.execute(
        "CREATE INDEX idx_messages_conversation_time ON messages (conversation_id, created_at)"
    )

    print("[OK] messages table created")

def main():
    print("=" * 60)
    print("Conversation and Message Tables Migration")
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
        create_conversations_table(cursor)
        create_messages_table(cursor)

        # 提交更改
        conn.commit()
        print()
        print("[SUCCESS] Migration completed successfully!")
        print()
        print("New tables created:")
        print("  - conversations: stores conversation sessions")
        print("  - messages: stores chat messages")
        print()
        print("Features enabled:")
        print("  - Persistent conversation history")
        print("  - Multi-conversation support")
        print("  - Intelligent context selection")
        print("  - Cross-device conversation sync")

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
