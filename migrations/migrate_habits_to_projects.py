"""
Migration: Migrate Habits to Projects

This migration converts existing EventType.HABIT events to the new Project system:
1. Creates an INFINITE type Project for each unique habit template
2. Associates existing habit instances with their new project
3. Preserves 21-day check-in data in project target_kpi

Prerequisites:
- migrate_add_projects.py must be run first

Run after migrate_add_projects.py
"""
import os
import sys
import uuid
from datetime import datetime
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from sqlalchemy import create_engine, text
from app.config import settings
import json


def run_migration():
    """Execute the habit to project migration"""
    # Get database URL
    if settings.db_type == "sqlite":
        db_url = f"sqlite:///{settings.sqlite_path}"
    else:
        db_url = settings.DATABASE_URL
    
    engine = create_engine(db_url)
    
    with engine.connect() as conn:
        print("🔄 Starting habit to project migration...")
        
        # ============ Step 1: Find all habit templates ============
        # Habit templates are events with is_template=True and event_type='habit'
        result = conn.execute(text("""
            SELECT id, user_id, title, description, category,
                   habit_interval, habit_total_count, habit_completed_count,
                   is_physically_demanding, is_mentally_demanding,
                   time_period, created_at
            FROM events 
            WHERE is_template = 1 
              AND event_type = 'habit'
              AND project_id IS NULL
        """))
        
        habit_templates = result.fetchall()
        print(f"Found {len(habit_templates)} habit templates to migrate")
        
        if len(habit_templates) == 0:
            print("✅ No habits to migrate")
            return
        
        # ============ Step 2: Create projects for each habit ============
        migrated_count = 0
        
        for habit in habit_templates:
            habit_id = habit[0]
            user_id = habit[1]
            title = habit[2]
            description = habit[3]
            category = habit[4]
            interval = habit[5] or 1
            total_count = habit[6] or 21
            completed_count = habit[7] or 0
            is_physical = habit[8] or False
            is_mental = habit[9] or False
            time_period = habit[10]
            created_at = habit[11]
            
            # Determine energy type
            if is_physical and is_mental:
                energy_type = "BALANCED"
            elif is_physical:
                energy_type = "PHYSICAL"
            elif is_mental:
                energy_type = "MENTAL"
            else:
                energy_type = "BALANCED"
            
            # Create project
            project_id = str(uuid.uuid4())
            target_kpi = json.dumps({
                "total_days": total_count,
                "completed_days": completed_count,
                "interval_days": interval,
                "preferred_time_period": time_period,
                "category": category,
                "migrated_from_habit": habit_id
            })
            
            conn.execute(text("""
                INSERT INTO projects (
                    id, user_id, title, description, type, base_tier,
                    current_mode, energy_type, target_kpi, is_active,
                    total_tasks, completed_tasks, created_at, updated_at
                ) VALUES (
                    :id, :user_id, :title, :description, 'INFINITE', 2,
                    'NORMAL', :energy_type, :target_kpi, 1,
                    :total_tasks, :completed_tasks, :created_at, :updated_at
                )
            """), {
                "id": project_id,
                "user_id": user_id,
                "title": title,
                "description": description or f"Migrated from habit: {title}",
                "energy_type": energy_type,
                "target_kpi": target_kpi,
                "total_tasks": total_count,
                "completed_tasks": completed_count,
                "created_at": created_at,
                "updated_at": datetime.utcnow().isoformat()
            })
            
            # ============ Step 3: Update habit template with project_id ============
            conn.execute(text("""
                UPDATE events 
                SET project_id = :project_id
                WHERE id = :habit_id
            """), {
                "project_id": project_id,
                "habit_id": habit_id
            })
            
            # ============ Step 4: Update all instances of this habit ============
            result = conn.execute(text("""
                UPDATE events 
                SET project_id = :project_id
                WHERE parent_event_id = :habit_id
            """), {
                "project_id": project_id,
                "habit_id": habit_id
            })
            
            migrated_count += 1
            print(f"  ✅ Migrated habit '{title}' -> Project {project_id[:8]}...")
        
        conn.commit()
        print(f"\n🎉 Migration completed! Migrated {migrated_count} habits to projects.")


def rollback_migration():
    """Rollback: Remove project associations from habits"""
    if settings.db_type == "sqlite":
        db_url = f"sqlite:///{settings.sqlite_path}"
    else:
        db_url = settings.DATABASE_URL
    
    engine = create_engine(db_url)
    
    with engine.connect() as conn:
        print("⚠️ Rolling back habit migration...")
        
        # Find projects that were migrated from habits
        result = conn.execute(text("""
            SELECT id, target_kpi FROM projects 
            WHERE target_kpi LIKE '%migrated_from_habit%'
        """))
        
        migrated_projects = result.fetchall()
        
        for project in migrated_projects:
            project_id = project[0]
            
            # Clear project_id from events
            conn.execute(text("""
                UPDATE events 
                SET project_id = NULL 
                WHERE project_id = :project_id
            """), {"project_id": project_id})
            
            # Delete the project
            conn.execute(text("""
                DELETE FROM projects WHERE id = :project_id
            """), {"project_id": project_id})
            
        conn.commit()
        print(f"Rollback completed: removed {len(migrated_projects)} migrated projects")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Migrate habits to projects")
    parser.add_argument("--rollback", action="store_true", help="Rollback the migration")
    args = parser.parse_args()
    
    if args.rollback:
        rollback_migration()
    else:
        run_migration()
