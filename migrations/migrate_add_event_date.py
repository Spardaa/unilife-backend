"""
Migration: Add event_date column to events table

The event_date column stores the date an event belongs to, independent of start_time.
- For floating events: event_date is set by user
- For scheduled events: event_date can be derived from start_time, but can also be set separately
"""
import sqlite3
from datetime import datetime
from pathlib import Path

def migrate():
    db_path = Path(__file__).parent.parent / "unilife.db"
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    try:
        # Add event_date column if it doesn't exist
        cursor.execute("ALTER TABLE events ADD COLUMN event_date DATETIME")
        print("✅ Added event_date column to events table")
        
        # For existing events without start_time, set event_date to created_at
        cursor.execute("""
            UPDATE events 
            SET event_date = created_at 
            WHERE event_date IS NULL AND start_time IS NULL
        """)
        
        # For existing events with start_time, derive event_date from start_time
        cursor.execute("""
            UPDATE events 
            SET event_date = DATE(start_time)
            WHERE event_date IS NULL AND start_time IS NOT NULL
        """)
        
        conn.commit()
        print("✅ Migrated existing events: event_date set for all records")
        
    except sqlite3.OperationalError as e:
        if "duplicate column name" in str(e):
            print("⚠️ Column event_date already exists, skipping migration")
        else:
            print(f"❌ Migration error: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    migrate()
