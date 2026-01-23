"""
将现有的单一 status 迁移为列表格式

运行方式：
    python migrate_relationship_status.py
"""
import sqlite3
import json
import os

DB_PATH = "unilife.db"


def migrate():
    if not os.path.exists(DB_PATH):
        print(f"Database file not found: {DB_PATH}")
        return

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # 检查表是否存在
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='user_profiles'")
    if not cursor.fetchone():
        print("Table 'user_profiles' does not exist. Migration skipped.")
        conn.close()
        return

    cursor.execute("SELECT id, user_id, profile_data FROM user_profiles")
    rows = cursor.fetchall()

    if not rows:
        print("No profiles found in database.")
        conn.close()
        return

    updated_count = 0

    for row in rows:
        id_, user_id, profile_data = row
        try:
            profile = json.loads(profile_data)

            # 迁移 relationships.status
            relationships = profile.get("relationships", {})
            status = relationships.get("status", "unknown")

            if isinstance(status, str) and status != "unknown":
                # 转换为列表
                relationships["status"] = [status]
                updated_count += 1
            elif not isinstance(status, list):
                # 确保是列表格式
                relationships["status"] = []

            # 移除 evidence_count 和 recent_evidence
            relationships.pop("evidence_count", None)
            relationships.pop("recent_evidence", None)

            profile["relationships"] = relationships

            # 更新数据库
            cursor.execute(
                "UPDATE user_profiles SET profile_data = ? WHERE id = ?",
                (json.dumps(profile, ensure_ascii=False), id_)
            )

        except json.JSONDecodeError as e:
            print(f"Error parsing profile for user {user_id}: {e}")
        except Exception as e:
            print(f"Error migrating profile for user {user_id}: {e}")

    conn.commit()
    conn.close()

    print(f"Migration completed! Updated {updated_count} profiles.")


if __name__ == "__main__":
    migrate()
