"""
Migration script to add new energy-related columns to events table

Run this script to update the existing database with the new fields:
- energy_consumption (JSON)
- is_physically_demanding (Boolean, default False)
- is_mentally_demanding (Boolean, default False)
"""
import sqlite3
from pathlib import Path

# Database path
DB_PATH = "unilife.db"

def migrate():
    """Add new columns to events table"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    try:
        # Check if columns already exist
        cursor.execute("PRAGMA table_info(events)")
        existing_columns = {row[1] for row in cursor.fetchall()}

        # Columns to add
        new_columns = {
            "energy_consumption": "JSON",
            "is_physically_demanding": "BOOLEAN DEFAULT 0",
            "is_mentally_demanding": "BOOLEAN DEFAULT 0",
        }

        for column, definition in new_columns.items():
            if column not in existing_columns:
                sql = f"ALTER TABLE events ADD COLUMN {column} {definition}"
                print(f"Adding column: {column}")
                cursor.execute(sql)
            else:
                print(f"Column already exists: {column}")

        conn.commit()
        print("\nMigration completed successfully!")

        # Show updated schema
        print("\nUpdated events table schema:")
        cursor.execute("PRAGMA table_info(events)")
        for row in cursor.fetchall():
            print(f"  - {row[1]} ({row[2]})")

    except Exception as e:
        conn.rollback()
        print(f"Migration failed: {e}")
        raise
    finally:
        conn.close()

if __name__ == "__main__":
    migrate()
