"""
数据库迁移脚本 - 添加 Dual Time Architecture 相关字段
用于在现有数据库中添加新字段，而不是删除重建
"""
import sqlite3
import os
import shutil

# 数据库路径
DB_PATH = os.environ.get("SQLITE_PATH", "unilife.db")


def migrate_database():
    """执行数据库迁移，添加 Dual Time Architecture 字段"""

    if not os.path.exists(DB_PATH):
        print(f"[ERROR] 数据库文件 {DB_PATH} 不存在")
        return False

    print(f"[INFO] 开始迁移数据库: {DB_PATH}")

    # 备份数据库
    backup_path = f"{DB_PATH}.backup_dual_time"
    shutil.copy2(DB_PATH, backup_path)
    print(f"[OK] 已创建备份: {backup_path}")

    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        # 检查表结构
        cursor.execute("PRAGMA table_info(events)")
        columns = [row[1] for row in cursor.fetchall()]
        print(f"[INFO] 当前字段: {columns}")

        # 要添加的新字段（Dual Time Architecture）
        new_columns = [
            # Duration source tracking
            ("duration_source", "TEXT DEFAULT 'default'"),
            ("duration_confidence", "REAL DEFAULT 1.0"),
            ("duration_actual", "INTEGER"),
            ("ai_original_estimate", "INTEGER"),

            # Display preference
            ("display_mode", "TEXT DEFAULT 'flexible'"),

            # Enhanced features
            ("energy_consumption", "JSON"),
            ("ai_description", "TEXT"),
            ("extracted_points", "JSON"),
        ]

        # 添加新字段（如果不存在）
        for column_name, column_type in new_columns:
            if column_name not in columns:
                try:
                    sql = f"ALTER TABLE events ADD COLUMN {column_name} {column_type}"
                    cursor.execute(sql)
                    print(f"[OK] 已添加字段: {column_name}")
                except Exception as e:
                    print(f"[WARN] 添加字段 {column_name} 失败: {e}")
            else:
                print(f"[INFO] 字段已存在: {column_name}")

        conn.commit()
        conn.close()

        print(f"\n[SUCCESS] 数据库迁移完成！")
        print(f"[INFO] 备份文件: {backup_path}")
        print(f"\n如果出现问题，可以恢复备份：")
        print(f"  del {DB_PATH}")
        print(f"  rename {backup_path} {DB_PATH}")

        return True

    except Exception as e:
        print(f"[ERROR] 迁移失败: {e}")
        print(f"\n恢复备份...")
        if os.path.exists(backup_path):
            shutil.copy2(backup_path, DB_PATH)
            print(f"[OK] 已恢复备份")
        return False


if __name__ == "__main__":
    print("=" * 60)
    print("UniLife Dual Time Architecture Migration")
    print("=" * 60)
    print()

    success = migrate_database()

    if success:
        print("\n" + "=" * 60)
        print("迁移完成！现在可以重启服务器了。")
        print("=" * 60)
    else:
        print("\n" + "=" * 60)
        print("迁移失败，请检查上面的错误信息。")
        print("=" * 60)
