"""
Migration: Add Projects Table and Event Fields

This migration:
1. Creates the 'projects' table for Life Projects
2. Adds 'project_id', 'anchor_time', 'energy_cost' columns to 'events' table

Run in order after previous migrations.
"""
import os
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from sqlalchemy import create_engine, text, inspect
from app.config import settings


def run_migration():
    """Execute the migration"""
    # Get database URL
    if settings.db_type == "sqlite":
        db_url = f"sqlite:///{settings.sqlite_path}"
    else:
        db_url = settings.database_url
    
    engine = create_engine(db_url)
    inspector = inspect(engine)
    
    with engine.connect() as conn:
        # ============ Create projects table ============
        existing_tables = inspector.get_table_names()
        
        if "projects" not in existing_tables:
            print("Creating 'projects' table...")
            conn.execute(text("""
                CREATE TABLE projects (
                    id VARCHAR(36) PRIMARY KEY,
                    user_id VARCHAR(255) NOT NULL,
                    title VARCHAR(255) NOT NULL,
                    description TEXT,
                    type VARCHAR(20) DEFAULT 'FINITE',
                    base_tier INTEGER DEFAULT 1,
                    current_mode VARCHAR(20) DEFAULT 'NORMAL',
                    energy_type VARCHAR(20) DEFAULT 'BALANCED',
                    target_kpi JSON,
                    is_active BOOLEAN DEFAULT 1,
                    total_tasks INTEGER DEFAULT 0,
                    completed_tasks INTEGER DEFAULT 0,
                    total_focus_minutes INTEGER DEFAULT 0,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """))
            
            # Create index on user_id
            conn.execute(text("""
                CREATE INDEX idx_projects_user_id ON projects(user_id)
            """))
            
            # Create index on is_active for filtering
            conn.execute(text("""
                CREATE INDEX idx_projects_active ON projects(user_id, is_active)
            """))
            
            print("✅ Created 'projects' table with indexes")
        else:
            print("⏭️ 'projects' table already exists, skipping...")
        
        # ============ Add columns to events table ============
        existing_columns = [col['name'] for col in inspector.get_columns('events')]
        
        # Add project_id column
        if 'project_id' not in existing_columns:
            print("Adding 'project_id' column to events...")
            conn.execute(text("""
                ALTER TABLE events ADD COLUMN project_id VARCHAR(36)
            """))
            # Create index for project_id lookups
            conn.execute(text("""
                CREATE INDEX idx_events_project_id ON events(project_id)
            """))
            print("✅ Added 'project_id' column with index")
        else:
            print("⏭️ 'project_id' column already exists")
        
        # Add anchor_time column
        if 'anchor_time' not in existing_columns:
            print("Adding 'anchor_time' column to events...")
            conn.execute(text("""
                ALTER TABLE events ADD COLUMN anchor_time DATETIME
            """))
            print("✅ Added 'anchor_time' column")
        else:
            print("⏭️ 'anchor_time' column already exists")
        
        # Add energy_cost column
        if 'energy_cost' not in existing_columns:
            print("Adding 'energy_cost' column to events...")
            conn.execute(text("""
                ALTER TABLE events ADD COLUMN energy_cost VARCHAR(10) DEFAULT 'NORMAL'
            """))
            print("✅ Added 'energy_cost' column")
        else:
            print("⏭️ 'energy_cost' column already exists")
        
        conn.commit()
        print("\n🎉 Migration completed successfully!")


def rollback_migration():
    """Rollback the migration (for development only)"""
    if settings.db_type == "sqlite":
        db_url = f"sqlite:///{settings.sqlite_path}"
    else:
        db_url = settings.database_url
    
    engine = create_engine(db_url)
    
    with engine.connect() as conn:
        print("⚠️ Rolling back migration...")
        
        # SQLite doesn't support DROP COLUMN easily
        # For production, would need to recreate tables
        
        # Drop projects table
        conn.execute(text("DROP TABLE IF EXISTS projects"))
        print("Dropped 'projects' table")
        
        conn.commit()
        print("Rollback completed")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Add Projects table migration")
    parser.add_argument("--rollback", action="store_true", help="Rollback the migration")
    args = parser.parse_args()
    
    if args.rollback:
        rollback_migration()
    else:
        run_migration()
