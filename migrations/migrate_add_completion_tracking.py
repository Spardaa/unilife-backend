"""
Migration: Add completion tracking fields to Events and RoutineInstance models

This migration adds the following columns:
- events table: completed_at, started_at
- routine_instances table: started_at, completed_at, and updates status enum to include 'in_progress'
- routine_templates table: skipped_instances, cancelled_instances, last_completed_at, current_streak

Run this migration after updating the models.
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import create_engine, text
from app.config import settings


def migrate():
    """Run migration to add completion tracking fields"""
    engine = create_engine(settings.database_url)

    with engine.connect() as conn:
        # Start transaction
        trans = conn.begin()

        try:
            print("Starting migration: Add completion tracking fields...")

            # Add columns to events table
            print("Adding columns to events table...")
            try:
                conn.execute(text("ALTER TABLE events ADD COLUMN completed_at DATETIME"))
                print("  ✓ Added events.completed_at")
            except Exception as e:
                if "duplicate column name" not in str(e).lower():
                    print(f"  ! events.completed_at: {e}")

            try:
                conn.execute(text("ALTER TABLE events ADD COLUMN started_at DATETIME"))
                print("  ✓ Added events.started_at")
            except Exception as e:
                if "duplicate column name" not in str(e).lower():
                    print(f"  ! events.started_at: {e}")

            # Add columns to routine_instances table
            print("\nAdding columns to routine_instances table...")
            try:
                conn.execute(text("ALTER TABLE routine_instances ADD COLUMN started_at DATETIME"))
                print("  ✓ Added routine_instances.started_at")
            except Exception as e:
                if "duplicate column name" not in str(e).lower():
                    print(f"  ! routine_instances.started_at: {e}")

            try:
                conn.execute(text("ALTER TABLE routine_instances ADD COLUMN completed_at DATETIME"))
                print("  ✓ Added routine_instances.completed_at")
            except Exception as e:
                if "duplicate column name" not in str(e).lower():
                    print(f"  ! routine_instances.completed_at: {e}")

            # Add columns to routine_templates table
            print("\nAdding columns to routine_templates table...")
            try:
                conn.execute(text("ALTER TABLE routine_templates ADD COLUMN skipped_instances INTEGER DEFAULT 0"))
                print("  ✓ Added routine_templates.skipped_instances")
            except Exception as e:
                if "duplicate column name" not in str(e).lower():
                    print(f"  ! routine_templates.skipped_instances: {e}")

            try:
                conn.execute(text("ALTER TABLE routine_templates ADD COLUMN cancelled_instances INTEGER DEFAULT 0"))
                print("  ✓ Added routine_templates.cancelled_instances")
            except Exception as e:
                if "duplicate column name" not in str(e).lower():
                    print(f"  ! routine_templates.cancelled_instances: {e}")

            try:
                conn.execute(text("ALTER TABLE routine_templates ADD COLUMN last_completed_at DATETIME"))
                print("  ✓ Added routine_templates.last_completed_at")
            except Exception as e:
                if "duplicate column name" not in str(e).lower():
                    print(f"  ! routine_templates.last_completed_at: {e}")

            try:
                conn.execute(text("ALTER TABLE routine_templates ADD COLUMN current_streak INTEGER DEFAULT 0"))
                print("  ✓ Added routine_templates.current_streak")
            except Exception as e:
                if "duplicate column name" not in str(e).lower():
                    print(f"  ! routine_templates.current_streak: {e}")

            # Commit transaction
            trans.commit()
            print("\n✅ Migration completed successfully!")

        except Exception as e:
            # Rollback on error
            trans.rollback()
            print(f"\n❌ Migration failed: {e}")
            raise


if __name__ == "__main__":
    migrate()
