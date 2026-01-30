"""Add is_template column to events table for Routine template support"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import create_engine, text
from app.config import settings

def migrate():
    engine = create_engine(settings.database_url)
    with engine.connect() as conn:
        trans = conn.begin()
        try:
            conn.execute(text("ALTER TABLE events ADD COLUMN is_template BOOLEAN DEFAULT 0"))
            trans.commit()
            print("✅ Successfully added is_template column to events table")
        except Exception as e:
            if "duplicate column name" in str(e).lower():
                print("ℹ️ Column is_template already exists")
            else:
                print(f"❌ Error: {e}")
                trans.rollback()
                raise

if __name__ == "__main__":
    migrate()
