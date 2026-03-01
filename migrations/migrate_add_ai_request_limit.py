"""
Migration script: Add daily AI request limit fields to users table
"""
import sqlite3
import os
import sys

# Get app path
current_dir = os.path.dirname(os.path.abspath(__file__))
app_dir = os.path.dirname(current_dir)
db_path = os.path.join(app_dir, "unilife.db")

def migrate():
    print(f"Migrating database at {db_path}...")
    
    if not os.path.exists(db_path):
        print(f"Error: Database file not found at {db_path}")
        return False
        
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    try:
        # Check if columns already exist
        cursor.execute("PRAGMA table_info(users)")
        columns = [column[1] for column in cursor.fetchall()]
        
        has_changes = False
        
        if "daily_ai_request_count" not in columns:
            print("Adding daily_ai_request_count column...")
            cursor.execute("ALTER TABLE users ADD COLUMN daily_ai_request_count INTEGER DEFAULT 0")
            has_changes = True
            
        if "last_ai_request_date" not in columns:
            print("Adding last_ai_request_date column...")
            cursor.execute("ALTER TABLE users ADD COLUMN last_ai_request_date VARCHAR NULL")
            has_changes = True
            
        if has_changes:
            conn.commit()
            print("Migration successful: Added AI request limit columns to users table.")
        else:
            print("Migration skipped: Columns already exist.")
            
        return True
        
    except Exception as e:
        print(f"Migration failed: {e}")
        conn.rollback()
        return False
    finally:
        conn.close()

if __name__ == "__main__":
    success = migrate()
    sys.exit(0 if success else 1)
